"""
config_manager.py
-----------------
Manages reading and writing the application configuration from/to config.json.
Provides default values if the config file does not exist yet.
"""

import json
import os
from pathlib import Path


# Path to config file (sits next to main.py in the project root)
CONFIG_PATH = Path(__file__).resolve().parents[2] / "config.json"

DEFAULT_CONFIG = {
    "hotkey": "<ctrl>+<alt>+t",
    "target_language": "Arabic",
    "selected_llm": "gemini",
    "gemini_api_key": "",
    "openai_api_key": "",
    "ocr_confidence_threshold": 0.6,
    "auto_save_history": True,
    "result_auto_close_seconds": 30,
    "theme": "dark",
    "tesseract_path": "",          # e.g. C:/Program Files/Tesseract-OCR/tesseract.exe
    "ocr_language": "en",          # EasyOCR language code
}


class ConfigManager:
    """
    Singleton-style config manager.
    Call ConfigManager() anywhere — it loads config.json on first access.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._config = {}
            cls._instance._loaded = False
        return cls._instance

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self) -> dict:
        """Load config from disk. Creates default config.json if not found."""
        if CONFIG_PATH.exists():
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                # Merge with defaults to handle missing keys from older versions
                self._config = {**DEFAULT_CONFIG, **loaded}
            except (json.JSONDecodeError, OSError):
                self._config = dict(DEFAULT_CONFIG)
        else:
            self._config = dict(DEFAULT_CONFIG)
            self.save()
        self._loaded = True
        return self._config

    def save(self) -> None:
        """Persist current config to disk."""
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
        except OSError as e:
            print(f"[ConfigManager] Failed to save config: {e}")

    def get(self, key: str, default=None):
        """Get a config value by key."""
        if not self._loaded:
            self.load()
        return self._config.get(key, default)

    def set(self, key: str, value) -> None:
        """Set a config value and immediately persist to disk."""
        if not self._loaded:
            self.load()
        self._config[key] = value
        self.save()

    def get_all(self) -> dict:
        """Return a copy of the entire config dict."""
        if not self._loaded:
            self.load()
        return dict(self._config)

    def reset_to_defaults(self) -> None:
        """Reset all settings to factory defaults."""
        self._config = dict(DEFAULT_CONFIG)
        self.save()
