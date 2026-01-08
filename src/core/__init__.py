"""
Core utilities for Freezeus backend.

This module contains shared utilities used across all components:
- Configuration management
- Structured logging
- Constants and enums
"""

from src.core.logging import get_logger, setup_logging

__all__ = ["get_logger", "setup_logging"]
