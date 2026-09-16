"""
main.py
-------
Game Screen Translator — Entry Point

Startup sequence:
  1. Check Python version
  2. Load configuration
  3. Initialise history database
  4. Launch the main GUI window (which starts the hotkey listener internally)

Usage:
  python main.py
"""

import sys
import os

# ---------------------------------------------------------------------------
# Python version guard
# ---------------------------------------------------------------------------
if sys.version_info < (3, 9):
    print("ERROR: Python 3.9 or higher is required.")
    sys.exit(1)

# ---------------------------------------------------------------------------
# Windows DPI awareness — must be set BEFORE any UI code imports
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    try:
        import ctypes
        ctypes.windll.shcore.SetProcessDpiAwareness(2)   # Per-monitor DPI aware
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
from app.data.config_manager import ConfigManager
from app.data.history_manager import HistoryManager
from app.ui.main_window import MainWindow


def main() -> None:
    print("=" * 55)
    print("  🎮  Game Screen Translator")
    print("  Version 1.0  |  Python", sys.version.split()[0])
    print("=" * 55)

    # 1. Load / create config
    config = ConfigManager()
    config.load()
    print(f"[Init] Config loaded  — hotkey: {config.get('hotkey')}")
    print(f"[Init] Target language: {config.get('target_language')}")
    print(f"[Init] LLM: {config.get('selected_llm')}")

    # 2. Initialise history DB
    history = HistoryManager()
    history.init_db()
    count = history.get_count()
    print(f"[Init] History DB ready — {count} entries")

    # 3. Launch main window (blocking until user closes)
    print("[Init] Launching GUI...")
    window = MainWindow()
    window.run()

    print("[Exit] Application closed.")


if __name__ == "__main__":
    main()
