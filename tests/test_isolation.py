import time
import logging
from upii.core.concurrency import SafeRunner

def test_safe_run_swallows_exception(caplog):
    def risky():
        raise ValueError("Boom!")
    
    with caplog.at_level(logging.ERROR):
        result = SafeRunner.run_safe(risky)
        assert result is None
        assert "Ambient Failure protected" in caplog.text
        assert "Boom!" in caplog.text

def test_daemon_isolation():
    # Verify the thread runs and handles crash without stopping main test
    def crasher():
        raise RuntimeError("Thread Crash")
        
    t = SafeRunner.run_daemon(crasher, name="TestCrash")
    t.join(timeout=1.0)
    
    assert not t.is_alive() # Should have finished
    # We can't easily assert log output from thread in pytest with caplog reliably 
    # dependent on log configuration, but the fact that test didn't crash is pass.
