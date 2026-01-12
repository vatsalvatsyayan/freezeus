"""
Unit tests for retry utility functions.
"""

import pytest
import time
from src.utils.retry import retry_with_backoff, RetryConfig


class TestRetryConfig:
    """Tests for RetryConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = RetryConfig(max_retries=5, base_delay=2.0)
        assert config.max_retries == 5
        assert config.base_delay == 2.0

    def test_validation_negative_retries(self):
        """Test that negative retries raises error."""
        with pytest.raises(ValueError, match="max_retries"):
            RetryConfig(max_retries=-1)

    def test_validation_invalid_base_delay(self):
        """Test that zero/negative base_delay raises error."""
        with pytest.raises(ValueError, match="base_delay"):
            RetryConfig(base_delay=0)

    def test_validation_max_delay_less_than_base(self):
        """Test that max_delay < base_delay raises error."""
        with pytest.raises(ValueError, match="max_delay"):
            RetryConfig(base_delay=10.0, max_delay=5.0)


class TestRetryWithBackoff:
    """Tests for retry_with_backoff function."""

    def test_succeeds_on_first_try(self):
        """Test function that succeeds immediately."""
        call_count = [0]

        def success_func():
            call_count[0] += 1
            return "success"

        result = retry_with_backoff(success_func)
        assert result == "success"
        assert call_count[0] == 1

    def test_succeeds_after_retries(self):
        """Test function that succeeds after some failures."""
        call_count = [0]

        def eventual_success():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Transient error")
            return "success"

        config = RetryConfig(max_retries=5, base_delay=0.01)
        result = retry_with_backoff(eventual_success, config=config)
        assert result == "success"
        assert call_count[0] == 3

    def test_exhausts_retries(self):
        """Test that all retries are exhausted and exception is raised."""
        call_count = [0]

        def always_fails():
            call_count[0] += 1
            raise ValueError("Persistent error")

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(ValueError, match="Persistent error"):
            retry_with_backoff(always_fails, config=config)

        assert call_count[0] == 3  # Initial + 2 retries

    def test_exponential_backoff_timing(self):
        """Test that delays follow exponential backoff."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            raise ConnectionError("Error")

        config = RetryConfig(max_retries=3, base_delay=0.1, exponential_base=2.0)

        with pytest.raises(ConnectionError):
            retry_with_backoff(failing_func, config=config)

        # Check delays between calls
        if len(call_times) >= 2:
            delay1 = call_times[1] - call_times[0]
            assert 0.08 <= delay1 <= 0.15  # ~0.1s with tolerance

        if len(call_times) >= 3:
            delay2 = call_times[2] - call_times[1]
            assert 0.15 <= delay2 <= 0.30  # ~0.2s with tolerance

    def test_max_delay_cap(self):
        """Test that delay is capped at max_delay."""
        call_times = []

        def failing_func():
            call_times.append(time.time())
            raise ConnectionError("Error")

        config = RetryConfig(
            max_retries=10,
            base_delay=0.1,
            max_delay=0.5,  # Cap at 0.5s (must be >= base_delay)
            exponential_base=2.0
        )

        with pytest.raises(ConnectionError):
            retry_with_backoff(failing_func, config=config)

        # Later delays should be capped at max_delay
        if len(call_times) >= 4:
            delay = call_times[3] - call_times[2]
            assert delay <= 0.6  # Should be capped at 0.5 + tolerance

    def test_retry_on_specific_exception(self):
        """Test retrying only on specific exceptions."""
        call_count = [0]

        def mixed_exceptions():
            call_count[0] += 1
            if call_count[0] == 1:
                raise ConnectionError("Retry this")
            raise ValueError("Don't retry this")

        config = RetryConfig(max_retries=3, base_delay=0.01)

        # Should retry ConnectionError but not ValueError
        with pytest.raises(ValueError, match="Don't retry this"):
            retry_with_backoff(
                mixed_exceptions,
                config=config,
                retry_on=(ConnectionError,)
            )

        assert call_count[0] == 2  # First call + one retry

    def test_on_retry_callback(self):
        """Test that on_retry callback is called."""
        call_count = [0]
        retry_info = []

        def failing_func():
            call_count[0] += 1
            raise ConnectionError("Error")

        def on_retry_callback(attempt, exception):
            retry_info.append((attempt, str(exception)))

        config = RetryConfig(max_retries=2, base_delay=0.01)

        with pytest.raises(ConnectionError):
            retry_with_backoff(
                failing_func,
                config=config,
                on_retry=on_retry_callback
            )

        assert len(retry_info) == 2  # 2 retries
        assert retry_info[0][0] == 1  # First retry
        assert retry_info[1][0] == 2  # Second retry
