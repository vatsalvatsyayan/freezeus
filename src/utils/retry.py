"""
Retry utility with exponential backoff for Freezeus backend.

This module provides retry logic for transient failures.
"""

import time
from typing import Callable, TypeVar, Optional
from dataclasses import dataclass
from src.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0

    def __post_init__(self):
        """Validate configuration."""
        if self.max_retries < 0:
            raise ValueError("max_retries must be non-negative")
        if self.base_delay <= 0:
            raise ValueError("base_delay must be positive")
        if self.max_delay < self.base_delay:
            raise ValueError("max_delay must be >= base_delay")
        if self.exponential_base <= 1:
            raise ValueError("exponential_base must be > 1")


def retry_with_backoff(
    func: Callable[[], T],
    config: Optional[RetryConfig] = None,
    retry_on: tuple = (Exception,),
    on_retry: Optional[Callable[[int, Exception], None]] = None
) -> T:
    """
    Retry a function with exponential backoff.

    Args:
        func: Function to retry (takes no arguments)
        config: Retry configuration (default: 3 retries, 1s base delay)
        retry_on: Tuple of exception types to retry on
        on_retry: Optional callback called on each retry (attempt, exception)

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries exhausted

    Example:
        >>> def flaky_function():
        ...     import random
        ...     if random.random() < 0.5:
        ...         raise ConnectionError("Transient error")
        ...     return "Success"
        >>> result = retry_with_backoff(flaky_function)
        >>> result == "Success"
        True
    """
    if config is None:
        config = RetryConfig()

    last_exception = None

    for attempt in range(config.max_retries + 1):
        try:
            return func()
        except retry_on as e:
            last_exception = e

            # Last attempt - don't wait, just raise
            if attempt == config.max_retries:
                logger.error(f"All {config.max_retries} retries exhausted: {e}")
                raise

            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.exponential_base ** attempt),
                config.max_delay
            )

            logger.warning(
                f"Retry {attempt + 1}/{config.max_retries} "
                f"after {delay:.2f}s: {e}"
            )

            # Call optional callback
            if on_retry:
                on_retry(attempt + 1, e)

            time.sleep(delay)

    # Should never reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Retry logic error")


def retry_async_with_backoff(
    func: Callable,
    config: Optional[RetryConfig] = None,
    retry_on: tuple = (Exception,)
):
    """
    Async version of retry_with_backoff.

    Args:
        func: Async function to retry
        config: Retry configuration
        retry_on: Tuple of exception types to retry on

    Returns:
        Async wrapper function

    Example:
        >>> import asyncio
        >>> async def flaky_async():
        ...     return "Success"
        >>> async def main():
        ...     result = await retry_async_with_backoff(flaky_async)()
        ...     return result
        >>> # asyncio.run(main()) == "Success"
    """
    import asyncio

    if config is None:
        config = RetryConfig()

    async def wrapper(*args, **kwargs):
        last_exception = None

        for attempt in range(config.max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except retry_on as e:
                last_exception = e

                if attempt == config.max_retries:
                    logger.error(f"All {config.max_retries} retries exhausted: {e}")
                    raise

                delay = min(
                    config.base_delay * (config.exponential_base ** attempt),
                    config.max_delay
                )

                logger.warning(
                    f"Retry {attempt + 1}/{config.max_retries} "
                    f"after {delay:.2f}s: {e}"
                )

                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic error")

    return wrapper
