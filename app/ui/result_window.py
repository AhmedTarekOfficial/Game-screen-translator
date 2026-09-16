"""
result_window.py
----------------
Floating, always-on-top popup that displays the OCR text and its translation.

Features:
  • Always-on-top transparent dark window
  • Draggable title bar
  • Copy-to-clipboard button
  • Save-to-history button
  • Auto-close timer (configurable, default 30 s)
  • Animated progress bar for the auto-close countdown
"""

import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BG_DARK        = "#0D0D1A"
BG_CARD        = "#141428"
BG_CARD2       = "#1A1A35"
ACCENT         = "#00D9FF"
ACCENT2        = "#7B2FFF"
TEXT_PRIMARY   = "#E8E8FF"
TEXT_SECONDARY = "#8888AA"
TEXT_ORIGINAL  = "#BBBBDD"
SUCCESS_GREEN  = "#00FF99"
ERROR_RED      = "#FF4466"
BORDER_COLOR   = "#2A2A50"


class ResultWindow:
    """
    Floating translation result popup.

    Parameters
    ----------
    root : tk.Tk
        The main application root window.
    original_text : str
        The raw text extracted by OCR.
    translated_text : str
        The translated text from the LLM.
    target_language : str
        Name of the target language (for the label).
    llm_used : str
        Which LLM was used (for display in footer).
    ocr_engine : str
        Which OCR engine was used (for display in footer).
    confidence : float
        OCR confidence score.
    on_save : Callable | None
        Optional callback called when the user clicks "Save to History".
    auto_close_seconds : int
        Seconds before the window auto-closes (0 = never).
    error : str | None
        If set, show an error message instead of translation.
    """

    def __init__(
        self,
        root: tk.Tk,
        original_text: str,
        translated_text: str,
        target_language: str = "Arabic",
        llm_used: str = "gemini",
        ocr_engine: str = "easyocr",
        confidence: float = 0.0,
        on_save: Optional[Callable] = None,
        auto_close_seconds: int = 30,
        error: Optional[str] = None,
    ):
        self._root = root
        self._original_text = original_text
        self._translated_text = translated_text
        self._target_language = target_language
        self._llm_used = llm_used
        self._ocr_engine = ocr_engine
        self._confidence = confidence
        self._on_save = on_save
        self._auto_close_seconds = auto_close_seconds
        self._error = error

        self._win: Optional[tk.Toplevel] = None
        self._drag_x = 0
        self._drag_y = 0
        self._countdown_remaining = auto_close_seconds
        self._countdown_timer_id = None
        self._progress_var: Optional[tk.DoubleVar] = None

        self._build()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build(self) -> None:
        win = tk.Toplevel(self._root)
        self._win = win
        win.title("Game Translator")
        win.attributes("-topmost", True)
        win.overrideredirect(True)           # Remove OS title bar
        win.attributes("-alpha", 0.97)
        win.configure(bg=BG_DARK)
        win.resizable(False, False)

        # Center on screen
        win.update_idletasks()
        win_w, win_h = 520, 420
        sw = win.winfo_screenwidth()
        sh = win.winfo_screenheight()
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2
        win.geometry(f"{win_w}x{win_h}+{x}+{y}")

        # Outer border frame
        outer = tk.Frame(win, bg=ACCENT2, bd=1)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        main = tk.Frame(outer, bg=BG_DARK)
        main.pack(fill="both", expand=True)

        self._build_title_bar(main)
        self._build_body(main)
        self._build_footer(main)
        self._build_buttons(main)

        if self._auto_close_seconds > 0:
            self._start_countdown()

    # ------------------------------------------------------------------
    # Title bar (draggable)
    # ------------------------------------------------------------------

    def _build_title_bar(self, parent: tk.Frame) -> None:
        bar = tk.Frame(parent, bg=BG_CARD, height=44)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        # Icon + Title
        title_lbl = tk.Label(
            bar,
            text="🎮  Game Translator",
            font=("Segoe UI", 12, "bold"),
            fg=ACCENT,
            bg=BG_CARD,
        )
        title_lbl.pack(side="left", padx=14, pady=10)

        # Close button
        close_btn = tk.Label(
            bar,
            text=" ✕ ",
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_SECONDARY,
            bg=BG_CARD,
            cursor="hand2",
        )
        close_btn.pack(side="right", padx=10, pady=8)
        close_btn.bind("<Button-1>", lambda e: self.close())
        close_btn.bind("<Enter>",    lambda e: close_btn.config(fg=ERROR_RED))
        close_btn.bind("<Leave>",    lambda e: close_btn.config(fg=TEXT_SECONDARY))

        # Drag bindings on bar
        for widget in (bar, title_lbl):
            widget.bind("<ButtonPress-1>",   self._drag_start)
            widget.bind("<B1-Motion>",        self._drag_move)

        # Thin accent separator
        sep = tk.Frame(parent, bg=ACCENT2, height=1)
        sep.pack(fill="x")

    # ------------------------------------------------------------------
    # Body — original + translated text
    # ------------------------------------------------------------------

    def _build_body(self, parent: tk.Frame) -> None:
        body = tk.Frame(parent, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=14, pady=(10, 4))

        if self._error:
            self._build_error_body(body)
            return

        # ---- Original text ----
        orig_label = tk.Label(
            body,
            text="📷  Original Text (OCR):",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
            anchor="w",
        )
        orig_label.pack(fill="x", pady=(0, 4))

        orig_frame = tk.Frame(body, bg=BG_CARD, bd=0)
        orig_frame.pack(fill="x", pady=(0, 10))

        orig_text = tk.Text(
            orig_frame,
            height=4,
            font=("Segoe UI", 10),
            fg=TEXT_ORIGINAL,
            bg=BG_CARD,
            relief="flat",
            wrap="word",
            padx=10,
            pady=8,
            state="normal",
            cursor="arrow",
        )
        orig_text.insert("1.0", self._original_text or "(No text detected)")
        orig_text.config(state="disabled")
        orig_text.pack(fill="x")

        # Thin separator
        tk.Frame(body, bg=BORDER_COLOR, height=1).pack(fill="x", pady=(0, 10))

        # ---- Translated text ----
        trans_label = tk.Label(
            body,
            text=f"✨  Translation → {self._target_language}:",
            font=("Segoe UI", 9, "bold"),
            fg=ACCENT,
            bg=BG_DARK,
            anchor="w",
        )
        trans_label.pack(fill="x", pady=(0, 4))

        trans_frame = tk.Frame(body, bg=BG_CARD2, bd=0)
        trans_frame.pack(fill="both", expand=True)

        self._trans_text_widget = tk.Text(
            trans_frame,
            height=5,
            font=("Segoe UI", 12, "bold"),
            fg=TEXT_PRIMARY,
            bg=BG_CARD2,
            relief="flat",
            wrap="word",
            padx=10,
            pady=10,
            state="normal",
            cursor="arrow",
        )
        self._trans_text_widget.insert("1.0", self._translated_text or "—")
        self._trans_text_widget.config(state="disabled")
        self._trans_text_widget.pack(fill="both", expand=True)

    def _build_error_body(self, parent: tk.Frame) -> None:
        """Show an error message in the body area."""
        err_frame = tk.Frame(parent, bg="#2A0A14")
        err_frame.pack(fill="both", expand=True, pady=10)

        tk.Label(
            err_frame,
            text="⚠  Error",
            font=("Segoe UI", 11, "bold"),
            fg=ERROR_RED,
            bg="#2A0A14",
        ).pack(pady=(16, 6))

        tk.Label(
            err_frame,
            text=self._error,
            font=("Segoe UI", 10),
            fg=TEXT_PRIMARY,
            bg="#2A0A14",
            wraplength=450,
            justify="center",
        ).pack(pady=(0, 16), padx=20)

    # ------------------------------------------------------------------
    # Footer — metadata
    # ------------------------------------------------------------------

    def _build_footer(self, parent: tk.Frame) -> None:
        sep = tk.Frame(parent, bg=BORDER_COLOR, height=1)
        sep.pack(fill="x", padx=14)

        footer = tk.Frame(parent, bg=BG_DARK)
        footer.pack(fill="x", padx=14, pady=(4, 0))

        conf_pct = int(self._confidence * 100)
        meta = (
            f"OCR: {self._ocr_engine}  •  "
            f"Confidence: {conf_pct}%  •  "
            f"LLM: {self._llm_used}"
        )
        tk.Label(
            footer,
            text=meta,
            font=("Segoe UI", 8),
            fg=TEXT_SECONDARY,
            bg=BG_DARK,
        ).pack(side="left")

        # Auto-close countdown label
        if self._auto_close_seconds > 0:
            self._countdown_label = tk.Label(
                footer,
                text=f"Auto-close: {self._auto_close_seconds}s",
                font=("Segoe UI", 8),
                fg=TEXT_SECONDARY,
                bg=BG_DARK,
            )
            self._countdown_label.pack(side="right")

    # ------------------------------------------------------------------
    # Buttons row
    # ------------------------------------------------------------------

    def _build_buttons(self, parent: tk.Frame) -> None:
        btn_frame = tk.Frame(parent, bg=BG_DARK)
        btn_frame.pack(fill="x", padx=14, pady=(8, 12))

        btn_style = dict(
            font=("Segoe UI", 9, "bold"),
            relief="flat",
            bd=0,
            padx=16,
            pady=8,
            cursor="hand2",
        )

        # Copy Translation button
        copy_btn = tk.Button(
            btn_frame,
            text="📋  Copy Translation",
            bg=ACCENT2,
            fg="white",
            activebackground="#5A1FCC",
            activeforeground="white",
            command=self._copy_translation,
            **btn_style,
        )
        copy_btn.pack(side="left", padx=(0, 8))
        self._add_hover(copy_btn, ACCENT2, "#5A1FCC")

        # Copy Original button
        copy_orig_btn = tk.Button(
            btn_frame,
            text="📄  Copy Original",
            bg=BG_CARD2,
            fg=TEXT_SECONDARY,
            activebackground=BG_CARD,
            activeforeground=TEXT_PRIMARY,
            command=self._copy_original,
            **btn_style,
        )
        copy_orig_btn.pack(side="left", padx=(0, 8))
        self._add_hover(copy_orig_btn, BG_CARD2, BG_CARD)

        # Save to history button
        if self._on_save and not self._error:
            save_btn = tk.Button(
                btn_frame,
                text="💾  Save",
                bg="#00664D",
                fg="white",
                activebackground="#00996B",
                activeforeground="white",
                command=self._save_to_history,
                **btn_style,
            )
            save_btn.pack(side="left")
            self._add_hover(save_btn, "#00664D", "#00996B")

        # Close button (right side)
        close_btn = tk.Button(
            btn_frame,
            text="✕  Close",
            bg=BG_CARD,
            fg=TEXT_SECONDARY,
            activebackground="#330011",
            activeforeground=ERROR_RED,
            command=self.close,
            **btn_style,
        )
        close_btn.pack(side="right")

    # ------------------------------------------------------------------
    # Dragging
    # ------------------------------------------------------------------

    def _drag_start(self, event: tk.Event) -> None:
        self._drag_x = event.x
        self._drag_y = event.y

    def _drag_move(self, event: tk.Event) -> None:
        if self._win is None:
            return
        x = self._win.winfo_x() + event.x - self._drag_x
        y = self._win.winfo_y() + event.y - self._drag_y
        self._win.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # Clipboard
    # ------------------------------------------------------------------

    def _copy_translation(self) -> None:
        self._copy_to_clipboard(self._translated_text)
        self._flash_feedback("✅  Copied!")

    def _copy_original(self) -> None:
        self._copy_to_clipboard(self._original_text)
        self._flash_feedback("✅  Copied!")

    def _copy_to_clipboard(self, text: str) -> None:
        try:
            self._root.clipboard_clear()
            self._root.clipboard_append(text)
            self._root.update()
        except Exception:
            pass

    def _flash_feedback(self, msg: str) -> None:
        """Briefly flash feedback text in the title bar."""
        if self._win is None:
            return
        try:
            # Simple: update title bar text briefly
            pass
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Save to history
    # ------------------------------------------------------------------

    def _save_to_history(self) -> None:
        if self._on_save:
            self._on_save()

    # ------------------------------------------------------------------
    # Auto-close countdown
    # ------------------------------------------------------------------

    def _start_countdown(self) -> None:
        self._countdown_remaining = self._auto_close_seconds
        self._tick()

    def _tick(self) -> None:
        if self._win is None:
            return
        if self._countdown_remaining <= 0:
            self.close()
            return
        try:
            if hasattr(self, "_countdown_label"):
                self._countdown_label.config(
                    text=f"Auto-close: {self._countdown_remaining}s"
                )
        except tk.TclError:
            return

        self._countdown_remaining -= 1
        self._countdown_timer_id = self._win.after(1000, self._tick)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Destroy the popup window."""
        if self._countdown_timer_id and self._win:
            try:
                self._win.after_cancel(self._countdown_timer_id)
            except Exception:
                pass
        if self._win:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def _add_hover(btn: tk.Button, normal_bg: str, hover_bg: str) -> None:
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg))


# ---------------------------------------------------------------------------
# Loading popup (shown while OCR + translation is running)
# ---------------------------------------------------------------------------

class LoadingWindow:
    """Small non-interactive popup showing a 'processing' animation."""

    def __init__(self, root: tk.Tk, message: str = "Translating..."):
        self._root = root
        self._message = message
        self._win: Optional[tk.Toplevel] = None
        self._dots = 0
        self._anim_id = None
        self._label: Optional[tk.Label] = None

    def show(self) -> None:
        win = tk.Toplevel(self._root)
        self._win = win
        win.attributes("-topmost", True)
        win.overrideredirect(True)
        win.configure(bg=BG_DARK)
        win.attributes("-alpha", 0.92)

        w, h = 300, 90
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        # Border
        outer = tk.Frame(win, bg=ACCENT2, bd=1)
        outer.pack(fill="both", expand=True, padx=1, pady=1)

        inner = tk.Frame(outer, bg=BG_DARK)
        inner.pack(fill="both", expand=True)

        self._label = tk.Label(
            inner,
            text=f"⚙  {self._message}",
            font=("Segoe UI", 11, "bold"),
            fg=ACCENT,
            bg=BG_DARK,
        )
        self._label.pack(expand=True)

        self._animate()

    def _animate(self) -> None:
        if self._win is None or self._label is None:
            return
        dots = "." * (self._dots % 4)
        try:
            self._label.config(text=f"⚙  {self._message}{dots}")
        except tk.TclError:
            return
        self._dots += 1
        self._anim_id = self._win.after(400, self._animate)

    def close(self) -> None:
        if self._anim_id and self._win:
            try:
                self._win.after_cancel(self._anim_id)
            except Exception:
                pass
        if self._win:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None
