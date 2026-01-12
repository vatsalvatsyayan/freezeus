# Core Module

Shared utilities and configuration management for the Freezeus backend. Provides centralized configuration, structured logging, and common utilities used across all components.

## 📁 Module Structure

```
src/core/
├── README.md         # This file
├── __init__.py       # Module exports
├── config.py         # Configuration management
└── logging.py        # Structured logging
```

## 🔗 Module Dependencies

```
All other modules depend on core
    ├── src.crawler → uses logging and config
    ├── src.llm → uses logging and config
    ├── src.db → uses config for Supabase settings
    └── External dependencies
        ├── python-dotenv (environment variable loading)
        └── logging (stdlib)
```

## 📄 File Descriptions

### `config.py` - Configuration Management
**Purpose**: Centralized configuration from environment variables with validation.

**Key Classes**:

#### `Config` - Application configuration
Loads all settings from environment variables (typically from `configs/.env`).

**Configuration Sections**:
- **Gemini API**: API key, model selection, retry settings
- **Supabase**: Database connection, table names
- **Crawler**: Timeouts, delays, retry logic
- **Logging**: Log levels, output paths
- **Output Paths**: Base directories for crawl output

**Key Methods**:
- `__init__(env_path: Optional[Path] = None)` - Load config from .env file
- `validate() -> None` - Validate required settings are present
- `__repr__() -> str` - String representation (hides secrets)

**Usage Example**:
```python
from src.core.config import get_config, validate_config

# Get global config instance
config = get_config()

# Access settings
print(config.gemini_model)  # "models/gemini-1.5-pro-latest"
print(config.supabase_enabled)  # True/False

# Validate at startup (fail fast if config is wrong)
try:
    validate_config()
    print("Configuration OK")
except ValueError as e:
    print(f"Config error: {e}")
    sys.exit(1)
```

**Key Configuration Variables**:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `GEMINI_MODEL` | `gemini-1.5-pro-latest` | Model to use for extraction |
| `LLM_MAX_HTML_CHARS` | `250000` | Max HTML size for LLM |
| `LLM_MAX_RETRIES` | `2` | Retry attempts for LLM calls |
| `LLM_RETRY_BASE_SLEEP` | `1.6` | Exponential backoff base (seconds) |
| `LLM_VERBOSE` | `1` | Enable verbose logging |
| `SUPABASE_ENABLED` | `1` | Enable database writes |
| `SUPABASE_URL` | *(required if enabled)* | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | *(required if enabled)* | Supabase API key |
| `SUPABASE_JOBS_TABLE` | `jobs` | Database table name |
| `MAX_RETRIES` | `3` | Crawler navigation retries |
| `NAV_TIMEOUT_MS` | `45000` | Navigation timeout (ms) |
| `PER_DOMAIN_DELAY_MIN` | `8` | Min delay between seeds (s) |
| `PER_DOMAIN_DELAY_MAX` | `15` | Max delay between seeds (s) |
| `LOG_LEVEL` | `INFO` | Logging level |
| `LOG_DIR` | `logs` | Log output directory |

**Validation Rules**:
- `GEMINI_API_KEY` must be set
- If `SUPABASE_ENABLED=1`, requires `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`
- `configs/urls.txt` must exist
- Numeric values must be positive and in valid ranges
- `PER_DOMAIN_DELAY_MIN` ≤ `PER_DOMAIN_DELAY_MAX`

---

### `logging.py` - Structured Logging
**Purpose**: Centralized logging configuration with console and file output.

**Key Functions**:

#### `setup_logging(level: str, log_file: Optional[str], console: bool) -> logging.Logger`
Configure root logger with handlers.

**Parameters**:
- `level`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`)
- `log_file`: Path to log file (default: `logs/crawler_YYYYMMDD.log`)
- `console`: Whether to log to stdout (default: `True`)

**Returns**: Configured root logger

**Example**:
```python
from src.core.logging import setup_logging

# Basic setup
logger = setup_logging(level="INFO")
logger.info("Application started")

# Debug mode with custom log file
logger = setup_logging(
    level="DEBUG",
    log_file="logs/debug.log",
    console=True
)
```

#### `get_logger(name: str) -> logging.Logger`
Get a module-specific logger.

**Parameters**:
- `name`: Logger name (typically `__name__`)

**Returns**: Logger instance for the module

**Example**:
```python
from src.core.logging import get_logger

logger = get_logger(__name__)
logger.info("Processing started")
logger.debug(f"Processing item: {item_id}")
logger.error(f"Failed to process: {error}")
```

#### `init_crawler_logging(verbose: bool) -> logging.Logger`
Convenience function for crawler initialization.

**Parameters**:
- `verbose`: If `True`, use `DEBUG` level; otherwise `INFO`

**Returns**: Configured logger

**Example**:
```python
from src.core.logging import init_crawler_logging

# Production mode
logger = init_crawler_logging(verbose=False)

# Debug mode
logger = init_crawler_logging(verbose=True)
```

**Log Format**:
```
%(asctime)s - %(name)s - %(levelname)s - %(message)s
```

**Example Output**:
```
2026-01-08 15:30:45 - src.crawler.multi_capture - INFO - [seed] example.com → https://example.com/careers
2026-01-08 15:30:47 - src.llm.client - DEBUG - Sending request to Gemini API
2026-01-08 15:30:50 - src.db.supabase_client - INFO - Upserted 25 jobs for example.com
```

**Features**:
- Dual output (console + file)
- Dated log files: `logs/crawler_20260108.log`
- Structured format with timestamps
- Per-module loggers
- Configurable log levels

---

## 🔄 How Core Wires to Other Modules

### Initialization Flow

```
Application Startup
    ├── 1. Load configuration
    │   └── get_config() reads configs/.env
    │
    ├── 2. Validate configuration
    │   └── validate_config() checks required settings
    │
    └── 3. Initialize logging
        └── setup_logging() or init_crawler_logging()

Then other modules import:
    ├── Crawler → get_config(), get_logger(__name__)
    ├── LLM → get_config(), get_logger(__name__)
    └── DB → get_config() for Supabase settings
```

### Configuration Flow

```
configs/.env
    ↓ (python-dotenv)
Config.__init__()
    ↓
Config.validate()
    ↓
get_config() ← All modules access settings here
    ├── crawler/multi_capture.py (timeouts, delays)
    ├── llm/client.py (API keys, model selection)
    ├── llm/extractor.py (HTML size limits, retry settings)
    └── db/supabase_client.py (connection strings, table names)
```

### Logging Flow

```
setup_logging(level="INFO")
    ↓
Root Logger Configured
    ├── Console Handler → stdout
    └── File Handler → logs/crawler_YYYYMMDD.log
    ↓
Modules call get_logger(__name__)
    ├── src.crawler.multi_capture → logger.info("[seed] ...")
    ├── src.llm.client → logger.debug("API call ...")
    └── src.db.supabase_client → logger.error("DB error ...")
    ↓
Logs written to both console and file
```

## 🧪 Testing

**Current Coverage**: Core utilities have integration testing through usage in other modules.

**Recommended Tests** (not yet implemented):
- `test_config_validation()` - Test Config.validate() catches errors
- `test_config_loading()` - Test loading from .env file
- `test_logging_setup()` - Test logger configuration
- `test_logging_output()` - Test log format and output

**Manual Testing**:
```python
# Test configuration
from src.core.config import get_config, validate_config

config = get_config()
print(config)  # Should hide API keys

try:
    validate_config()
    print("✓ Config valid")
except ValueError as e:
    print(f"✗ Config invalid: {e}")

# Test logging
from src.core.logging import setup_logging, get_logger

logger = setup_logging(level="DEBUG")
module_logger = get_logger(__name__)

logger.info("Root logger message")
module_logger.debug("Module logger message")
```

## 🔧 Configuration Files

### `configs/.env`
Main configuration file for all environment variables.

**Example**:
```bash
# === Gemini API ===
GEMINI_API_KEY=your-api-key-here
GEMINI_MODEL=models/gemini-1.5-pro-latest
LLM_MAX_HTML_CHARS=250000
LLM_MAX_RETRIES=2
LLM_RETRY_BASE_SLEEP=1.6
LLM_VERBOSE=1
LLM_OVERWRITE=0

# === Supabase Database ===
SUPABASE_ENABLED=1
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key
SUPABASE_JOBS_TABLE=jobs_raw

# === Crawler ===
MAX_RETRIES=3
NAV_TIMEOUT_MS=45000
PER_DOMAIN_DELAY_MIN=8
PER_DOMAIN_DELAY_MAX=15

# === Logging ===
LOG_LEVEL=INFO
LOG_DIR=logs
```

See `configs/.env.example` for full documentation.

## 🚀 Common Use Cases

### 1. Application Startup with Config Validation

```python
from src.core.config import get_config, validate_config
from src.core.logging import init_crawler_logging
import sys

def main():
    # Initialize logging
    logger = init_crawler_logging(verbose=True)

    # Load and validate config
    try:
        config = get_config()
        validate_config()
        logger.info(f"Configuration loaded: {config}")
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Now safe to use config in other modules
    logger.info("Starting application...")

if __name__ == "__main__":
    main()
```

### 2. Module-Specific Logging

```python
from src.core.logging import get_logger

logger = get_logger(__name__)

def process_item(item_id: str):
    logger.info(f"Processing item {item_id}")

    try:
        # ... processing logic ...
        logger.debug(f"Item {item_id} processed successfully")
    except Exception as e:
        logger.error(f"Failed to process {item_id}: {e}", exc_info=True)
        raise
```

### 3. Accessing Configuration in Modules

```python
from src.core.config import get_config

def make_api_call():
    config = get_config()

    # Use config values
    api_key = config.gemini_api_key
    model = config.gemini_model
    max_retries = config.llm_max_retries

    # ... make API call with these settings ...
```

### 4. Conditional Features Based on Config

```python
from src.core.config import get_config

def save_results(data):
    config = get_config()

    # Save to file always
    save_to_file(data)

    # Conditionally save to database
    if config.supabase_enabled:
        save_to_database(data)
```

## 📝 Important Functions Reference

| Function | Purpose | Returns |
|----------|---------|---------|
| `get_config(env_path)` | Get global config instance | `Config` |
| `validate_config(env_path)` | Validate configuration (fail fast) | `None` (raises on error) |
| `setup_logging(level, log_file, console)` | Configure root logger | `logging.Logger` |
| `get_logger(name)` | Get module-specific logger | `logging.Logger` |
| `init_crawler_logging(verbose)` | Initialize crawler logging | `logging.Logger` |

## 🐛 Troubleshooting

### Issue: Missing required configuration
**Symptoms**: `ValueError: GEMINI_API_KEY is required`

**Solution**:
1. Check that `configs/.env` exists
2. Verify `GEMINI_API_KEY=...` is set in `.env`
3. Ensure no typos in variable name

### Issue: Configuration not loading
**Symptoms**: Config values show defaults instead of .env values

**Solution**:
1. Verify `.env` file is at `configs/.env` (not project root)
2. Check that `python-dotenv` is installed
3. Ensure values don't have quotes: use `KEY=value` not `KEY="value"`

### Issue: Supabase validation error
**Symptoms**: `ValueError: SUPABASE_URL is required when Supabase is enabled`

**Solution**: Either:
1. Disable Supabase: `SUPABASE_ENABLED=0`
2. Or provide credentials: `SUPABASE_URL=...` and `SUPABASE_SERVICE_ROLE_KEY=...`

### Issue: Logs not appearing
**Symptoms**: No log output to console or file

**Solution**:
1. Check log level is appropriate (use `DEBUG` for verbose output)
2. Ensure `setup_logging()` was called before logging
3. Verify `logs/` directory is writable
4. Check that `console=True` if expecting stdout output

### Issue: Multiple log entries (duplicates)
**Symptoms**: Each log message appears multiple times

**Solution**:
1. Ensure `setup_logging()` is called only once
2. Check that handlers aren't being added multiple times
3. The code already calls `root_logger.handlers.clear()` to prevent this

## 📚 Further Reading

- **Python Logging Docs**: https://docs.python.org/3/library/logging.html
- **python-dotenv Docs**: https://github.com/theskumar/python-dotenv
- **Environment Variable Best Practices**: https://12factor.net/config
- **LLM Module**: [src/llm/README.md](../llm/README.md) - Uses config for API keys
- **Crawler Module**: [src/crawler/README.md](../crawler/README.md) - Uses config for timeouts
- **Database Module**: [src/db/README.md](../db/README.md) - Uses config for Supabase
