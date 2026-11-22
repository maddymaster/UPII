"""Real-window overlay test (macOS): Escape and the hotkey toggle really hide and show the
window. It opens a window on screen, so it runs only when asked:

    UPII_GUI_TESTS=1 pytest -q tests/test_overlay_gui.py

It needs the overlay extra (pywebview). The hotkey is driven through HotkeyDaemon.on_activate
from a background thread with its own CFRunLoop, like pynput's listener; pressing the real
keys needs Accessibility permission, which a test process does not have.
"""
import os
import subprocess
import sys
import textwrap

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("UPII_GUI_TESTS") != "1" or sys.platform != "darwin",
    reason="opens a real window: set UPII_GUI_TESTS=1 on macOS",
)

PROBE = textwrap.dedent('''
    import sys, threading, time
    for m in ("pynput", "pynput.keyboard"):
        from unittest.mock import MagicMock; sys.modules.setdefault(m, MagicMock())
    import Quartz
    import upii.overlay.app as A
    class _Stub: pass
    A.ContextRehydrator = _Stub; A.LocalLLM = _Stub
    from upii.overlay.daemon import HotkeyDaemon
    app = A.OverlayApp(); daemon = HotkeyDaemon(app)
    def step(name, fn):
        fn(); time.sleep(1.0); print(name, app.native_visible(), app.visible, flush=True)
    def run():
        while app.window is None: time.sleep(0.05)
        app.window.events.shown.wait(20); time.sleep(1.5)
        print("start", app.native_visible(), app.visible, flush=True)
        step("hotkey1", daemon.on_activate)
        step("hotkey2", daemon.on_activate)
        step("escape", app.api.hide_window)
        step("hotkey3", daemon.on_activate)
        app.window.destroy()
    def tap_thread():
        # Run the steps from inside a CFRunLoop callback on a non-main thread, like pynput.
        fired = []
        def fire(timer, info):
            if not fired:
                fired.append(1); run()
        t = Quartz.CFRunLoopTimerCreate(None, Quartz.CFAbsoluteTimeGetCurrent() + 0.2, 0, 0, 0, fire, None)
        Quartz.CFRunLoopAddTimer(Quartz.CFRunLoopGetCurrent(), t, Quartz.kCFRunLoopCommonModes)
        Quartz.CFRunLoopRunInMode(Quartz.kCFRunLoopDefaultMode, 60, True)
    threading.Thread(target=tap_thread, daemon=True).start()
    app.launch()
''')


def test_escape_and_hotkey_really_hide_and_show_the_window(tmp_path):
    pytest.importorskip("webview")
    src = os.path.join(os.path.dirname(__file__), "..", "src")
    env = dict(os.environ, PYTHONPATH=os.path.abspath(src))
    r = subprocess.run([sys.executable, "-c", PROBE], cwd=tmp_path, env=env,
                       capture_output=True, text=True, timeout=90)
    lines = [l for l in r.stdout.splitlines() if l.split(" ")[0] in
             ("start", "hotkey1", "hotkey2", "escape", "hotkey3")]
    assert lines == [
        "start True True",
        "hotkey1 False False",
        "hotkey2 True True",
        "escape False False",
        "hotkey3 True True",
    ], r.stdout + r.stderr
    assert "warning:" not in r.stdout
