"""
overlay.py
----------
Fullscreen semi-transparent overlay for selecting a screen region.

The user clicks and drags to draw a rectangle over the text they want
to translate. On mouse release the selected bounding box is passed to
the `on_capture` callback and the overlay closes.

Press ESC to cancel without capturing.
"""

import tkinter as tk
from typing import Callable, Optional


class RegionOverlay:
    """
    Transparent fullscreen window that lets the user drag-select a region.

    Usage
    -----
    def on_captured(x1, y1, x2, y2):
        # do OCR on the region
        ...

    overlay = RegionOverlay(on_capture=on_captured, on_cancel=lambda: ...)
    overlay.show()
    """

    # Visual constants
    OVERLAY_ALPHA = 0.45
    SELECTION_COLOR = "#00D9FF"          # Bright cyan selection border
    SELECTION_FILL = "#00D9FF"           # Selection fill (low opacity via stipple)
    BORDER_WIDTH = 2
    INSTRUCTION_TEXT = "✛  Drag to select text  |  ESC to cancel"
    INSTRUCTION_FONT = ("Segoe UI", 14, "bold")
    INSTRUCTION_BG = "#0D0D1A"
    INSTRUCTION_FG = "#00D9FF"
    DIM_COLOR = "#0D0D1A"                # Dark overlay tint

    def __init__(
        self,
        on_capture: Callable[[int, int, int, int], None],
        on_cancel: Optional[Callable] = None,
        root: Optional[tk.Tk] = None,
    ):
        self._on_capture = on_capture
        self._on_cancel = on_cancel
        self._root = root          # parent window for Toplevel

        self._start_x: Optional[int] = None
        self._start_y: Optional[int] = None
        self._rect_id: Optional[int] = None
        self._win: Optional[tk.Toplevel] = None
        self._canvas: Optional[tk.Canvas] = None

    # ------------------------------------------------------------------
    # Public
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Open the overlay window. Does NOT block."""
        # Use root as parent if available so Toplevel is properly owned
        self._win = tk.Toplevel(self._root) if self._root else tk.Toplevel()
        self._setup_window()
        self._setup_canvas()
        self._bind_events()
        self._win.focus_force()
        # NOTE: do NOT call grab_set() — it can block pynput events on Windows
        # and prevents the user from interacting with overlapping windows.

    def close(self) -> None:
        """Destroy the overlay window."""
        if self._win:
            try:
                self._win.destroy()
            except tk.TclError:
                pass
            self._win = None

    # ------------------------------------------------------------------
    # Window setup
    # ------------------------------------------------------------------

    def _setup_window(self) -> None:
        win = self._win
        win.title("Select Region")
        win.attributes("-fullscreen", True)
        win.attributes("-topmost", True)
        win.attributes("-alpha", self.OVERLAY_ALPHA)
        win.configure(bg=self.DIM_COLOR)
        win.config(cursor="crosshair")
        # Remove window decorations
        win.overrideredirect(True)

    def _setup_canvas(self) -> None:
        win = self._win
        screen_w = win.winfo_screenwidth()
        screen_h = win.winfo_screenheight()

        self._canvas = tk.Canvas(
            win,
            width=screen_w,
            height=screen_h,
            bg=self.DIM_COLOR,
            highlightthickness=0,
            cursor="crosshair",
        )
        self._canvas.pack(fill="both", expand=True)

        # Instruction label at top centre — responsive to screen width
        half_w = min(260, screen_w // 2 - 20)   # never wider than screen
        self._canvas.create_rectangle(
            screen_w // 2 - half_w, 18,
            screen_w // 2 + half_w, 52,
            fill=self.INSTRUCTION_BG,
            outline=self.SELECTION_COLOR,
            width=1,
        )
        self._canvas.create_text(
            screen_w // 2, 35,
            text=self.INSTRUCTION_TEXT,
            font=self.INSTRUCTION_FONT,
            fill=self.INSTRUCTION_FG,
        )

    # ------------------------------------------------------------------
    # Event bindings
    # ------------------------------------------------------------------

    def _bind_events(self) -> None:
        self._canvas.bind("<ButtonPress-1>",   self._on_press)
        self._canvas.bind("<B1-Motion>",        self._on_drag)
        self._canvas.bind("<ButtonRelease-1>", self._on_release)
        self._win.bind("<Escape>",              self._on_escape)

    def _on_press(self, event: tk.Event) -> None:
        self._start_x = event.x
        self._start_y = event.y
        # Remove previous rectangle if any
        if self._rect_id:
            self._canvas.delete(self._rect_id)
            self._rect_id = None

    def _on_drag(self, event: tk.Event) -> None:
        if self._start_x is None:
            return
        if self._rect_id:
            self._canvas.delete(self._rect_id)

        # Draw selection rectangle with dashed bright border
        self._rect_id = self._canvas.create_rectangle(
            self._start_x, self._start_y,
            event.x, event.y,
            outline=self.SELECTION_COLOR,
            width=self.BORDER_WIDTH,
            dash=(6, 3),
            fill=self.SELECTION_FILL,
            stipple="gray12",           # Very light transparent fill
        )

    def _on_release(self, event: tk.Event) -> None:
        if self._start_x is None:
            return

        x1, y1 = self._start_x, self._start_y
        x2, y2 = event.x, event.y

        self.close()

        # Ignore tiny accidental clicks (< 10 × 10 px)
        if abs(x2 - x1) < 10 or abs(y2 - y1) < 10:
            if self._on_cancel:
                self._on_cancel()
            return

        # Normalise coordinates
        left   = min(x1, x2)
        top    = min(y1, y2)
        right  = max(x1, x2)
        bottom = max(y1, y2)

        self._on_capture(left, top, right, bottom)

    def _on_escape(self, event: tk.Event) -> None:
        self.close()
        if self._on_cancel:
            self._on_cancel()
