"""
Configuration Management for Freezeus Backend

This module provides centralized configuration management with:
- Environment variable loading
- Type validation
- Sensible defaults
- Configuration documentation
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv


class Config:
    """
    Application configuration loaded from environment variables.

    All configuration is read from configs/.env file or environment variables.
    See configs/.env.example for documentation of all settings.
    """

    def __init__(self, env_path: Optional[Path] = None):
        """
        Initialize configuration from environment.

        Args:
            env_path: Path to .env file (default: configs/.env)
        """
        if env_path is None:
            env_path = Path("configs/.env")

        # Load environment variables
        load_dotenv(dotenv_path=env_path, override=True)

        # === Gemini API Configuration ===
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
        self.llm_max_html_chars: int = int(os.getenv("LLM_MAX_HTML_CHARS", "250000"))
        self.llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
        self.llm_retry_base_sleep: float = float(os.getenv("LLM_RETRY_BASE_SLEEP", "1.6"))
        self.llm_verbose: bool = os.getenv("LLM_VERBOSE", "1") not in {"0", "false", "False"}
        self.llm_overwrite: bool = os.getenv("LLM_OVERWRITE", "0") in {"1", "true", "True"}

        # === Supabase Configuration ===
        self.supabase_enabled: bool = os.getenv("SUPABASE_ENABLED", "1") not in {"0", "false", "False"}
        self.supabase_url: Optional[str] = os.getenv("SUPABASE_URL")
        self.supabase_service_role_key: Optional[str] = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        self.supabase_jobs_table: str = os.getenv("SUPABASE_JOBS_TABLE", "jobs")

        # === Crawler Configuration ===
        self.max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
        self.nav_timeout_ms: int = int(os.getenv("NAV_TIMEOUT_MS", "45000"))
        self.per_domain_delay_min: int = int(os.getenv("PER_DOMAIN_DELAY_MIN", "8"))
        self.per_domain_delay_max: int = int(os.getenv("PER_DOMAIN_DELAY_MAX", "15"))

        # === Logging Configuration ===
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.log_dir: Path = Path(os.getenv("LOG_DIR", "logs"))

        # === Output Paths ===
        self.base_out_dir: Path = Path(os.getenv("BASE_OUT_DIR", "out"))
        self.config_urls_file: Path = Path(os.getenv("CONFIG_URLS_FILE", "configs/urls.txt"))
        self.llm_prompt_file: Path = Path(os.getenv("LLM_PROMPT_FILE", "configs/llm_extraction_prompt.txt"))

    def validate(self) -> None:
        """
        Validate required configuration is present.

        Raises:
            ValueError: If required configuration is missing or invalid
        """
        errors = []

        # Check required API keys
        if not self.gemini_api_key:
            errors.append("GEMINI_API_KEY is required")

        # Check Supabase config if enabled
        if self.supabase_enabled:
            if not self.supabase_url:
                errors.append("SUPABASE_URL is required when Supabase is enabled")
            if not self.supabase_service_role_key:
                errors.append("SUPABASE_SERVICE_ROLE_KEY is required when Supabase is enabled")

        # Check required files exist
        if not self.config_urls_file.exists():
            errors.append(f"URLs file not found: {self.config_urls_file}")

        # Validate numeric ranges
        if self.llm_max_html_chars <= 0:
            errors.append(f"LLM_MAX_HTML_CHARS must be positive, got {self.llm_max_html_chars}")

        if self.max_retries < 0:
            errors.append(f"MAX_RETRIES must be non-negative, got {self.max_retries}")

        if self.nav_timeout_ms <= 0:
            errors.append(f"NAV_TIMEOUT_MS must be positive, got {self.nav_timeout_ms}")

        if self.per_domain_delay_min > self.per_domain_delay_max:
            errors.append(f"PER_DOMAIN_DELAY_MIN ({self.per_domain_delay_min}) cannot be greater than PER_DOMAIN_DELAY_MAX ({self.per_domain_delay_max})")

        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))

    def __repr__(self) -> str:
        """Return string representation of config (without secrets)."""
        return (
            f"Config(\n"
            f"  gemini_model={self.gemini_model},\n"
            f"  gemini_api_key={'***' if self.gemini_api_key else 'NOT SET'},\n"
            f"  supabase_enabled={self.supabase_enabled},\n"
            f"  supabase_url={self.supabase_url or 'NOT SET'},\n"
            f"  max_retries={self.max_retries},\n"
            f"  log_level={self.log_level}\n"
            f")"
        )


# Global configuration instance (lazy-loaded)
_config: Optional[Config] = None


def get_config(env_path: Optional[Path] = None) -> Config:
    """
    Get the global configuration instance.

    Args:
        env_path: Optional path to .env file (only used on first call)

    Returns:
        Global Config instance

    Example:
        >>> config = get_config()
        >>> print(config.gemini_model)
    """
    global _config
    if _config is None:
        _config = Config(env_path=env_path)
    return _config


def validate_config(env_path: Optional[Path] = None) -> None:
    """
    Validate configuration and raise error if invalid.

    This should be called at application startup to fail fast
    if configuration is incorrect.

    Args:
        env_path: Optional path to .env file

    Raises:
        ValueError: If configuration is invalid

    Example:
        >>> validate_config()  # Raises ValueError if config is bad
        >>> print("Configuration OK")
    """
    config = get_config(env_path=env_path)
    config.validate()
