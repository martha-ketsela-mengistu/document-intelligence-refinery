import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from typing import Optional

def get_logger(name: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Get a configured logger with both console and rotating file handlers.
    """
    logger = logging.getLogger(name)
    
    # Avoid adding multiple handlers if the logger is already configured
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)  # Capture everything, filter at handler level

    # Log format: 2026-03-06T16:31:39 | INFO     | src.agents.triage | Message...
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S"
    )

    # Console Handler (INFO and above)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler (DEBUG and above)
    log_dir = ".refinery/logs"
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "refinery.log")
    
    file_handler = RotatingFileHandler(
        log_file, 
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Prevent propagation to root logger to avoid duplicate logs in some environments
    logger.propagate = False

    return logger
