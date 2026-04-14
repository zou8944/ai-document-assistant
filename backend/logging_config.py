"""
Logging configuration for AI Document Assistant Backend.
"""

import logging
import sys


def configure_logging(config):
    """Configure logging with file and console handlers

    Args:
        config: AppConfig instance with log_level and log file path
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.system.log_level.upper()))

    # Clear existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [Thread-%(threadName)s] - %(message)s'
    )

    # File handler
    file_handler = logging.FileHandler(config.get_log_file_path())
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
