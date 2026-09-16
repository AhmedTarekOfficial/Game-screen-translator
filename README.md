# Game Screen Translator 🎮

A Python desktop application that lets you **capture any text on screen** while gaming, **extract it with OCR**, and **translate it with an LLM** — all triggered by a customizable global hotkey.

---

## ✨ Features

- **Global Hotkey** — Works even when a game is in focus (customizable, recordable from keyboard)
- **Region Selector** — Drag-select any area of the screen with a transparent overlay
- **Dual OCR Engine** — EasyOCR (primary) + Tesseract (fallback) for maximum accuracy
- **Multi-LLM Translation** — Google Gemini (default) + OpenAI support
- **Dark Mode UI** — Modern CustomTkinter interface with glassmorphism styling
- **Translation History** — SQLite-backed history with search and CSV export
- **Always-on-top Result** — Floating popup with copy-to-clipboard and auto-close timer
- **Persistent Settings** — API keys, hotkeys, language preferences all saved locally

---

## 🚀 Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

> **Optional:** For Tesseract OCR fallback, install [Tesseract](https://github.com/tesseract-ocr/tesseract/releases) and set its path in Settings.

### 2. Run the App

```bash
python main.py
```

### 3. Configure

1. Go to the **Settings** tab
2. Add your **Gemini API Key** (get one at [aistudio.google.com](https://aistudio.google.com))
3. Set your **Target Language** (default: Arabic)
4. Set your preferred **Hotkey** (default: `Ctrl + Alt + T`)

### 4. Use While Gaming

1. Press your hotkey (default: `Ctrl + Alt + T`) while in-game
2. Drag to select the text region
3. The translation appears in a floating popup

---

## 📁 Project Structure

```
game_translator/
├── main.py                    # Entry point
├── requirements.txt
├── ARCHITECTURE.md            # Full technical architecture
├── APPLICATION_PROGRESS.md    # Development task tracker
└── app/
    ├── ui/
    │   ├── main_window.py     # Main 3-tab window (Translator, History, Settings)
    │   ├── overlay.py         # Fullscreen region selector overlay
    │   └── result_window.py   # Floating result popup
    ├── core/
    │   ├── hotkey_manager.py  # Global hotkey listener (pynput)
    │   ├── screenshot.py      # Screen capture (mss)
    │   ├── ocr_engine.py      # EasyOCR + Tesseract pipeline
    │   └── translator.py      # Gemini + OpenAI clients
    ├── data/
    │   ├── config_manager.py  # JSON config persistence
    │   └── history_manager.py # SQLite history CRUD
    └── utils/
        └── helpers.py
```

---

## ⚙️ Configuration (`config.json`)

Auto-created on first run. Key settings:

| Key | Default | Description |
|---|---|---|
| `hotkey` | `<ctrl>+<alt>+t` | Global trigger hotkey |
| `target_language` | `Arabic` | Translation target |
| `selected_llm` | `gemini` | LLM backend |
| `gemini_api_key` | `""` | Your Gemini API key |
| `openai_api_key` | `""` | Your OpenAI API key |
| `ocr_confidence_threshold` | `0.6` | EasyOCR → Tesseract fallback threshold |
| `result_auto_close_seconds` | `30` | Auto-close popup (0 = never) |

---

## 📋 Requirements

- Python 3.9+
- Windows 10/11 (primary target; Linux/macOS may work with adjustments)
- Internet connection (for LLM translation)

---

## 🤖 Supported LLMs

| LLM | Model | Notes |
|---|---|---|
| Google Gemini | gemini-3.6-flash | Default, free tier available |
| OpenAI | gpt-4o-mini | Requires paid API |

---

## 📝 Notes

- The overlay works best in **borderless windowed** or **windowed** game mode
- EasyOCR model loads ~5 seconds on first run (warm-up happens at startup)
- All data is stored locally — no data is sent anywhere except to your chosen LLM API
