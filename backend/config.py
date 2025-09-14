"""
Configuration management for AI Document Assistant Backend.
Centralized configuration handling with environment variable support.
"""

import os
from dataclasses import dataclass
from typing import Optional

import dotenv


@dataclass
class Config:
    """Central configuration class for the backend application"""

    # Chat Model Configuration
    openai_api_key: Optional[str] = None
    openai_api_base: Optional[str] = None
    openai_chat_model: str = "gpt-3.5-turbo"

    # Embedding Model Configuration (fallback to chat config if not set)
    embedding_api_key: Optional[str] = None
    embedding_api_base: Optional[str] = None
    embedding_model: str = "text-embedding-ada-002"

    # ChromaDB Configuration
    chroma_persist_directory: str = "./chroma_db"

    # File Processing Configuration
    max_file_size_mb: float = 50.0

    # Text Processing Configuration
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # Web Crawling Configuration
    crawler_cache_dir: str = "data/crawler_cache"
    crawler_max_depth: int = 0
    crawler_delay: float = 1.0
    crawler_max_pages: int = 1000

    # Application Configuration
    log_level: str = "DEBUG"

    @classmethod
    def from_env(cls) -> 'Config':
        """Create Config instance from environment variables"""
        dotenv.load_dotenv() # Load .env file if present
        return cls(
            # Chat Model Configuration
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_api_base=os.getenv("OPENAI_API_BASE"),
            openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-3.5-turbo"),

            # Embedding Model Configuration
            embedding_api_key=os.getenv("EMBEDDING_API_KEY"),
            embedding_api_base=os.getenv("EMBEDDING_API_BASE"),
            embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),

            # ChromaDB Configuration
            chroma_persist_directory=os.getenv("CHROMA_PERSIST_DIRECTORY", "./chroma_db"),

            # File Processing Configuration
            max_file_size_mb=float(os.getenv("MAX_FILE_SIZE_MB", "50.0")),

            # Text Processing Configuration
            chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
            chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),

            # Web Crawling Configuration
            crawler_max_depth=int(os.getenv("CRAWLER_MAX_DEPTH", "0")),
            crawler_delay=float(os.getenv("CRAWLER_DELAY", "1.0")),
            crawler_max_pages=int(os.getenv("CRAWLER_MAX_PAGES", "1000")),

            # Application Configuration
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )

    def validate(self) -> None:
        """Validate configuration values"""
        # At least one API key must be set (for chat or embedding)
        if not self.openai_api_key and not self.embedding_api_key:
            raise ValueError("Either OPENAI_API_KEY or EMBEDDING_API_KEY must be set")

        # If embedding config is partial, ensure fallback is available
        if (self.embedding_api_key or self.embedding_api_base) and not self.openai_api_key and not self.embedding_api_key:
            raise ValueError("When using custom embedding config, ensure API keys are properly set")

        if not self.chroma_persist_directory:
            raise ValueError("CHROMA_PERSIST_DIRECTORY must be set")

        if self.max_file_size_mb <= 0:
            raise ValueError("MAX_FILE_SIZE_MB must be positive")

        if self.chunk_size <= 0:
            raise ValueError("CHUNK_SIZE must be positive")

        if self.chunk_overlap < 0:
            raise ValueError("CHUNK_OVERLAP must be non-negative")

        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_SIZE")

    def get_openai_embeddings_kwargs(self) -> dict:
        """Get kwargs for OpenAIEmbeddings initialization with fallback to chat config"""
        kwargs = {
            "model": self.embedding_model
        }

        # Use embedding-specific config if available, otherwise fallback to chat config
        api_key = self.embedding_api_key or self.openai_api_key
        api_base = self.embedding_api_base or self.openai_api_base

        if api_key:
            kwargs["api_key"] = api_key

        if api_base:
            kwargs["base_url"] = api_base

        return kwargs

    def get_openai_chat_kwargs(self) -> dict:
        """Get kwargs for ChatOpenAI initialization"""
        kwargs = {
            "model": self.openai_chat_model,
            "temperature": 0.1  # Low temperature for factual answers
        }

        if self.openai_api_key:
            kwargs["api_key"] = self.openai_api_key

        if self.openai_api_base:
            kwargs["base_url"] = self.openai_api_base

        return kwargs

    def get_config_info(self) -> dict:
        """Get current configuration information for debugging"""
        return {
            "chat_config": {
                "api_base": self.openai_api_base or "https://api.openai.com/v1",
                "model": self.openai_chat_model,
                "has_api_key": bool(self.openai_api_key)
            },
            "embedding_config": {
                "api_base": self.embedding_api_base or self.openai_api_base or "https://api.openai.com/v1",
                "model": self.embedding_model,
                "has_api_key": bool(self.embedding_api_key or self.openai_api_key),
                "using_fallback": not bool(self.embedding_api_key or self.embedding_api_base)
            },
            "chromadb": {
                "persist_directory": self.chroma_persist_directory
            }
        }


# Global config instance
config: Optional[Config] = None


def get_config() -> Config:
    """Get the global config instance"""
    global config
    if config is None:
        config = Config.from_env()
    return config


def init_config() -> Config:
    """Initialize global config from environment variables"""
    global config
    config = Config.from_env()
    return config
