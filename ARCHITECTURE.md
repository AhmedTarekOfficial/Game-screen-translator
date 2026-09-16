# Game Screen Translator — Architecture Document

> **Living Document** — Updated continuously during development.  
> Last Updated: 2026-09-16

---

## 1. Project Overview

**Game Screen Translator** is a Python desktop application that allows gamers to:
1. Press a global hotkey (even while in-game, full-screen)
2. Draw a rectangle over any on-screen text
3. Extract that text via OCR (EasyOCR primary, Tesseract fallback)
4. Send it to an LLM (Gemini default, OpenAI supported) for context-aware translation
5. View the result in a floating, always-on-top dark-mode popup

---

## 2. Directory Structure

```
game_translator/
├── main.py                        # Entry point
├── requirements.txt               # Python dependencies
├── config.json                    # User config (auto-created on first run)
├── history.db                     # SQLite history (auto-created on first run)
├── ARCHITECTURE.md                # This file
├── APPLICATION_PROGRESS.md        # Task tracking
└── app/
    ├── __init__.py
    ├── ui/
    │   ├── __init__.py
    │   ├── main_window.py         # Main CustomTkinter app window
    │   ├── overlay.py             # Transparent fullscreen region selector
    │   └── result_window.py       # Floating translation result popup
    ├── core/
    │   ├── __init__.py
    │   ├── hotkey_manager.py      # pynput global hotkey listener
    │   ├── screenshot.py          # mss screen capture module
    │   ├── ocr_engine.py          # EasyOCR + Tesseract fallback
    │   └── translator.py          # Multi-LLM translation client
    ├── data/
    │   ├── __init__.py
    │   ├── config_manager.py      # config.json read/write
    │   └── history_manager.py     # SQLite CRUD
    └── utils/
        ├── __init__.py
        └── helpers.py             # Shared utilities
```

---

## 3. Module Descriptions

### 3.1 `main.py` — Entry Point
- Initializes `ConfigManager` (creates `config.json` if missing)
- Initializes `HistoryManager` (creates `history.db` if missing)
- Starts `HotkeyManager` as a daemon thread
- Launches `MainWindow` (CustomTkinter event loop)

**Key flow:**
```
main.py
  └─► ConfigManager.load()
  └─► HistoryManager.init_db()
  └─► HotkeyManager.start()   ← background thread
  └─► MainWindow.run()        ← blocks (tkinter mainloop)
```

---

### 3.2 `app/core/hotkey_manager.py`
**Purpose:** Listen for the user's configured global hotkey, fire a callback even while another app (game) is in focus.

**Key Details:**
- Uses `pynput.keyboard.GlobalHotKeys` in a **daemon thread**
- Reads hotkey string from `ConfigManager` (e.g. `"<ctrl>+<alt>+t"`)
- On hotkey press → calls `on_trigger_callback()` on main thread via `root.after(0, callback)`
- Supports **dynamic restart**: when user changes hotkey in settings, old listener is `.stop()`ped and a new one is created
- Hotkey recording: uses a raw `pynput.keyboard.Listener` in capture mode to record key combo

**Thread Safety:** All UI calls are marshalled back to the Tkinter main thread using `root.after()`.

---

### 3.3 `app/core/screenshot.py`
**Purpose:** Capture a region of the screen given pixel coordinates.

**Key Details:**
- Uses `mss` (faster than Pillow's ImageGrab, works on multi-monitor)
- Input: `(x1, y1, x2, y2)` bounding box in screen pixels
- Output: `PIL.Image` object
- DPI-awareness: accounts for Windows DPI scaling via `ctypes`

---

### 3.4 `app/core/ocr_engine.py`
**Purpose:** Extract text from a PIL Image.

**OCR Pipeline:**
```
PIL Image
  └─► Preprocessing (grayscale, contrast boost, resize 2x)
  └─► EasyOCR.readtext()           ← Primary engine
      └─► If confidence < 0.6 OR text is empty:
          └─► pytesseract.image_to_string()  ← Fallback engine
  └─► Return: raw_text (string)
```

**Key Details:**
- EasyOCR initialized once at startup (lazy-loaded to avoid slow import)
- Language: auto-detected or set to English for game text
- Tesseract requires separate system install (checked at startup, warning shown if missing)
- Confidence threshold for fallback: configurable (default 0.6)

---

### 3.5 `app/core/translator.py`
**Purpose:** Send extracted text to an LLM and return a translated string.

**Supported LLMs:**
| LLM | API Key Config Key | Model Used |
|---|---|---|
| Google Gemini | `gemini_api_key` | `gemini-1.5-flash` |
| OpenAI | `openai_api_key` | `gpt-4o-mini` |

**Translation Prompt:**
```
You are a professional game translator. 
Translate the following in-game text to {target_language}.
Preserve the tone, context, and game-specific terms.
Return only the translation, no explanations.

Text: {ocr_text}
```

**Key Details:**
- Async-compatible (uses threading to not block UI during API call)
- Error handling: network errors, quota exceeded, invalid API key → shown in result window
- Streaming not used (wait for full response)

---

### 3.6 `app/ui/main_window.py`
**Purpose:** Main application window with 3 tabs.

**Tabs:**
1. **Translator** — Status indicator, last captured image preview, trigger button (alternative to hotkey)
2. **History** — Searchable list of past translations with original/translated text
3. **Settings** — Hotkey recorder, LLM selector, API keys, target language, OCR confidence threshold

**Window Behavior:**
- Minimizes to system tray when closed (stays running in background)
- Reopens from tray icon
- Always uses dark theme (`customtkinter.set_appearance_mode("dark")`)

---

### 3.7 `app/ui/overlay.py`
**Purpose:** Fullscreen transparent window for selecting screen region.

**Behavior:**
- Opens as a `Toplevel` over all windows (including games in borderless/windowed mode)
- Semi-transparent dark overlay (`alpha=0.35`)
- Mouse drag draws a bright rectangle (selection box)
- On `ButtonRelease`: records coordinates → triggers screenshot → closes overlay
- `ESC` key → cancels and closes overlay
- Shows instruction text: "Drag to select text area | ESC to cancel"

---

### 3.8 `app/ui/result_window.py`
**Purpose:** Floating popup showing translation result.

**Layout:**
```
┌─────────────────────────────────┐
│  🎮 Game Translator             │  ← header
├─────────────────────────────────┤
│  Original Text:                 │
│  [detected text box]            │
├─────────────────────────────────┤
│  Translation (Arabic):          │
│  [translated text box]          │
├─────────────────────────────────┤
│  [📋 Copy]  [💾 Save]  [✕ Close]│
└─────────────────────────────────┘
```

**Behavior:**
- Always on top (`wm_attributes("-topmost", True)`)
- Draggable (click and drag title bar)
- Auto-fades after 30 seconds (configurable)
- "Save" button saves to history DB

---

### 3.9 `app/data/config_manager.py`
**Purpose:** Read/write `config.json` in the project root.

**Config Schema:**
```json
{
  "hotkey": "<ctrl>+<alt>+t",
  "target_language": "Arabic",
  "selected_llm": "gemini",
  "gemini_api_key": "...",
  "openai_api_key": "",
  "ocr_confidence_threshold": 0.6,
  "auto_save_history": true,
  "result_auto_close_seconds": 30,
  "theme": "dark"
}
```

---

### 3.10 `app/data/history_manager.py`
**Purpose:** SQLite CRUD for translation history.

**DB Schema:**
```sql
CREATE TABLE history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    original_text TEXT NOT NULL,
    translated_text TEXT NOT NULL,
    source_detected TEXT,
    target_language TEXT,
    llm_used TEXT,
    ocr_engine TEXT,
    confidence REAL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Methods:**
- `add_entry(...)` — Insert new record
- `get_all(limit=100)` — Fetch recent entries
- `search(query)` — Full-text search on original/translated
- `delete_entry(id)` — Remove single record
- `export_csv(path)` — Export all to CSV

---

## 4. Data Flow (Full Pipeline)

```
User presses hotkey
    │
    ▼
HotkeyManager.on_trigger()
    │
    ▼
overlay.py opens (fullscreen transparent window)
    │
User drags mouse to select region
    │
    ▼
screenshot.py captures (x1,y1,x2,y2) → PIL Image
    │
    ▼
ocr_engine.py:
    ├─► EasyOCR.readtext(image)
    └─► [fallback] pytesseract(image)  if confidence < 0.6
    │
    ▼
translator.py:
    └─► LLM API call (Gemini/OpenAI) with context prompt
    │
    ▼
result_window.py shows popup with:
    ├─► Original text
    └─► Translated text
    │
[Optional] User clicks "Save" → history_manager.add_entry()
```

---

## 5. Threading Model

| Thread | Purpose |
|---|---|
| Main thread | Tkinter event loop (all UI updates) |
| HotkeyManager thread | pynput listener (daemon thread) |
| OCR + Translation thread | Background worker thread (avoids UI freeze) |

All cross-thread communication to UI uses `root.after(0, callback)`.

---

## 6. Dependencies

| Package | Version | Purpose |
|---|---|---|
| `customtkinter` | ≥5.2.2 | Modern dark-mode GUI |
| `pillow` | ≥10.0.0 | Image processing |
| `mss` | ≥9.0.1 | Fast screen capture |
| `easyocr` | ≥1.7.1 | Primary OCR engine |
| `pytesseract` | ≥0.3.10 | Fallback OCR engine |
| `pynput` | ≥1.7.6 | Global hotkey listener |
| `google-generativeai` | ≥0.7.0 | Gemini LLM client |
| `openai` | ≥1.30.0 | OpenAI LLM client |

**System Requirements:**
- Python 3.9+
- Tesseract OCR binary (optional, for fallback): https://github.com/tesseract-ocr/tesseract
- Windows 10/11 (primary target)
