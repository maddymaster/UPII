import time
import random
from upii.ambient.sources import Source, registry
from upii.core.concurrency import SafeRunner
from upii.core.logger import logger

class BrowserSource(Source):
    """Simulates capturing high-dwell web pages."""
    def __init__(self):
        super().__init__("browser", "Captures metadata from high-dwell browser tabs.")
        self.thread = None
        
    def start(self):
        self.is_running = True
        self.thread = SafeRunner.run_daemon(self._loop, name="BrowserWatcher")
        
    def stop(self):
        self.is_running = False
        
    def _loop(self):
        while self.is_running:
            time.sleep(10) # Simulate infrequent capture
            # In a real app, this would poll a browser extension API
            # Here we just randomly decide to 'capture' something if enabled
            if random.random() < 0.1: # 10% chance per loop
                 logger.info("BrowserSource: simulating capture")
                 fake_url = "https://example.com/interesting-article"
                 self.storage.add_event("browser_visit", fake_url)
                 self.storage.log_audit(self.name, "capture", {"url": fake_url, "dwell_time": 120})

class CalendarSource(Source):
    """Simulates capturing calendar metadata."""
    def __init__(self):
        super().__init__("calendar", "Ingests event titles and participants.")
        
    def start(self):
        self.is_running = True
        # Calendar might be poll-once or interval
        self.thread = SafeRunner.run_daemon(self._loop, name="CalendarWatcher")
        
    def stop(self):
        self.is_running = False
        
    def _loop(self):
        while self.is_running:
            time.sleep(20)
            if random.random() < 0.1:
                logger.info("CalendarSource: simulating capture")
                self.storage.add_event("calendar_event", "Meeting with Omega Team")
                self.storage.log_audit(self.name, "capture", {"summary": "Meeting", "participants": ["alice@example.com"]})

# Register
registry.register(BrowserSource())
registry.register(CalendarSource())
