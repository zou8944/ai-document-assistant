"""
Configuration management for AI Document Assistant Backend.
TOML-based configuration with automatic initialization.
"""

from typing import Optional

from models.config import AppConfig

# Fixed paths and configuration
DATA_DIR_PATH = AppConfig.get_user_config_dir()
CONFIG_FILE_PATH = AppConfig.get_config_file_path()
APP_DB_PATH = AppConfig.get_app_db_path()
CHROMA_DB_PATH = AppConfig.get_chroma_db_path()
CRAWL_CACHE_DIR = AppConfig.get_crawl_cache_dir()
LOG_FILE_PATH = AppConfig.get_log_file_path()

# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get current configuration, always reading from file to ensure freshness."""
    # Check if config file exists, create with defaults if not
    if not CONFIG_FILE_PATH.exists():
        default_config = AppConfig()
        default_config.ensure_directories_exist()
        default_config.to_toml_file()
        return default_config
    else:
        config = AppConfig.from_toml_file()
        config.ensure_directories_exist()
        return config


def init_config() -> AppConfig:
    """Initialize configuration from config.toml file. (Deprecated - use get_config instead)"""
    return get_config()


def update_config(config: AppConfig) -> None:
    """Update configuration file with new values."""
    config.ensure_directories_exist()
    config.to_toml_file()

    # Update global cache
    global _config
    _config = config

