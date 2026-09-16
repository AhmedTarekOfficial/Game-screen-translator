"""
ocr_engine.py
-------------
Text extraction from PIL Images.

Pipeline:
  1. Preprocess image (grayscale + contrast boost + 2× upscale)
  2. EasyOCR (primary) — deep-learning based, best for game text
  3. pytesseract (fallback) — fires when EasyOCR confidence < threshold
                              or when EasyOCR returns empty text

EasyOCR is lazy-loaded on first use to keep startup fast.
Tesseract is optional — a warning is shown if the binary is missing.
"""

import threading
from typing import Optional

from PIL import Image, ImageEnhance, ImageFilter


# ---------------------------------------------------------------------------
# Lazy singletons
# ---------------------------------------------------------------------------

_easyocr_reader = None
_easyocr_languages: list[str] = []
_easyocr_lock = threading.Lock()
_tesseract_available = None          # None = not yet checked


def _get_easyocr(languages: list[str] = None):
    """
    Return (or create) the shared EasyOCR Reader. Thread-safe.
    Re-creates the reader if the language list changes.
    """
    global _easyocr_reader, _easyocr_languages
    if languages is None:
        languages = ["en"]
    with _easyocr_lock:
        # Re-create reader if languages changed or not yet created
        if _easyocr_reader is None or sorted(languages) != sorted(_easyocr_languages):
            try:
                import easyocr  # noqa: PLC0415
                _easyocr_reader = easyocr.Reader(
                    languages, gpu=False, verbose=False
                )
                _easyocr_languages = list(languages)
            except ImportError:
                raise RuntimeError(
                    "easyocr is not installed. Run: pip install easyocr"
                )
    return _easyocr_reader


def _is_tesseract_available(custom_path: str = "") -> bool:
    """Check once whether pytesseract + the Tesseract binary are available."""
    global _tesseract_available
    if _tesseract_available is not None:
        return _tesseract_available
    try:
        import pytesseract  # noqa: PLC0415
        if custom_path:
            pytesseract.pytesseract.tesseract_cmd = custom_path
        pytesseract.get_tesseract_version()
        _tesseract_available = True
    except Exception:
        _tesseract_available = False
    return _tesseract_available


# ---------------------------------------------------------------------------
# Preprocessing
# ---------------------------------------------------------------------------

def preprocess_image(img: Image.Image) -> Image.Image:
    """
    Enhance image quality before OCR:
      • Convert to RGB if needed
      • Upscale 2× (OCR engines work better on larger images)
      • Convert to grayscale
      • Boost contrast by 1.8×
      • Slight sharpening
    """
    # Ensure RGB mode
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")
    if img.mode == "RGBA":
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.split()[3])
        img = background

    # 2× upscale with high-quality resampling
    new_size = (img.width * 2, img.height * 2)
    img = img.resize(new_size, Image.LANCZOS)

    # Grayscale
    img = img.convert("L")

    # Contrast boost
    img = ImageEnhance.Contrast(img).enhance(1.8)

    # Sharpen
    img = img.filter(ImageFilter.SHARPEN)

    return img


# ---------------------------------------------------------------------------
# OCR Engine
# ---------------------------------------------------------------------------

class OCRResult:
    """Holds OCR output with metadata."""

    def __init__(
        self,
        text: str,
        confidence: float,
        engine: str,
        raw_data: Optional[list] = None,
    ):
        self.text = text.strip()
        self.confidence = confidence
        self.engine = engine          # "easyocr" | "tesseract"
        self.raw_data = raw_data or []

    def __bool__(self):
        return bool(self.text)

    def __repr__(self):
        snippet = self.text[:60].replace("\n", " ")
        return (
            f"<OCRResult engine={self.engine!r} "
            f"confidence={self.confidence:.2f} text={snippet!r}>"
        )


def run_easyocr(
    img: Image.Image,
    languages: list[str] = None,
) -> OCRResult:
    """
    Run EasyOCR on a PIL Image.

    Returns an OCRResult. Confidence is the mean of all detected blocks.
    """
    if languages is None:
        languages = ["en"]
    reader = _get_easyocr(languages)

    # EasyOCR accepts numpy arrays or file paths;
    # convert PIL Image → bytes → numpy via io buffer
    import numpy as np  # noqa: PLC0415
    img_np = np.array(img.convert("RGB"))

    results = reader.readtext(img_np, detail=1, paragraph=False)
    # results: list of ([bbox], text, confidence)

    if not results:
        return OCRResult(text="", confidence=0.0, engine="easyocr", raw_data=[])

    texts = []
    confidences = []
    for (_, text, conf) in results:
        texts.append(text)
        confidences.append(conf)

    combined_text = " ".join(texts)
    mean_confidence = sum(confidences) / len(confidences)

    return OCRResult(
        text=combined_text,
        confidence=mean_confidence,
        engine="easyocr",
        raw_data=results,
    )


def run_tesseract(
    img: Image.Image,
    lang: str = "eng",
    tesseract_path: str = "",
) -> OCRResult:
    """
    Run pytesseract on a PIL Image as a fallback.

    Returns an OCRResult with a fixed confidence of 0.5
    (Tesseract doesn't provide per-result confidence easily).
    """
    try:
        import pytesseract  # noqa: PLC0415
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path

        config = "--psm 6 --oem 3"          # Assume a single uniform block
        text = pytesseract.image_to_string(
            img, lang=lang, config=config
        ).strip()

        # Get per-word confidence from Tesseract data
        data = pytesseract.image_to_data(
            img, lang=lang, config=config,
            output_type=pytesseract.Output.DICT
        )
        confs = [
            c for c in data["conf"]
            if isinstance(c, (int, float)) and c != -1
        ]
        confidence = (sum(confs) / len(confs) / 100.0) if confs else 0.5

        return OCRResult(
            text=text, confidence=confidence, engine="tesseract"
        )
    except Exception as e:
        return OCRResult(text="", confidence=0.0, engine="tesseract")


def extract_text(
    img: Image.Image,
    confidence_threshold: float = 0.6,
    languages: list[str] = None,
    tesseract_path: str = "",
    ocr_language: str = "en",
) -> OCRResult:
    """
    Main entry point: run the full OCR pipeline.

    1. Preprocess the image.
    2. Try EasyOCR.
    3. If confidence < threshold or text is empty → fallback to Tesseract.

    Parameters
    ----------
    img : PIL.Image.Image
        The captured screen region.
    confidence_threshold : float
        Min EasyOCR confidence before falling back (default 0.6).
    languages : list[str]
        EasyOCR language codes (default ['en']).
    tesseract_path : str
        Optional path to Tesseract binary (for non-standard installs).
    ocr_language : str
        Language code used for both EasyOCR and Tesseract.

    Returns
    -------
    OCRResult
        Best result from the pipeline, with engine name and confidence.
    """
    if languages is None:
        languages = [ocr_language] if ocr_language else ["en"]

    # Step 1 — preprocess
    processed = preprocess_image(img)

    # Step 2 — EasyOCR (primary)
    try:
        easy_result = run_easyocr(processed, languages=languages)
    except Exception as e:
        print(f"[OCR] EasyOCR error: {e}")
        easy_result = OCRResult(text="", confidence=0.0, engine="easyocr")

    # Step 3 — decide if fallback is needed
    needs_fallback = (
        not easy_result.text
        or easy_result.confidence < confidence_threshold
    )

    if needs_fallback and _is_tesseract_available(tesseract_path):
        tess_lang = ocr_language if ocr_language != "en" else "eng"
        tess_result = run_tesseract(processed, lang=tess_lang, tesseract_path=tesseract_path)

        # Use tesseract result if it produced more text or better confidence
        if tess_result.text and (
            not easy_result.text
            or tess_result.confidence > easy_result.confidence
        ):
            return tess_result

    return easy_result


def warmup_easyocr(languages: list[str] = None) -> None:
    """
    Pre-load the EasyOCR model in a background thread.
    Call this at app startup to avoid the 5-second first-run delay.
    """
    if languages is None:
        languages = ["en"]

    def _load():
        try:
            _get_easyocr(languages)
            print("[OCR] EasyOCR model loaded and ready.")
        except Exception as e:
            print(f"[OCR] EasyOCR warmup failed: {e}")

    t = threading.Thread(target=_load, daemon=True, name="easyocr-warmup")
    t.start()
