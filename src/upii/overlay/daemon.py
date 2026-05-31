
import time
import threading
import sys
from pynput import keyboard

# Helper to manage window state
# Since pywebview dominates the main thread, we need to communicate via events or object state if thread-safe
# Or the OverlayApp instance needs to provide thread-safe methods

class HotkeyDaemon:
    def __init__(self, app_instance):
        self.app = app_instance
        self.visible = True # Starts visible by default in pywebview usually
        
    def on_activate(self):
        print("Global Hotkey Triggered!")
        if self.app.window:
            try:
                # Toggle logic
                # Note: pywebview API for hide/show varies by OS/backend.
                # 'hide()' and 'show()' are standard.
                if self.visible:
                    self.app.window.hide()
                    self.visible = False
                else:
                    self.app.window.show()
                    self.app.window.restore() # Ensure it's not minimized
                    self.visible = True
            except Exception as e:
                print(f"Error toggling window: {e}")

    def start_listener(self):
        # Cmd+Shift+K on Mac is <cmd>+<shift>+k
        # pynput format: '<cmd>+<shift>+k'
        with keyboard.GlobalHotKeys({
                '<cmd>+<shift>+k': self.on_activate,
                '<ctrl>+<shift>+k': self.on_activate # fallback for non-mac
            }) as h:
            h.join()

def run_overlay():
    """
    Entry point to run the overlay.
    """
    from upii.overlay.app import OverlayApp
    
    app = OverlayApp()
    
    # Start Hotkey Daemon in a separate thread
    daemon = HotkeyDaemon(app)
    t = threading.Thread(target=daemon.start_listener, daemon=True)
    t.start()
    
    print("Starting UPII Overlay...")
    print("Press Cmd+Shift+K to toggle.")
    
    # Main thread must run the GUI
    app.launch()

if __name__ == "__main__":
    run_overlay()
