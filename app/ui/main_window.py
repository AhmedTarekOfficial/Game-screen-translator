"""
main_window.py
--------------
Main application window built with CustomTkinter.

Tabs:
  1. Translator  — status, last captured image, manual trigger button
  2. History     — searchable list of past translations
  3. Settings    — hotkey recorder, API keys, LLM, language, OCR settings

The window minimises to the taskbar (not system tray — tray needs
third-party pystray which is optional). Hotkey listening continues
even when the window is minimised.
"""

from __future__ import annotations

import threading
import tkinter as tk
import tkinter.filedialog as fd
import tkinter.messagebox as mb
from datetime import datetime
from typing import Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from app.core.hotkey_manager import HotkeyManager
from app.core.ocr_engine import extract_text, warmup_easyocr, _is_tesseract_available
from app.core.screenshot import capture_region
from app.core.translator import SUPPORTED_LANGUAGES, SUPPORTED_LLMS, translate
from app.data.config_manager import ConfigManager
from app.data.history_manager import HistoryManager
from app.ui.overlay import RegionOverlay
from app.ui.result_window import LoadingWindow, ResultWindow


# ---------------------------------------------------------------------------
# Theming
# ---------------------------------------------------------------------------

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

ACCENT_COLOR = "#00D9FF"
ACCENT2_COLOR = "#7B2FFF"
BG_DARK = "#0D0D1A"
BG_CARD = "#141428"
BG_CARD2 = "#1A1A35"
TEXT_PRIMARY = "#E8E8FF"
TEXT_SECONDARY = "#8888AA"
SUCCESS = "#00FF99"
ERROR = "#FF4466"
WARNING = "#FFB800"


# ---------------------------------------------------------------------------
# MainWindow
# ---------------------------------------------------------------------------

class MainWindow:
    """
    The primary application window.
    Holds references to all managers and orchestrates the full
    capture → OCR → translate → display pipeline.
    """

    APP_TITLE = "🎮 Game Screen Translator"
    APP_SIZE = "820x600"

    def __init__(self):
        self._config = ConfigManager()
        self._config.load()
        self._history = HistoryManager()
        self._history.init_db()

        self._root = ctk.CTk()
        self._root.title(self.APP_TITLE)
        self._root.geometry(self.APP_SIZE)
        self._root.resizable(False, False)
        self._root.configure(fg_color=BG_DARK)

        self._loading_win: Optional[LoadingWindow] = None
        self._result_win: Optional[ResultWindow] = None
        self._last_image: Optional[Image.Image] = None
        self._last_ocr_result = None
        self._last_translation = None
        self._status_var = tk.StringVar(value="Ready  ✓")
        self._status_color_var = "#00FF99"

        # Hotkey manager
        hotkey_str = self._config.get("hotkey", "<ctrl>+<alt>+t")
        self._hotkey_mgr = HotkeyManager(
            hotkey_str=hotkey_str,
            on_trigger=self._on_hotkey_triggered,
            root=self._root,
        )

        self._build_ui()
        self._hotkey_mgr.start()

        # Warm up EasyOCR in background
        ocr_lang = self._config.get("ocr_language", "en")
        warmup_easyocr([ocr_lang])

        # Handle window close
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        self._root.mainloop()

    # ------------------------------------------------------------------
    # UI Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        # ---- Header ----
        self._build_header()

        # ---- Tab view ----
        self._tabview = ctk.CTkTabview(
            self._root,
            fg_color=BG_CARD,
            segmented_button_fg_color=BG_DARK,
            segmented_button_selected_color=ACCENT2_COLOR,
            segmented_button_unselected_color=BG_DARK,
            segmented_button_selected_hover_color="#6020EE",
            text_color=TEXT_PRIMARY,
        )
        self._tabview.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self._tabview.add("  🎮 Translator  ")
        self._tabview.add("  📚 History  ")
        self._tabview.add("  ⚙ Settings  ")

        self._build_translator_tab(self._tabview.tab("  🎮 Translator  "))
        self._build_history_tab(self._tabview.tab("  📚 History  "))
        self._build_settings_tab(self._tabview.tab("  ⚙ Settings  "))

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self._root, fg_color=BG_CARD, height=70, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)

        # Left: icon + title
        left = ctk.CTkFrame(header, fg_color="transparent")
        left.pack(side="left", padx=20, pady=12)

        ctk.CTkLabel(
            left,
            text="🎮",
            font=ctk.CTkFont(size=28),
        ).pack(side="left", padx=(0, 10))

        title_frame = ctk.CTkFrame(left, fg_color="transparent")
        title_frame.pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="Game Screen Translator",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_frame,
            text="OCR + AI Translation  ·  Always-on hotkey",
            font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w")

        # Right: status pill
        right = ctk.CTkFrame(header, fg_color="transparent")
        right.pack(side="right", padx=20)

        self._status_label = ctk.CTkLabel(
            right,
            textvariable=self._status_var,
            font=ctk.CTkFont(family="Segoe UI", size=10, weight="bold"),
            text_color=SUCCESS,
        )
        self._status_label.pack()

        hotkey_disp = HotkeyManager.format_hotkey_display(
            self._config.get("hotkey", "<ctrl>+<alt>+t")
        )
        self._hotkey_display_label = ctk.CTkLabel(
            right,
            text=f"Hotkey: {hotkey_disp}",
            font=ctk.CTkFont(size=9),
            text_color=TEXT_SECONDARY,
        )
        self._hotkey_display_label.pack()

    # ------------------------------------------------------------------
    # Tab 1: Translator
    # ------------------------------------------------------------------

    def _build_translator_tab(self, parent) -> None:
        parent.configure(fg_color=BG_CARD)

        # Top: big capture button
        capture_frame = ctk.CTkFrame(parent, fg_color="transparent")
        capture_frame.pack(fill="x", padx=20, pady=(20, 10))

        self._capture_btn = ctk.CTkButton(
            capture_frame,
            text="📸  Capture & Translate",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=ACCENT2_COLOR,
            hover_color="#6020EE",
            height=52,
            corner_radius=12,
            command=self._on_hotkey_triggered,
        )
        self._capture_btn.pack(side="left", expand=True, fill="x", padx=(0, 10))

        hotkey_lbl = ctk.CTkLabel(
            capture_frame,
            text=f"or press\n{HotkeyManager.format_hotkey_display(self._config.get('hotkey', '<ctrl>+<alt>+t'))}",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_SECONDARY,
            width=90,
        )
        hotkey_lbl.pack(side="left")
        self._hotkey_hint_label = hotkey_lbl

        # Divider
        ctk.CTkFrame(parent, fg_color=BG_CARD2, height=1).pack(fill="x", padx=20, pady=(10, 16))

        # Image preview area
        preview_frame = ctk.CTkFrame(parent, fg_color=BG_CARD2, corner_radius=10)
        preview_frame.pack(fill="both", expand=True, padx=20, pady=(0, 12))

        self._preview_label_title = ctk.CTkLabel(
            preview_frame,
            text="Last Captured Region",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_SECONDARY,
        )
        self._preview_label_title.pack(pady=(12, 8))

        self._preview_canvas = tk.Canvas(
            preview_frame,
            bg=BG_DARK,
            bd=0,
            highlightthickness=0,
            width=760,
            height=180,
        )
        self._preview_canvas.pack(padx=10, pady=(0, 12))
        self._preview_canvas.create_text(
            380, 90,
            text="No capture yet — press the button or hotkey to start",
            fill=TEXT_SECONDARY,
            font=("Segoe UI", 10),
        )

        # OCR result preview
        ocr_frame = ctk.CTkFrame(parent, fg_color="transparent")
        ocr_frame.pack(fill="x", padx=20, pady=(0, 4))

        ctk.CTkLabel(
            ocr_frame,
            text="Last OCR Text:",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=TEXT_SECONDARY,
        ).pack(anchor="w")

        self._ocr_preview_label = ctk.CTkLabel(
            ocr_frame,
            text="—",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_PRIMARY,
            wraplength=740,
            justify="left",
            anchor="w",
        )
        self._ocr_preview_label.pack(fill="x", pady=(2, 0))

    # ------------------------------------------------------------------
    # Tab 2: History
    # ------------------------------------------------------------------

    def _build_history_tab(self, parent) -> None:
        parent.configure(fg_color=BG_CARD)

        # Search bar + controls
        top_bar = ctk.CTkFrame(parent, fg_color="transparent")
        top_bar.pack(fill="x", padx=20, pady=(16, 8))

        self._history_search_var = tk.StringVar()
        search_entry = ctk.CTkEntry(
            top_bar,
            placeholder_text="🔍  Search history...",
            textvariable=self._history_search_var,
            fg_color=BG_CARD2,
            border_color=ACCENT2_COLOR,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        search_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        search_entry.bind("<Return>", lambda e: self._refresh_history())
        self._history_search_var.trace("w", lambda *_: self._refresh_history())

        ctk.CTkButton(
            top_bar,
            text="Export CSV",
            width=100,
            height=36,
            fg_color=BG_CARD2,
            hover_color=BG_DARK,
            border_width=1,
            border_color=ACCENT2_COLOR,
            text_color=TEXT_SECONDARY,
            command=self._export_history_csv,
        ).pack(side="right", padx=(0, 0))

        ctk.CTkButton(
            top_bar,
            text="Clear All",
            width=90,
            height=36,
            fg_color=BG_CARD2,
            hover_color="#330011",
            border_width=1,
            border_color=ERROR,
            text_color=ERROR,
            command=self._clear_history,
        ).pack(side="right", padx=(0, 8))

        # Scrollable list
        self._history_frame = ctk.CTkScrollableFrame(
            parent,
            fg_color=BG_CARD2,
            scrollbar_button_color=ACCENT2_COLOR,
            scrollbar_button_hover_color=ACCENT_COLOR,
            corner_radius=10,
        )
        self._history_frame.pack(fill="both", expand=True, padx=20, pady=(0, 16))

        self._history_count_label = ctk.CTkLabel(
            parent,
            text="",
            font=ctk.CTkFont(size=9),
            text_color=TEXT_SECONDARY,
        )
        self._history_count_label.pack(pady=(0, 4))

        self._refresh_history()

    def _refresh_history(self) -> None:
        # Clear old widgets
        for widget in self._history_frame.winfo_children():
            widget.destroy()

        query = self._history_search_var.get().strip()
        if query:
            rows = self._history.search(query)
        else:
            rows = self._history.get_all(limit=100)

        if not rows:
            ctk.CTkLabel(
                self._history_frame,
                text="No history yet — start translating!",
                text_color=TEXT_SECONDARY,
                font=ctk.CTkFont(size=11),
            ).pack(pady=40)
            self._history_count_label.configure(text="0 entries")
            return

        self._history_count_label.configure(text=f"{len(rows)} entries")

        for row in rows:
            self._build_history_card(self._history_frame, row)

    def _build_history_card(self, parent, row: dict) -> None:
        card = ctk.CTkFrame(parent, fg_color=BG_CARD, corner_radius=8)
        card.pack(fill="x", padx=4, pady=4)

        top_row = ctk.CTkFrame(card, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        # Timestamp + LLM badge
        ts = row.get("timestamp", "")
        if ts:
            try:
                ts = datetime.fromisoformat(ts).strftime("%d %b %Y  %H:%M")
            except ValueError:
                pass
        ctk.CTkLabel(
            top_row,
            text=ts,
            font=ctk.CTkFont(size=8),
            text_color=TEXT_SECONDARY,
        ).pack(side="left")

        badge_text = f"{row.get('llm_used','?')}  ·  {row.get('ocr_engine','?')}"
        ctk.CTkLabel(
            top_row,
            text=badge_text,
            font=ctk.CTkFont(size=8),
            text_color=ACCENT_COLOR,
        ).pack(side="right")

        # Original
        orig = (row.get("original_text") or "").strip()[:200]
        ctk.CTkLabel(
            card,
            text=f"📷  {orig}",
            font=ctk.CTkFont(size=10),
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=700,
            justify="left",
        ).pack(fill="x", padx=10, pady=(0, 2))

        # Translated
        trans = (row.get("translated_text") or "").strip()[:300]
        ctk.CTkLabel(
            card,
            text=f"✨  {trans}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_PRIMARY,
            anchor="w",
            wraplength=700,
            justify="left",
        ).pack(fill="x", padx=10, pady=(0, 2))

        # Bottom: delete button
        bot_row = ctk.CTkFrame(card, fg_color="transparent")
        bot_row.pack(fill="x", padx=10, pady=(0, 6))

        entry_id = row.get("id")
        ctk.CTkButton(
            bot_row,
            text="🗑 Delete",
            width=70,
            height=22,
            font=ctk.CTkFont(size=8),
            fg_color="transparent",
            text_color=ERROR,
            hover_color="#330011",
            border_width=0,
            command=lambda eid=entry_id: self._delete_history_entry(eid),
        ).pack(side="right")

    def _delete_history_entry(self, entry_id: int) -> None:
        self._history.delete_entry(entry_id)
        self._refresh_history()

    def _clear_history(self) -> None:
        if mb.askyesno(
            "Clear History",
            "Are you sure you want to delete ALL translation history?",
        ):
            self._history.clear_all()
            self._refresh_history()

    def _export_history_csv(self) -> None:
        path = fd.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Export History to CSV",
        )
        if path:
            count = self._history.export_csv(path)
            mb.showinfo("Export Complete", f"Exported {count} entries to:\n{path}")

    # ------------------------------------------------------------------
    # Tab 3: Settings
    # ------------------------------------------------------------------

    def _build_settings_tab(self, parent) -> None:
        parent.configure(fg_color=BG_CARD)

        scroll = ctk.CTkScrollableFrame(
            parent,
            fg_color="transparent",
            scrollbar_button_color=ACCENT2_COLOR,
        )
        scroll.pack(fill="both", expand=True, padx=20, pady=10)

        # ---- Section: Hotkey ----
        self._settings_section(scroll, "⌨  Global Hotkey")

        hotkey_row = ctk.CTkFrame(scroll, fg_color="transparent")
        hotkey_row.pack(fill="x", pady=(4, 12))

        current_hotkey = self._config.get("hotkey", "<ctrl>+<alt>+t")
        self._hotkey_display_var = tk.StringVar(
            value=HotkeyManager.format_hotkey_display(current_hotkey)
        )
        self._hotkey_entry = ctk.CTkEntry(
            hotkey_row,
            textvariable=self._hotkey_display_var,
            state="readonly",
            fg_color=BG_CARD2,
            border_color=ACCENT_COLOR,
            text_color=ACCENT_COLOR,
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
        )
        self._hotkey_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self._record_btn = ctk.CTkButton(
            hotkey_row,
            text="🔴 Record Hotkey",
            width=140,
            height=40,
            fg_color=ACCENT2_COLOR,
            hover_color="#6020EE",
            command=self._start_hotkey_recording,
        )
        self._record_btn.pack(side="left")

        self._settings_note(
            scroll,
            "Press the button, then press your desired key combination. "
            "Release all keys to confirm."
        )

        # ---- Section: Translation ----
        self._settings_section(scroll, "🌍  Translation")

        lang_row = ctk.CTkFrame(scroll, fg_color="transparent")
        lang_row.pack(fill="x", pady=(4, 6))

        ctk.CTkLabel(
            lang_row,
            text="Target Language:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=160,
            anchor="w",
        ).pack(side="left")

        self._lang_var = tk.StringVar(
            value=self._config.get("target_language", "Arabic")
        )
        lang_menu = ctk.CTkOptionMenu(
            lang_row,
            variable=self._lang_var,
            values=SUPPORTED_LANGUAGES,
            fg_color=BG_CARD2,
            button_color=ACCENT2_COLOR,
            button_hover_color="#6020EE",
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            command=lambda v: self._config.set("target_language", v),
        )
        lang_menu.pack(side="left")

        llm_row = ctk.CTkFrame(scroll, fg_color="transparent")
        llm_row.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(
            llm_row,
            text="LLM Backend:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=160,
            anchor="w",
        ).pack(side="left")

        self._llm_var = tk.StringVar(
            value=self._config.get("selected_llm", "gemini")
        )
        llm_menu = ctk.CTkOptionMenu(
            llm_row,
            variable=self._llm_var,
            values=list(SUPPORTED_LLMS.keys()),
            fg_color=BG_CARD2,
            button_color=ACCENT2_COLOR,
            button_hover_color="#6020EE",
            dropdown_fg_color=BG_CARD,
            text_color=TEXT_PRIMARY,
            command=lambda v: self._config.set("selected_llm", v),
        )
        llm_menu.pack(side="left")

        # ---- Section: API Keys ----
        self._settings_section(scroll, "🔑  API Keys")

        self._build_api_key_row(
            scroll,
            label="Google Gemini API Key:",
            config_key="gemini_api_key",
            placeholder="AIza...",
        )
        self._build_api_key_row(
            scroll,
            label="OpenAI API Key:",
            config_key="openai_api_key",
            placeholder="sk-...",
        )

        # ---- Section: OCR ----
        self._settings_section(scroll, "👁  OCR Settings")

        threshold_row = ctk.CTkFrame(scroll, fg_color="transparent")
        threshold_row.pack(fill="x", pady=(4, 6))

        ctk.CTkLabel(
            threshold_row,
            text="EasyOCR → Tesseract Fallback Threshold:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=300,
            anchor="w",
        ).pack(side="left")

        self._threshold_var = tk.DoubleVar(
            value=self._config.get("ocr_confidence_threshold", 0.6)
        )
        self._threshold_label = ctk.CTkLabel(
            threshold_row,
            text=f"{self._threshold_var.get():.1f}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=ACCENT_COLOR,
            width=40,
        )
        self._threshold_label.pack(side="right")

        threshold_slider = ctk.CTkSlider(
            scroll,
            from_=0.1,
            to=1.0,
            number_of_steps=9,
            variable=self._threshold_var,
            button_color=ACCENT2_COLOR,
            button_hover_color=ACCENT_COLOR,
            progress_color=ACCENT2_COLOR,
            command=self._on_threshold_change,
        )
        threshold_slider.pack(fill="x", pady=(0, 6))

        # Tesseract path
        tess_row = ctk.CTkFrame(scroll, fg_color="transparent")
        tess_row.pack(fill="x", pady=(4, 4))

        ctk.CTkLabel(
            tess_row,
            text="Tesseract Binary Path (optional):",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=240,
            anchor="w",
        ).pack(side="left")

        self._tess_path_var = tk.StringVar(
            value=self._config.get("tesseract_path", "")
        )
        tess_entry = ctk.CTkEntry(
            tess_row,
            textvariable=self._tess_path_var,
            placeholder_text="C:/Program Files/Tesseract-OCR/tesseract.exe",
            fg_color=BG_CARD2,
            border_color=BG_CARD2,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        tess_entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        tess_entry.bind("<FocusOut>", lambda e: self._config.set("tesseract_path", self._tess_path_var.get()))

        # Tesseract status
        tess_available = _is_tesseract_available(self._config.get("tesseract_path", ""))
        tess_status = "✅ Tesseract found" if tess_available else "⚠ Tesseract not found (fallback disabled)"
        ctk.CTkLabel(
            scroll,
            text=tess_status,
            font=ctk.CTkFont(size=9),
            text_color=SUCCESS if tess_available else WARNING,
        ).pack(anchor="w", pady=(0, 6))

        # OCR Language
        ocr_lang_row = ctk.CTkFrame(scroll, fg_color="transparent")
        ocr_lang_row.pack(fill="x", pady=(4, 6))

        ctk.CTkLabel(
            ocr_lang_row,
            text="OCR Language Code:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=240,
            anchor="w",
        ).pack(side="left")

        self._ocr_lang_var = tk.StringVar(
            value=self._config.get("ocr_language", "en")
        )
        ocr_lang_entry = ctk.CTkEntry(
            ocr_lang_row,
            textvariable=self._ocr_lang_var,
            placeholder_text="en",
            fg_color=BG_CARD2,
            border_color=BG_CARD2,
            text_color=TEXT_PRIMARY,
            height=36,
            width=80,
        )
        ocr_lang_entry.pack(side="left", padx=(8, 0))
        ocr_lang_entry.bind("<FocusOut>", lambda e: self._config.set("ocr_language", self._ocr_lang_var.get()))

        self._settings_note(scroll, "EasyOCR language codes: 'en' (English), 'ar' (Arabic), 'fr' (French), etc.")

        # ---- Section: Behaviour ----
        self._settings_section(scroll, "🕹  Behaviour")

        auto_close_row = ctk.CTkFrame(scroll, fg_color="transparent")
        auto_close_row.pack(fill="x", pady=(4, 6))

        ctk.CTkLabel(
            auto_close_row,
            text="Result auto-close (seconds, 0 = never):",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=300,
            anchor="w",
        ).pack(side="left")

        self._auto_close_var = tk.IntVar(
            value=self._config.get("result_auto_close_seconds", 30)
        )
        auto_close_entry = ctk.CTkEntry(
            auto_close_row,
            textvariable=self._auto_close_var,
            fg_color=BG_CARD2,
            border_color=BG_CARD2,
            text_color=TEXT_PRIMARY,
            height=36,
            width=70,
        )
        auto_close_entry.pack(side="left", padx=(8, 0))
        auto_close_entry.bind("<FocusOut>", lambda e: self._save_auto_close())

        auto_save_row = ctk.CTkFrame(scroll, fg_color="transparent")
        auto_save_row.pack(fill="x", pady=(4, 12))

        ctk.CTkLabel(
            auto_save_row,
            text="Auto-save translations to history:",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=300,
            anchor="w",
        ).pack(side="left")

        self._auto_save_var = tk.BooleanVar(
            value=self._config.get("auto_save_history", True)
        )
        ctk.CTkSwitch(
            auto_save_row,
            text="",
            variable=self._auto_save_var,
            onvalue=True,
            offvalue=False,
            button_color=ACCENT2_COLOR,
            button_hover_color=ACCENT_COLOR,
            progress_color=ACCENT2_COLOR,
            command=lambda: self._config.set("auto_save_history", self._auto_save_var.get()),
        ).pack(side="left", padx=(8, 0))

        # ---- Save button ----
        ctk.CTkButton(
            scroll,
            text="💾  Save All Settings",
            fg_color=ACCENT2_COLOR,
            hover_color="#6020EE",
            height=44,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._save_all_settings,
        ).pack(fill="x", pady=(16, 4))

    def _build_api_key_row(self, parent, label: str, config_key: str, placeholder: str) -> None:
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(4, 6))

        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_SECONDARY,
            width=200,
            anchor="w",
        ).pack(side="left")

        var = tk.StringVar(value=self._config.get(config_key, ""))
        entry = ctk.CTkEntry(
            row,
            textvariable=var,
            placeholder_text=placeholder,
            show="•",
            fg_color=BG_CARD2,
            border_color=BG_CARD2,
            text_color=TEXT_PRIMARY,
            height=36,
        )
        entry.pack(side="left", fill="x", expand=True, padx=(8, 8))
        entry.bind("<FocusOut>", lambda e, k=config_key, v=var: self._config.set(k, v.get()))

        # Show/hide toggle
        show_state = {"visible": False}

        def toggle_visibility(e=None, en=entry, st=show_state):
            st["visible"] = not st["visible"]
            en.configure(show="" if st["visible"] else "•")
            eye_btn.configure(text="🙈" if st["visible"] else "👁")

        eye_btn = ctk.CTkButton(
            row,
            text="👁",
            width=36,
            height=36,
            fg_color=BG_CARD2,
            hover_color=BG_DARK,
            command=toggle_visibility,
        )
        eye_btn.pack(side="left")

        # Store var reference
        setattr(self, f"_{config_key}_var", var)

    # ------------------------------------------------------------------
    # Settings helpers
    # ------------------------------------------------------------------

    def _settings_section(self, parent, title: str) -> None:
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=(14, 4))

        ctk.CTkLabel(
            frame,
            text=title,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT_COLOR,
        ).pack(side="left")

        ctk.CTkFrame(frame, fg_color=BG_CARD2, height=1).pack(
            side="left", fill="x", expand=True, padx=(10, 0), pady=6
        )

    def _settings_note(self, parent, text: str) -> None:
        ctk.CTkLabel(
            parent,
            text=f"ℹ  {text}",
            font=ctk.CTkFont(size=9),
            text_color=TEXT_SECONDARY,
            anchor="w",
            wraplength=720,
            justify="left",
        ).pack(fill="x", pady=(0, 4))

    def _on_threshold_change(self, value) -> None:
        self._threshold_label.configure(text=f"{value:.1f}")
        self._config.set("ocr_confidence_threshold", float(value))

    def _save_auto_close(self) -> None:
        try:
            self._config.set("result_auto_close_seconds", int(self._auto_close_var.get()))
        except Exception:
            pass

    def _save_all_settings(self) -> None:
        # Persist all settings that might not be auto-saved
        self._config.set("target_language", self._lang_var.get())
        self._config.set("selected_llm", self._llm_var.get())
        self._config.set("auto_save_history", self._auto_save_var.get())
        try:
            self._config.set("result_auto_close_seconds", int(self._auto_close_var.get()))
        except Exception:
            pass
        self._config.save()

        # Flash feedback
        mb.showinfo("Settings Saved", "All settings have been saved successfully.")

    # ------------------------------------------------------------------
    # Hotkey Recording
    # ------------------------------------------------------------------

    def _start_hotkey_recording(self) -> None:
        self._record_btn.configure(
            text="⏺  Listening... (press your combo)",
            fg_color=ERROR,
        )
        self._hotkey_display_var.set("...")
        self._hotkey_mgr.start_recording(on_done=self._on_hotkey_recorded)

    def _on_hotkey_recorded(self, hotkey_str: str) -> None:
        # Called back on main thread via root.after()
        self._config.set("hotkey", hotkey_str)
        self._hotkey_mgr.update_hotkey(hotkey_str)

        display = HotkeyManager.format_hotkey_display(hotkey_str)
        self._hotkey_display_var.set(display)
        self._hotkey_display_label.configure(text=f"Hotkey: {display}")
        self._hotkey_hint_label.configure(
            text=f"or press\n{display}"
        )

        self._record_btn.configure(
            text="🔴 Record Hotkey",
            fg_color=ACCENT2_COLOR,
        )

    # ------------------------------------------------------------------
    # Capture Pipeline
    # ------------------------------------------------------------------

    def _on_hotkey_triggered(self) -> None:
        """Called when hotkey fires OR user clicks the Capture button."""
        self._set_status("Waiting for selection...", WARNING)
        overlay = RegionOverlay(
            on_capture=self._on_region_selected,
            on_cancel=self._on_capture_cancelled,
            root=self._root,          # pass root for proper Toplevel ownership
        )
        overlay.show()

    def _on_capture_cancelled(self) -> None:
        self._set_status("Capture cancelled", TEXT_SECONDARY)
        self._root.after(2000, lambda: self._set_status("Ready  ✓", SUCCESS))

    def _on_region_selected(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Called by the overlay after the user releases the mouse."""
        self._set_status("Capturing & processing...", ACCENT_COLOR)

        # Show loading popup
        self._loading_win = LoadingWindow(self._root, "Running OCR + Translation")
        self._loading_win.show()

        # Run pipeline in background thread
        thread = threading.Thread(
            target=self._pipeline_worker,
            args=(x1, y1, x2, y2),
            daemon=True,
        )
        thread.start()

    def _pipeline_worker(self, x1: int, y1: int, x2: int, y2: int) -> None:
        """Background worker: capture → OCR → translate → update UI."""
        try:
            # 1. Screenshot
            img = capture_region(x1, y1, x2, y2)
            self._last_image = img

            # 2. OCR
            ocr_result = extract_text(
                img,
                confidence_threshold=self._config.get("ocr_confidence_threshold", 0.6),
                ocr_language=self._config.get("ocr_language", "en"),
                tesseract_path=self._config.get("tesseract_path", ""),
            )
            self._last_ocr_result = ocr_result

            if not ocr_result.text:
                self._root.after(0, lambda: self._pipeline_done(
                    img, ocr_result, None,
                    error="No text detected in the selected region. Try selecting a larger area."
                ))
                return

            # 3. Translate
            api_keys = {
                "gemini": self._config.get("gemini_api_key", ""),
                "openai": self._config.get("openai_api_key", ""),
            }
            translation = translate(
                text=ocr_result.text,
                target_language=self._config.get("target_language", "Arabic"),
                selected_llm=self._config.get("selected_llm", "gemini"),
                api_keys=api_keys,
            )
            self._last_translation = translation

            self._root.after(0, lambda: self._pipeline_done(img, ocr_result, translation))

        except Exception as e:
            self._root.after(0, lambda: self._pipeline_done(
                None, None, None, error=str(e)
            ))

    def _pipeline_done(
        self,
        img,
        ocr_result,
        translation,
        error: Optional[str] = None,
    ) -> None:
        """Called on main thread when the background worker finishes."""
        # Close loading window
        if self._loading_win:
            self._loading_win.close()
            self._loading_win = None

        # Close old result window if open
        if self._result_win:
            self._result_win.close()
            self._result_win = None

        if error:
            self._set_status(f"Error: {error[:60]}", ERROR)
        else:
            self._set_status(
                f"Done — {ocr_result.engine} ({int(ocr_result.confidence*100)}%)",
                SUCCESS,
            )

        # Update image preview
        if img:
            self._update_preview(img)

        # Update OCR preview label
        if ocr_result and ocr_result.text:
            preview_text = ocr_result.text[:120] + ("..." if len(ocr_result.text) > 120 else "")
            self._ocr_preview_label.configure(text=preview_text)

        # Show result popup
        original = (ocr_result.text if ocr_result else "") or ""
        translated = ""
        llm = self._config.get("selected_llm", "gemini")
        ocr_eng = (ocr_result.engine if ocr_result else "") or ""
        confidence = (ocr_result.confidence if ocr_result else 0.0) or 0.0

        if translation and translation.success:
            translated = translation.translated_text
        elif translation and translation.error:
            error = error or translation.error

        self._result_win = ResultWindow(
            root=self._root,
            original_text=original,
            translated_text=translated,
            target_language=self._config.get("target_language", "Arabic"),
            llm_used=llm,
            ocr_engine=ocr_eng,
            confidence=confidence,
            on_save=lambda: self._save_result_to_history(ocr_result, translation),
            auto_close_seconds=self._config.get("result_auto_close_seconds", 30),
            error=error,
        )

        # Auto-save if enabled
        if (
            self._config.get("auto_save_history", True)
            and ocr_result
            and translation
            and translation.success
            and not error
        ):
            self._save_result_to_history(ocr_result, translation)

    def _save_result_to_history(self, ocr_result, translation) -> None:
        if not ocr_result or not translation:
            return
        try:
            self._history.add_entry(
                original_text=ocr_result.text,
                translated_text=translation.translated_text,
                target_language=self._config.get("target_language", "Arabic"),
                llm_used=translation.llm_used,
                ocr_engine=ocr_result.engine,
                confidence=ocr_result.confidence,
            )
        except Exception as e:
            print(f"[MainWindow] Failed to save history: {e}")

    # ------------------------------------------------------------------
    # Image preview
    # ------------------------------------------------------------------

    def _update_preview(self, img: Image.Image) -> None:
        try:
            canvas = self._preview_canvas
            canvas_w = canvas.winfo_width() or 760
            canvas_h = canvas.winfo_height() or 180

            # Fit image within canvas preserving aspect ratio
            img_copy = img.copy()
            img_copy.thumbnail((canvas_w - 20, canvas_h - 20), Image.LANCZOS)

            photo = ImageTk.PhotoImage(img_copy)
            canvas.delete("all")
            cx = canvas_w // 2
            cy = canvas_h // 2
            canvas.create_image(cx, cy, image=photo, anchor="center")
            canvas._photo_ref = photo   # prevent GC
        except Exception as e:
            print(f"[MainWindow] Preview error: {e}")

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def _set_status(self, text: str, color: str = SUCCESS) -> None:
        self._status_var.set(text)
        self._status_label.configure(text_color=color)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _on_close(self) -> None:
        self._hotkey_mgr.stop()
        self._root.destroy()
