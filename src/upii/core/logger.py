import logging
import logging.handlers
import sys
from typing import Optional

logger = logging.getLogger("upii")

def setup_logging(debug: bool = False, log_file: str = "upii.log"):
    """Configures structured, rotating logging."""
    
    # We configure the root logger so 'upii' logger inherits
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)
    
    # Remove existing handlers to avoid duplication during tests/reloads
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 1. Rotating File Handler (10MB x 5 backups)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10*1024*1024, backupCount=5
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.DEBUG if debug else logging.INFO)
    root_logger.addHandler(file_handler)

    # 2. Console Handler (Standard Error)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    # Only show ERRORs on console by default unless debug is on?
    # CLI usually handles output via print, logs are for background/debug.
    # Let's keep console logs high level or suppress if not debug.
    console_handler.setLevel(logging.DEBUG if debug else logging.WARNING)
    root_logger.addHandler(console_handler)

    return root_logger
