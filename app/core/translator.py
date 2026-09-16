"""
translator.py
-------------
Multi-LLM translation client.

Supported backends:
  • Google Gemini  (default) — gemini-1.5-flash
  • OpenAI         — gpt-4o-mini

The translation prompt is context-aware and designed specifically
for in-game text to preserve tone and game-specific terminology.

All API calls are synchronous (run in a background thread by the caller).
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

TRANSLATION_PROMPT = """You are a professional game translator with deep knowledge of gaming terminology and culture.

Translate the following in-game text to {target_language}.

Rules:
- Preserve the original tone (epic, humorous, scary, etc.)
- Keep game-specific terms (item names, skill names, character names) intact or transliterate them naturally
- If the text contains UI labels (e.g. "Inventory", "Save Game"), translate them naturally
- Return ONLY the translation — no explanations, no notes, no alternatives
- If the text is already in {target_language}, return it as-is

Text to translate:
\"\"\"
{text}
\"\"\"
"""


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

class TranslationResult:
    """Holds the result of a translation call."""

    def __init__(
        self,
        translated_text: str,
        original_text: str,
        target_language: str,
        llm_used: str,
        error: Optional[str] = None,
    ):
        self.translated_text = translated_text
        self.original_text = original_text
        self.target_language = target_language
        self.llm_used = llm_used
        self.error = error
        self.success = error is None and bool(translated_text)

    def __repr__(self):
        snippet = self.translated_text[:60].replace("\n", " ")
        return (
            f"<TranslationResult llm={self.llm_used!r} "
            f"success={self.success} text={snippet!r}>"
        )


# ---------------------------------------------------------------------------
# Gemini Backend
# ---------------------------------------------------------------------------

def _translate_gemini(
    text: str,
    target_language: str,
    api_key: str,
    model: str = "gemini-3.6-flash",
) -> TranslationResult:
    """Call Google Gemini API to translate text using the new google-genai SDK."""
    if not api_key:
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used="gemini",
            error="Gemini API key is not set. Please add it in Settings.",
        )

    # Fallback model list if the primary is unavailable
    models_to_try = [model, "gemini-2.5-flash", "gemini-2.5-flash-lite"]

    try:
        from google import genai  # noqa: PLC0415
        from google.genai import types  # noqa: PLC0415

        client = genai.Client(api_key=api_key)

        prompt = TRANSLATION_PROMPT.format(
            target_language=target_language,
            text=text,
        )

        last_error = None
        for model_name in models_to_try:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        max_output_tokens=1024,
                    ),
                )
                translated = response.text.strip()
                return TranslationResult(
                    translated_text=translated,
                    original_text=text,
                    target_language=target_language,
                    llm_used=f"gemini ({model_name})",
                )
            except Exception as e:
                last_error = e
                print(f"[Translator] Model {model_name} failed: {e}, trying next...")
                continue

        raise last_error

    except Exception as e:
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used="gemini",
            error=f"Gemini error: {e}",
        )



# ---------------------------------------------------------------------------
# OpenAI Backend
# ---------------------------------------------------------------------------

def _translate_openai(
    text: str,
    target_language: str,
    api_key: str,
    model: str = "gpt-4o-mini",
) -> TranslationResult:
    """Call OpenAI API to translate text."""
    if not api_key:
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used="openai",
            error="OpenAI API key is not set. Please add it in Settings.",
        )
    try:
        from openai import OpenAI  # noqa: PLC0415
        client = OpenAI(api_key=api_key)

        prompt = TRANSLATION_PROMPT.format(
            target_language=target_language,
            text=text,
        )
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024,
        )
        translated = response.choices[0].message.content.strip()

        return TranslationResult(
            translated_text=translated,
            original_text=text,
            target_language=target_language,
            llm_used="openai",
        )

    except Exception as e:
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used="openai",
            error=f"OpenAI error: {e}",
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

SUPPORTED_LLMS = {
    "gemini": "Google Gemini (gemini-1.5-flash)",
    "openai": "OpenAI (gpt-4o-mini)",
}

SUPPORTED_LANGUAGES = [
    "Arabic",
    "English",
    "French",
    "Spanish",
    "German",
    "Italian",
    "Portuguese",
    "Russian",
    "Japanese",
    "Chinese (Simplified)",
    "Chinese (Traditional)",
    "Korean",
    "Turkish",
    "Polish",
    "Dutch",
    "Swedish",
    "Norwegian",
    "Danish",
    "Finnish",
    "Greek",
    "Hebrew",
    "Hindi",
    "Thai",
    "Vietnamese",
    "Indonesian",
]


def translate(
    text: str,
    target_language: str,
    selected_llm: str,
    api_keys: dict[str, str],
) -> TranslationResult:
    """
    Translate `text` to `target_language` using the selected LLM.

    Parameters
    ----------
    text : str
        The raw OCR-extracted text to translate.
    target_language : str
        Human-readable target language name (e.g. "Arabic").
    selected_llm : str
        LLM identifier: "gemini" | "openai"
    api_keys : dict
        Mapping of LLM name to API key string.
        e.g. {"gemini": "AIza...", "openai": "sk-..."}

    Returns
    -------
    TranslationResult
    """
    if not text or not text.strip():
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used=selected_llm,
            error="No text provided for translation.",
        )

    llm = selected_llm.lower().strip()

    if llm == "gemini":
        return _translate_gemini(
            text=text,
            target_language=target_language,
            api_key=api_keys.get("gemini", ""),
        )
    elif llm == "openai":
        return _translate_openai(
            text=text,
            target_language=target_language,
            api_key=api_keys.get("openai", ""),
        )
    else:
        return TranslationResult(
            translated_text="",
            original_text=text,
            target_language=target_language,
            llm_used=llm,
            error=f"Unknown LLM: '{llm}'. Supported: {list(SUPPORTED_LLMS.keys())}",
        )
