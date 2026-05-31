"""
Configuration management for AI Document Assistant Backend.
TOML-based configuration with automatic initialization.
Supports both TOML file configuration and environment variables (Docker-friendly).
"""

import os
from typing import Optional

from models.config import (
    AppConfig,
    EmbeddingConfig,
    KnowledgeBaseConfig,
    LLMConfig,
    LLMEndpointConfig,
    SystemConfig,
)

# Fixed paths and configuration
DATA_DIR_PATH = AppConfig.get_user_config_dir()
CONFIG_FILE_PATH = AppConfig.get_config_file_path()
CRAWL_CACHE_DIR = AppConfig.get_crawl_cache_dir()
TRANSCRIPT_DIR = AppConfig.get_transcript_dir()
CHROMA_DIR = AppConfig.get_chroma_dir()
LOG_FILE_PATH = AppConfig.get_log_file_path()

# Global config instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get current configuration. Priority: environment variables > config file > defaults."""
    # If running in Docker or key env vars are set, use env config
    if os.getenv("DOCKER_ENV") or os.getenv("CRAWL_API_KEY"):
        config = AppConfig.from_env()
        config.ensure_directories_exist()
        return config

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


def load_config_from_db() -> AppConfig:
    """Build AppConfig from database settings table.

    Falls back to defaults when a setting is missing.
    """
    from settings_util import get_setting_typed

    def _s(key: str, default: str = "") -> str:
        val = get_setting_typed(key)
        return val if val is not None else default

    def _n(key: str, default: int | float = 0) -> int | float:
        val = get_setting_typed(key)
        return val if val is not None else default

    # Determine embedding API key: use CRAWL_API_KEY as fallback
    embedding_key = _s("EMBEDDING_API_KEY") or _s("CRAWL_API_KEY")

    config = AppConfig(
        llm=LLMConfig(
            crawl=LLMEndpointConfig(
                provider=_s("CRAWL_PROVIDER", "openai"),
                api_key=_s("CRAWL_API_KEY"),
                base_url=_s("CRAWL_BASE_URL"),
                model=_s("CRAWL_MODEL"),
            ),
            agent=LLMEndpointConfig(
                provider=_s("AGENT_PROVIDER", "anthropic"),
                api_key=_s("AGENT_API_KEY"),
                base_url=_s("AGENT_BASE_URL"),
                model=_s("AGENT_MODEL"),
            ),
            max_tokens=int(_n("LLM_MAX_TOKENS", 8192)),
        ),
        embedding=EmbeddingConfig(
            api_key=embedding_key,
            base_url=_s("EMBEDDING_BASE_URL"),
            model=_s("EMBEDDING_MODEL"),
        ),
        knowledge_base=KnowledgeBaseConfig(
            max_file_size_mb=int(_n("MAX_FILE_SIZE_MB", 10)),
            max_crawl_pages=int(_n("MAX_CRAWL_PAGES", 1000)),
        ),
        system=SystemConfig(
            log_level=_s("LOG_LEVEL", "info"),
        ),
    )

    config.ensure_directories_exist()
    return config

