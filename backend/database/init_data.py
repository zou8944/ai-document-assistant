"""Database initialization with default settings."""

from typing import Any

from sqlalchemy.orm import Session

from repository.settings import SettingsRepository

# Default settings data
DEFAULT_SETTINGS: list[dict[str, Any]] = [
    # LLM settings
    {
        "key": "llm.base_url",
        "value": "https://api.openai.com/v1",
        "value_type": "string",
        "category": "llm",
        "description": "LLM API base URL",
        "is_sensitive": False,
    },
    {
        "key": "llm.chat_model",
        "value": "gpt-4o",
        "value_type": "string",
        "category": "llm",
        "description": "Chat model name",
        "is_sensitive": False,
    },
    {
        "key": "llm.api_key",
        "value": "",
        "value_type": "string",
        "category": "llm",
        "description": "LLM API key",
        "is_sensitive": True,
    },
    {
        "key": "llm.temperature",
        "value": "0.1",
        "value_type": "number",
        "category": "llm",
        "description": "Model temperature parameter",
        "is_sensitive": False,
    },
    {
        "key": "llm.max_tokens",
        "value": "2048",
        "value_type": "number",
        "category": "llm",
        "description": "Maximum output tokens",
        "is_sensitive": False,
    },

    # Embedding settings
    {
        "key": "embedding.base_url",
        "value": "https://api.openai.com/v1",
        "value_type": "string",
        "category": "embedding",
        "description": "Embedding API base URL",
        "is_sensitive": False,
    },
    {
        "key": "embedding.model",
        "value": "text-embedding-3-small",
        "value_type": "string",
        "category": "embedding",
        "description": "Embedding model name",
        "is_sensitive": False,
    },
    {
        "key": "embedding.api_key",
        "value": "",
        "value_type": "string",
        "category": "embedding",
        "description": "Embedding API key",
        "is_sensitive": True,
    },
    {
        "key": "embedding.dimensions",
        "value": "1536",
        "value_type": "number",
        "category": "embedding",
        "description": "Embedding dimensions",
        "is_sensitive": False,
    },

    # Path settings
    {
        "key": "paths.data_location",
        "value": "./data",
        "value_type": "string",
        "category": "paths",
        "description": "Data storage location",
        "is_sensitive": False,
    },
    {
        "key": "paths.allowed_roots",
        "value": "[]",
        "value_type": "json",
        "category": "paths",
        "description": "Allowed root directories list",
        "is_sensitive": False,
    },

    # Crawler settings
    {
        "key": "crawler.max_concurrent",
        "value": "5",
        "value_type": "number",
        "category": "crawler",
        "description": "Maximum concurrent crawling",
        "is_sensitive": False,
    },
    {
        "key": "crawler.delay_seconds",
        "value": "1.0",
        "value_type": "number",
        "category": "crawler",
        "description": "Crawling delay in seconds",
        "is_sensitive": False,
    },
    {
        "key": "crawler.timeout_seconds",
        "value": "30",
        "value_type": "number",
        "category": "crawler",
        "description": "Request timeout in seconds",
        "is_sensitive": False,
    },
    {
        "key": "crawler.user_agent",
        "value": "AI-Document-Assistant/1.0",
        "value_type": "string",
        "category": "crawler",
        "description": "Crawler user agent",
        "is_sensitive": False,
    },

    # Text processing settings
    {
        "key": "text.chunk_size",
        "value": "1000",
        "value_type": "number",
        "category": "general",
        "description": "Text chunk size",
        "is_sensitive": False,
    },
    {
        "key": "text.chunk_overlap",
        "value": "200",
        "value_type": "number",
        "category": "general",
        "description": "Text chunk overlap",
        "is_sensitive": False,
    },
    {
        "key": "text.max_file_size_mb",
        "value": "50",
        "value_type": "number",
        "category": "general",
        "description": "Maximum file size in MB",
        "is_sensitive": False,
    },
]


def initialize_default_settings(session: Session) -> None:
    """
    Initialize default settings in the database.

    Args:
        session: Database session
    """
    settings_repo = SettingsRepository(session)
    settings_repo.initialize_defaults(DEFAULT_SETTINGS)


def get_default_settings() -> list[dict[str, Any]]:
    """
    Get the default settings list.

    Returns:
        list of default setting dictionaries
    """
    return DEFAULT_SETTINGS.copy()
