"""Configuration data classes for TOML-based configuration."""

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import toml


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-3.5-turbo"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class EmbeddingConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "text-embedding-ada-002"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class KnowledgeBaseConfig:
    max_crawl_pages: int = 1000
    max_file_size_mb: int = 10

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class SystemConfig:
    log_level: str = "info"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class AppConfig:
    """Complete application configuration."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    embedding: EmbeddingConfig = field(default_factory=EmbeddingConfig)
    knowledge_base: KnowledgeBaseConfig = field(default_factory=KnowledgeBaseConfig)
    system: SystemConfig = field(default_factory=SystemConfig)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "AppConfig":
        return cls(
            llm=LLMConfig.from_dict(data.get("llm", {})),
            embedding=EmbeddingConfig.from_dict(data.get("embedding", {})),
            knowledge_base=KnowledgeBaseConfig.from_dict(data.get("knowledge_base", {})),
            system=SystemConfig.from_dict(data.get("system", {}))
        )

    @classmethod
    def get_user_config_dir(cls) -> Path:
        return Path.home() / ".ai-document-assistant"

    @classmethod
    def get_config_file_path(cls) -> Path:
        return cls.get_user_config_dir() / "config.toml"

    @classmethod
    def get_app_db_path(cls) -> Path:
        return cls.get_user_config_dir() / "app.db"

    @classmethod
    def get_chroma_db_path(cls) -> Path:
        return cls.get_user_config_dir() / "chroma.db"

    @classmethod
    def get_crawl_cache_dir(cls) -> Path:
        return cls.get_user_config_dir() / "crawl-cache"

    @classmethod
    def get_log_file_path(cls) -> Path:
        return cls.get_user_config_dir() / "backend.log"

    @classmethod
    def from_toml_file(cls, file_path: Optional[Path] = None) -> "AppConfig":
        if file_path is None:
            file_path = cls.get_config_file_path()

        if not file_path.exists():
            # Return default configuration if file doesn't exist
            return cls()

        with open(file_path, encoding="utf-8") as f:
            data = toml.load(f)

        return cls(
            llm=LLMConfig(**data.get("llm", {})),
            embedding=EmbeddingConfig(**data.get("embedding", {})),
            knowledge_base=KnowledgeBaseConfig(**data.get("knowledge_base", {})),
            system=SystemConfig(**data.get("system", {}))
        )

    def to_toml_file(self, file_path: Optional[Path] = None) -> None:
        if file_path is None:
            file_path = self.get_config_file_path()

        # Ensure directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Convert to dictionary
        config_dict = self.to_dict()

        with open(file_path, "w", encoding="utf-8") as f:
            toml.dump(config_dict, f)

    def ensure_directories_exist(self) -> None:
        """Ensure all necessary directories exist."""
        directories = [
            self.get_user_config_dir(),
            self.get_crawl_cache_dir(),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_openai_chat_kwargs(self) -> dict:
        """Get kwargs for ChatOpenAI initialization."""
        kwargs = {
            "model": self.llm.chat_model,
            "temperature": 0.1,
            "api_key": self.llm.api_key,
            "base_url": self.llm.base_url,
        }
        return kwargs

    def get_openai_embeddings_kwargs(self) -> dict:
        """Get kwargs for OpenAIEmbeddings initialization."""
        kwargs = {
            "model": self.embedding.model,
            "api_key": self.embedding.api_key or self.llm.api_key,
            "base_url": self.embedding.base_url or self.llm.base_url,
        }
        return kwargs

    def validate(self) -> None:
        """Validate configuration values."""
        # At least one API key must be set
        if not self.llm.api_key:
            raise ValueError("LLM API key must be set")

        if self.knowledge_base.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")

        if self.knowledge_base.max_crawl_pages <= 0:
            raise ValueError("max_crawl_pages must be positive")
