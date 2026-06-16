"""Logging configuration module."""

import os
import sys
from typing import Optional
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


class LoggingConfig:
    """Configuration for logging setup using loguru."""

    def __init__(
        self,
        log_level: str = "INFO",
        log_file_path: Optional[str] = None,
        cloudwatch_log_group: Optional[str] = None,
    ):
        """
        Initialize logging configuration.

        Args:
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            log_file_path: Optional path to log file
            cloudwatch_log_group: Optional CloudWatch log group name
        """
        self.log_level = log_level
        self.log_file_path = log_file_path
        self.cloudwatch_log_group = cloudwatch_log_group

    @classmethod
    def from_env(cls) -> "LoggingConfig":
        """Create LoggingConfig from environment variables."""
        log_file_path = os.getenv("LOG_FILE_PATH")
        if log_file_path:
            # Create log directory if it doesn't exist
            Path(log_file_path).parent.mkdir(parents=True, exist_ok=True)

        return cls(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file_path=log_file_path,
            cloudwatch_log_group=os.getenv("CLOUDWATCH_LOG_GROUP"),
        )

    def setup_logging(self) -> None:
        """Configure loguru logger with appropriate handlers."""
        # Remove default handler
        logger.remove()

        # Add console handler with color
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level=self.log_level,
            colorize=True,
        )

        # Add file handler if path is provided
        if self.log_file_path:
            logger.add(
                self.log_file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                level=self.log_level,
                rotation="100 MB",
                retention="30 days",
                compression="zip",
            )

        logger.info(f"Logging configured with level: {self.log_level}")


# Global instance
logging_config = LoggingConfig.from_env()

