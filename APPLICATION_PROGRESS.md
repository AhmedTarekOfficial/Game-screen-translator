# Game Screen Translator — Application Progress

> Task tracking document. Updated in real-time during development.
> Status: 🟡 In Progress

---

## Legend
- `[x]` — Completed
- `[/]` — In Progress
- `[ ]` — Pending

---

## 📁 Project Setup

| Status | Task | Description |
|---|---|---|
| [x] | Create directory structure | `app/ui`, `app/core`, `app/data`, `app/utils` |
| [x] | `requirements.txt` | All Python dependencies |
| [x] | `ARCHITECTURE.md` | Living architecture document |
| [x] | `APPLICATION_PROGRESS.md` | This file |
| [x] | `.gitignore` | Python + IDE ignores |

---

## 🗂️ Data Layer

| Status | Task | Description |
|---|---|---|
| [x] | `app/data/config_manager.py` | Reads/writes `config.json`. Manages hotkey, API keys, target language, LLM selection, OCR threshold, auto-save, auto-close timer |
| [x] | `app/data/history_manager.py` | SQLite CRUD for translation history. Methods: add_entry, get_all, search, delete_entry, export_csv |

---

## ⚙️ Core Engine

| Status | Task | Description |
|---|---|---|
| [x] | `app/core/hotkey_manager.py` | pynput GlobalHotKeys in daemon thread. Supports dynamic hotkey re-registration without restart. Callback marshalled to Tkinter main thread via `root.after()` |
| [x] | `app/core/screenshot.py` | Uses `mss` to capture a bounding box region. Returns PIL Image. Handles Windows DPI scaling |
| [x] | `app/core/ocr_engine.py` | EasyOCR primary + pytesseract fallback. Preprocessing pipeline: grayscale, contrast, 2x upscale. Confidence threshold configurable |
| [x] | `app/core/translator.py` | Multi-LLM client. Gemini (gemini-1.5-flash) default. OpenAI (gpt-4o-mini) supported. Context-aware game translation prompt |

---

## 🎨 UI Layer

| Status | Task | Description |
|---|---|---|
| [x] | `app/ui/overlay.py` | Fullscreen semi-transparent region selector. Mouse drag draws selection rectangle. ESC cancels. Captures coordinates on release |
| [x] | `app/ui/result_window.py` | Floating always-on-top popup. Shows original + translated text. Copy to clipboard, Save to history, Close buttons. Draggable title bar. Auto-close timer |
| [x] | `app/ui/main_window.py` | Main 3-tab window: Translator (status + preview), History (searchable list), Settings (hotkey, API keys, language, LLM, OCR threshold) |

---

## 🚀 Entry Point

| Status | Task | Description |
|---|---|---|
| [x] | `main.py` | Initializes all managers, starts hotkey listener daemon, launches CustomTkinter main loop |

---

## 🔗 Git & GitHub

| Status | Task | Description |
|---|---|---|
| [x] | Initial commit | Project structure + docs |
| [x] | Core modules push | Data + Core layers complete |
| [x] | UI modules push | All UI layers complete |
| [x] | Final push | Full app with tests |

---

## 🐛 Known Issues / TODOs
- Tesseract binary must be installed separately by user (documented in README)
- EasyOCR first load is slow (~5s) — show loading indicator
- Overlay may not work in exclusive fullscreen games (borderless/windowed recommended)
