
import logging
import threading

from pynput import keyboard

logger = logging.getLogger("upii.overlay")


class HotkeyDaemon:
    """Listens for Cmd+Shift+K (Ctrl+Shift+K elsewhere) and toggles the overlay window.
    The window state lives in the app, so Escape and the hotkey agree on it."""

    def __init__(self, app_instance):
        self.app = app_instance

    def on_activate(self):
        logger.debug("overlay hotkey")
        try:
            self.app.toggle("hotkey")
        except Exception as e:  # never let the listener thread die on a window error
            logger.warning(f"Could not toggle the overlay window: {e}")

    def start_listener(self):
        # Cmd+Shift+K on Mac is <cmd>+<shift>+k
        # pynput format: '<cmd>+<shift>+k'
        with keyboard.GlobalHotKeys({
                '<cmd>+<shift>+k': self.on_activate,
                '<ctrl>+<shift>+k': self.on_activate # fallback for non-mac
            }) as h:
            h.join()

def run_overlay(debug: bool = False):
    """Entry point to run the overlay. ``debug`` turns on the web inspector."""
    from upii.overlay.app import OverlayApp

    app = OverlayApp(debug=debug)

    # The hotkey listener runs in a thread; the GUI must own the main thread.
    daemon = HotkeyDaemon(app)
    t = threading.Thread(target=daemon.start_listener, daemon=True)
    t.start()

    print("Starting UPII Overlay...")
    print("Press Cmd+Shift+K to show or hide it, Escape to hide it.")
    if debug:
        print("Web inspector on (--debug).")

    app.launch()


if __name__ == "__main__":
    run_overlay()
