"""
screenshot.py
-------------
Captures a rectangular region of the screen using mss.
Returns a PIL Image ready for OCR processing.

Handles Windows DPI scaling via ctypes so coordinates
match actual screen pixels regardless of display scaling.
"""

import ctypes
import sys
from typing import Tuple

import mss
import mss.tools
from PIL import Image


def _get_dpi_scale() -> float:
    """
    Return the DPI scaling factor on Windows.
    On non-Windows systems, returns 1.0.
    """
    if sys.platform != "win32":
        return 1.0
    try:
        # SetProcessDpiAwareness(2) = Per-monitor DPI aware
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    try:
        hdc = ctypes.windll.user32.GetDC(0)
        dpi = ctypes.windll.gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
        ctypes.windll.user32.ReleaseDC(0, hdc)
        return dpi / 96.0
    except Exception:
        return 1.0


# Cache DPI scale at module load time
DPI_SCALE = _get_dpi_scale()


def capture_region(x1: int, y1: int, x2: int, y2: int) -> Image.Image:
    """
    Capture a screen region defined by the top-left (x1, y1) and
    bottom-right (x2, y2) corners (in logical/screen-coordinate pixels).

    Parameters
    ----------
    x1, y1 : int
        Top-left corner of the region.
    x2, y2 : int
        Bottom-right corner of the region.

    Returns
    -------
    PIL.Image.Image
        The captured screen region as an RGB PIL Image.

    Raises
    ------
    ValueError
        If the region has zero or negative dimensions.
    """
    # Normalise: ensure x1 < x2 and y1 < y2
    left   = min(x1, x2)
    top    = min(y1, y2)
    right  = max(x1, x2)
    bottom = max(y1, y2)

    width  = right - left
    height = bottom - top

    if width <= 0 or height <= 0:
        raise ValueError(
            f"Invalid capture region: ({left},{top}) → ({right},{bottom}). "
            "Width and height must be positive."
        )

    monitor = {
        "left":   left,
        "top":    top,
        "width":  width,
        "height": height,
    }

    with mss.mss() as sct:
        screenshot = sct.grab(monitor)
        # mss returns BGRA; convert to RGB PIL Image
        img = Image.frombytes(
            "RGB",
            (screenshot.width, screenshot.height),
            screenshot.rgb,
        )

    return img


def capture_full_screen(monitor_index: int = 1) -> Image.Image:
    """
    Capture the entire screen (or a specific monitor).

    Parameters
    ----------
    monitor_index : int
        1-indexed monitor number. 0 = all monitors combined.

    Returns
    -------
    PIL.Image.Image
    """
    with mss.mss() as sct:
        monitor = sct.monitors[monitor_index]
        screenshot = sct.grab(monitor)
        img = Image.frombytes(
            "RGB",
            (screenshot.width, screenshot.height),
            screenshot.rgb,
        )
    return img
