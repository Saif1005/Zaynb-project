"""Logger utility module using loguru."""

from pathlib import Path
from typing import Optional
from loguru import logger
from config.logging_config import logging_config


def setup_logger(
    log_level: Optional[str] = None,
    log_file_path: Optional[str] = None,
) -> None:
    """
    Setup logger configuration.

    Args:
        log_level: Optional log level override
        log_file_path: Optional log file path override
    """
    if log_level:
        logging_config.log_level = log_level
    if log_file_path:
        logging_config.log_file_path = log_file_path
        # Ensure log directory exists
        Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

    logging_config.setup_logging()


def get_logger(name: Optional[str] = None):
    """
    Get logger instance.

    Args:
        name: Optional logger name (usually __name__)

    Returns:
        Logger instance
    """
    if name:
        return logger.bind(name=name)
    return logger


# Setup logger on import
setup_logger()

