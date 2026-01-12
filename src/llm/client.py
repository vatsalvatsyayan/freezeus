"""
Gemini API client for LLM job extraction.

This module handles all interactions with the Google Gemini API,
including initialization, retries, and error handling.
"""

import os
import time
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv
from src.core.logging import get_logger

logger = get_logger(__name__)

# Load environment configuration
load_dotenv(dotenv_path=Path("configs/.env"), override=True)

# Import Gemini SDK
try:
    import google.generativeai as genai
except ImportError as e:
    raise RuntimeError(
        "google-generativeai not installed. "
        "pip install google-generativeai>=0.8.0"
    ) from e


# Configuration from environment
DEFAULT_MODEL = os.getenv("GEMINI_MODEL", "models/gemini-1.5-pro-latest")
API_KEY = os.getenv("GEMINI_API_KEY")
MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "2"))
RETRY_BASE_SLEEP = float(os.getenv("LLM_RETRY_BASE_SLEEP", "1.6"))
VERBOSE = os.getenv("LLM_VERBOSE", "1") not in {"0", "false", "False"}


def _log(msg: str):
    """Internal logging helper."""
    if VERBOSE:
        logger.info(f"[LLM Client] {msg}")


def get_gemini_client(api_key: str = None, model_name: str = None):
    """
    Initialize and configure Gemini API client.

    Args:
        api_key: Optional API key (defaults to env GEMINI_API_KEY)
        model_name: Optional model name (defaults to env GEMINI_MODEL)

    Returns:
        Configured GenerativeModel instance

    Raises:
        RuntimeError: If API key is missing

    Example:
        >>> client = get_gemini_client()
        >>> client.model_name
        'models/gemini-1.5-pro-latest'
    """
    key = api_key or API_KEY
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY missing. "
            "Set it in configs/.env (e.g., GEMINI_API_KEY=...)"
        )

    genai.configure(api_key=key)
    model = model_name or DEFAULT_MODEL

    _log(f"Initialized Gemini client with model: {model}")
    return genai.GenerativeModel(model)


def call_gemini_with_retries(
    prompt: str,
    model_name: str = None,
    generation_config: Dict[str, Any] = None,
    max_retries: int = None,
    base_sleep: float = None
):
    """
    Call Gemini API with exponential backoff retry logic.

    Args:
        prompt: The prompt text to send to the model
        model_name: Optional model name (defaults to DEFAULT_MODEL)
        generation_config: Optional generation configuration dict
        max_retries: Optional max retry count (defaults to MAX_RETRIES)
        base_sleep: Optional base sleep duration in seconds

    Returns:
        GenerateContentResponse from Gemini API

    Raises:
        Last exception if all retries exhausted

    Example:
        >>> response = call_gemini_with_retries("Extract jobs from: ...")
        >>> text = response.text
    """
    model_name = model_name or DEFAULT_MODEL
    max_retries = max_retries if max_retries is not None else MAX_RETRIES
    base_sleep = base_sleep if base_sleep is not None else RETRY_BASE_SLEEP

    if generation_config is None:
        generation_config = {
            "temperature": 0.0,
            "candidate_count": 1,
            "response_mime_type": "application/json",
        }

    model = genai.GenerativeModel(model_name)
    tries = max_retries + 1
    last_err = None

    for i in range(tries):
        try:
            _log(f"API call attempt {i+1}/{tries}")
            response = model.generate_content(prompt, generation_config=generation_config)
            _log(f"API call succeeded on attempt {i+1}")
            return response
        except Exception as e:
            last_err = e
            sleep_duration = base_sleep * (2 ** i)  # Exponential backoff

            if i < tries - 1:  # Don't sleep on last attempt
                _log(
                    f"API call failed (attempt {i+1}/{tries}): {e}. "
                    f"Retrying in {sleep_duration:.1f}s"
                )
                time.sleep(sleep_duration)
            else:
                _log(f"API call failed on final attempt {i+1}/{tries}: {e}")

    # All retries exhausted
    logger.error(f"All {max_retries} retries exhausted. Last error: {last_err}")
    raise last_err


def call_gemini(
    prompt: str,
    model_name: str = None,
    temperature: float = 0.0,
    response_mime_type: str = "application/json"
):
    """
    Simplified Gemini API call with default retry logic.

    Args:
        prompt: The prompt text
        model_name: Optional model name
        temperature: Generation temperature (0.0 = deterministic)
        response_mime_type: Expected response format

    Returns:
        Response text content

    Example:
        >>> text = call_gemini("Extract jobs...")
        >>> isinstance(text, str)
        True
    """
    gen_config = {
        "temperature": temperature,
        "candidate_count": 1,
        "response_mime_type": response_mime_type,
    }

    response = call_gemini_with_retries(
        prompt=prompt,
        model_name=model_name,
        generation_config=gen_config
    )

    return getattr(response, "text", "").strip()
