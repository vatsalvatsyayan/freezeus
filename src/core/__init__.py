"""
Core utilities for Freezeus backend.

This module contains shared utilities used across all components:
- Configuration management
- Structured logging
- Error logging and tracking
- Constants and enums
"""

from src.core.logging import get_logger, setup_logging
from src.core.config import get_config, validate_config, Config
from src.core.error_logger import get_error_logger
from src.core.error_models import (
    ErrorComponent,
    ErrorSeverity,
    ErrorType,
    ErrorStage,
    ErrorRecord,
)

__all__ = [
    "get_logger",
    "setup_logging",
    "get_config",
    "validate_config",
    "Config",
    "get_error_logger",
    "ErrorComponent",
    "ErrorSeverity",
    "ErrorType",
    "ErrorStage",
    "ErrorRecord",
]
