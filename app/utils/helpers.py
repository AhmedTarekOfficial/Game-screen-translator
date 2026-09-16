"""
helpers.py
----------
Shared utility functions used across the application.
"""

import sys
from pathlib import Path


def get_project_root() -> Path:
    """Return the absolute path to the project root directory."""
    return Path(__file__).resolve().parents[2]


def resource_path(relative_path: str) -> Path:
    """
    Get absolute path to a resource file.
    Works for both development and PyInstaller-frozen builds.
    """
    if hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return get_project_root() / relative_path


def truncate_text(text: str, max_chars: int = 100) -> str:
    """Truncate text to max_chars and append '...' if needed."""
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "..."


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a float value within [min_val, max_val]."""
    return max(min_val, min(max_val, value))
