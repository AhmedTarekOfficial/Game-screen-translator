"""
hotkey_manager.py
-----------------
Manages the global keyboard hotkey listener using pynput.
The listener runs in a daemon background thread so it captures
key combinations even when a game window is in focus.

Features:
- Dynamic hotkey re-registration (no app restart needed)
- Hotkey recording (capture any key combo from the keyboard)
- Thread-safe callback to Tkinter main thread via root.after()
"""

import threading
from typing import Callable, Optional

from pynput import keyboard


class HotkeyManager:
    """
    Wraps pynput.keyboard.GlobalHotKeys to provide:
      - Background hotkey listening
      - Dynamic restart when hotkey changes
      - Hotkey recording mode
    """

    def __init__(self, hotkey_str: str, on_trigger: Callable, root=None):
        """
        Parameters
        ----------
        hotkey_str : str
            pynput-format hotkey string, e.g. '<ctrl>+<alt>+t'
        on_trigger : Callable
            Zero-arg function called when the hotkey fires.
            If root is provided, the call is marshalled to the Tkinter
            main thread via root.after(0, on_trigger).
        root : tk.Tk | None
            The Tkinter root window (for thread-safe UI callbacks).
        """
        self._hotkey_str = hotkey_str
        self._on_trigger = on_trigger
        self._root = root
        self._listener: Optional[keyboard.GlobalHotKeys] = None
        self._lock = threading.Lock()

        # For recording mode
        self._recording = False
        self._recorded_keys: set = set()
        self._record_listener: Optional[keyboard.Listener] = None
        self._on_record_done: Optional[Callable] = None

    # ------------------------------------------------------------------
    # Listener lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Start the hotkey listener in a background daemon thread."""
        with self._lock:
            self._start_listener(self._hotkey_str)

    def stop(self) -> None:
        """Stop the hotkey listener."""
        with self._lock:
            self._stop_listener()

    def update_hotkey(self, new_hotkey_str: str) -> None:
        """
        Replace the current hotkey with a new one.
        Stops the old listener and starts a fresh one — no restart required.
        """
        with self._lock:
            self._stop_listener()
            self._hotkey_str = new_hotkey_str
            self._start_listener(new_hotkey_str)

    def get_hotkey(self) -> str:
        return self._hotkey_str

    # ------------------------------------------------------------------
    # Hotkey recording
    # ------------------------------------------------------------------

    def start_recording(self, on_done: Callable[[str], None]) -> None:
        """
        Enter recording mode.
        Listens for the next key combination the user presses and
        calls on_done(hotkey_str) when the user releases all keys.

        Parameters
        ----------
        on_done : Callable[[str], None]
            Receives the pynput-formatted hotkey string, e.g. '<ctrl>+<alt>+t'
        """
        if self._recording:
            return
        self._recording = True
        self._recorded_keys = set()
        self._pressed_count = 0          # track how many keys are currently down
        self._on_record_done = on_done

        # Pause the main listener while recording
        self._stop_listener()

        self._record_listener = keyboard.Listener(
            on_press=self._record_on_press,
            on_release=self._record_on_release,
        )
        self._record_listener.daemon = True
        self._record_listener.start()

    def stop_recording(self) -> None:
        """Cancel recording mode and restore the main listener."""
        self._recording = False
        if self._record_listener:
            self._record_listener.stop()
            self._record_listener = None
        self._start_listener(self._hotkey_str)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _start_listener(self, hotkey_str: str) -> None:
        """(Un-locked) Create and start a GlobalHotKeys listener."""
        try:
            self._listener = keyboard.GlobalHotKeys(
                {hotkey_str: self._fire_callback}
            )
            self._listener.daemon = True
            self._listener.start()
        except Exception as e:
            print(f"[HotkeyManager] Failed to start listener for '{hotkey_str}': {e}")
            self._listener = None

    def _stop_listener(self) -> None:
        """(Un-locked) Stop the current GlobalHotKeys listener."""
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _fire_callback(self) -> None:
        """Called by pynput thread → marshal to Tkinter main thread."""
        if self._root is not None:
            self._root.after(0, self._on_trigger)
        else:
            self._on_trigger()

    # ------------------------------------------------------------------
    # Recording callbacks
    # ------------------------------------------------------------------

    def _record_on_press(self, key) -> None:
        key_str = self._key_to_str(key)
        if key_str:
            self._recorded_keys.add(key_str)
            self._pressed_count += 1

    def _record_on_release(self, key) -> None:
        """
        Track key releases. Only finalise the recorded combo once ALL
        pressed keys have been released (pressed_count reaches 0).
        This prevents capturing a partial combo when modifiers release
        before regular keys.
        """
        if not self._recorded_keys:
            return

        # Decrement counter — clamp at 0 to avoid underflow
        self._pressed_count = max(0, self._pressed_count - 1)

        # Wait until all keys are released
        if self._pressed_count > 0:
            return

        hotkey_str = "+".join(sorted(self._recorded_keys))
        self._recording = False

        if self._record_listener:
            self._record_listener.stop()
            self._record_listener = None

        # Resume main listener
        self._start_listener(self._hotkey_str)

        # Notify caller
        if self._on_record_done:
            if self._root:
                self._root.after(0, lambda: self._on_record_done(hotkey_str))
            else:
                self._on_record_done(hotkey_str)

    @staticmethod
    def _key_to_str(key) -> Optional[str]:
        """Convert a pynput Key or KeyCode to a pynput hotkey string token."""
        try:
            # Special keys (ctrl, alt, shift, etc.)
            if hasattr(key, "name"):
                name = key.name.lower()
                # Map common key names to pynput hotkey format
                mapping = {
                    "ctrl_l": "<ctrl>",
                    "ctrl_r": "<ctrl>",
                    "ctrl": "<ctrl>",
                    "alt_l": "<alt>",
                    "alt_r": "<alt>",
                    "alt": "<alt>",
                    "shift_l": "<shift>",
                    "shift_r": "<shift>",
                    "shift": "<shift>",
                    "cmd": "<cmd>",
                    "cmd_l": "<cmd>",
                    "cmd_r": "<cmd>",
                }
                return mapping.get(name, f"<{name}>")
            # Regular character keys
            char = key.char
            if char and char.isprintable():
                return char.lower()
        except AttributeError:
            pass
        return None

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    @staticmethod
    def format_hotkey_display(hotkey_str: str) -> str:
        """
        Convert pynput hotkey string to human-readable display.
        e.g. '<ctrl>+<alt>+t'  →  'Ctrl + Alt + T'
        """
        parts = hotkey_str.split("+")
        display = []
        for part in parts:
            part = part.strip()
            if part.startswith("<") and part.endswith(">"):
                inner = part[1:-1].capitalize()
                display.append(inner)
            else:
                display.append(part.upper())
        return " + ".join(display)
