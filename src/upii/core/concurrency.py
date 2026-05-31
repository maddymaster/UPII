import threading
import traceback
import logging
from typing import Callable, Any

# Dedicated logger for ambient failures
ambient_logger = logging.getLogger("upii.ambient")

class SafeRunner:
    """
    Executes tasks in isolation. 
    Failures here MUST NOT propagate to the main application.
    """
    
    @staticmethod
    def run_safe(func: Callable[..., Any], *args, **kwargs) -> Any:
        """Run a function synchronously but suppress all exceptions."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = f"Ambient Failure protected: {e}\n{traceback.format_exc()}"
            ambient_logger.error(error_msg)
            return None

    @staticmethod
    def run_daemon(target: Callable, name: str = "AmbientWorker", args: tuple = ()) -> threading.Thread:
        """
        Spawns a daemon thread with an isolated run loop.
        Arguments:
            target: The function to run (must be infinite loop aware if needed)
            name: Thread name for debugging
        """
        def _wrapper():
            try:
                ambient_logger.info(f"Starting isolated worker: {name}")
                target(*args)
            except Exception as e:
                ambient_logger.critical(f"Worker {name} CRASHED: {e}\n{traceback.format_exc()}")
            finally:
                ambient_logger.info(f"Worker {name} terminated.")

        t = threading.Thread(target=_wrapper, name=name, daemon=True)
        t.start()
        return t
