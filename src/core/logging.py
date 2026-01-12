"""
Structured Logging Configuration for Freezeus Backend

This module provides centralized logging configuration with:
- Console and file output
- Configurable log levels
- Structured log formatting
- Per-module loggers
"""

import logging
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


# Default log level from environment or INFO
DEFAULT_LOG_LEVEL = "INFO"

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    level: str = DEFAULT_LOG_LEVEL,
    log_file: Optional[str] = None,
    console: bool = True
) -> logging.Logger:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file (default: logs/crawler.log)
        console: Whether to log to console (default: True)

    Returns:
        Configured root logger

    Example:
        >>> logger = setup_logging(level="DEBUG")
        >>> logger.info("Application started")
    """
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, level.upper()))
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_path = Path(log_file)
    else:
        # Default: logs/crawler.log
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True, parents=True)

        # Create dated log file
        date_str = datetime.now().strftime("%Y%m%d")
        log_path = log_dir / f"crawler_{date_str}.log"

    log_path.parent.mkdir(exist_ok=True, parents=True)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setLevel(getattr(logging, level.upper()))
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    root_logger.info(f"Logging initialized - Level: {level}, File: {log_path}")

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Args:
        name: Name of the logger (typically __name__)

    Returns:
        Logger instance for the module

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    return logging.getLogger(name)


# Convenience function for common use case
def init_crawler_logging(verbose: bool = False) -> logging.Logger:
    """
    Initialize logging for crawler with appropriate settings.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO

    Returns:
        Configured logger

    Example:
        >>> logger = init_crawler_logging(verbose=True)
    """
    level = "DEBUG" if verbose else "INFO"
    return setup_logging(level=level)
