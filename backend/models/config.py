"""Configuration data classes for TOML-based configuration."""

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import toml


@dataclass
class LLMConfig:
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    chat_model: str = "gpt-3.5-turbo"
    crawl_model: str = ""
    max_tokens: Optional[int] = 8192

    # Anthropic configuration
    anthropic_api_key: str = ""
    anthropic_base_url: str = ""
    anthropic_chat_model: str = "claude-sonnet-4-20250514"

    # Agent model configuration
    fast_model: str = "gpt-4o-mini"
    deep_model: str = "claude-sonnet-4-20250514"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        max_tokens = os.getenv("OPENAI_MAX_TOKENS", "")
        chat_model = os.getenv("OPENAI_CHAT_MODEL", "gpt-3.5-turbo")
        return cls(
            api_key=os.getenv("OPENAI_API_KEY", ""),
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            chat_model=chat_model,
            crawl_model=os.getenv("OPENAI_CRAWL_MODEL", ""),
            max_tokens=int(max_tokens) if max_tokens else 8192,
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", ""),
            anthropic_chat_model=os.getenv("ANTHROPIC_CHAT_MODEL", "claude-sonnet-4-20250514"),
            fast_model=os.getenv("FAST_MODEL", chat_model),
            deep_model=os.getenv("DEEP_MODEL", "claude-sonnet-4-20250514"),
        )


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

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        return cls(
            api_key=os.getenv("EMBEDDING_API_KEY", os.getenv("OPENAI_API_KEY", "")),
            base_url=os.getenv("EMBEDDING_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")),
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-ada-002"),
        )


@dataclass
class KnowledgeBaseConfig:
    max_file_size_mb: int = 10
    max_crawl_pages: int = 1000

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

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        return cls(
            log_level=os.getenv("LOG_LEVEL", "info"),
        )


@dataclass
class AgentConfig:
    """Agent loop configuration."""

    max_iterations: int = 15
    context_window: int = 200_000
    compact_threshold: float = 0.8
    keep_recent_tool_results: int = 2
    transcript_dir: str = "./var/agent_transcripts"
    model: str = "standard"  # fast | standard | deep

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
    agent: AgentConfig = field(default_factory=AgentConfig)

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
        # In Docker, use /app/data; otherwise use home directory
        docker_data_dir = os.getenv("DATA_DIR", "")
        if docker_data_dir:
            return Path(docker_data_dir)
        return Path.home() / ".ai-document-assistant"

    @classmethod
    def get_config_file_path(cls) -> Path:
        return cls.get_user_config_dir() / "config.toml"

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

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        return cls(
            llm=LLMConfig.from_env(),
            embedding=EmbeddingConfig.from_env(),
            knowledge_base=KnowledgeBaseConfig(),
            system=SystemConfig.from_env(),
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
            "max_tokens": self.llm.max_tokens,
        }
        return kwargs

    def get_openai_crawl_kwargs(self) -> dict:
        """Get kwargs for crawl-phase ChatOpenAI initialization."""
        model = self.llm.crawl_model or self.llm.chat_model
        return {
            "model": model,
            "temperature": 0.1,
            "api_key": self.llm.api_key,
            "base_url": self.llm.base_url,
            "max_tokens": self.llm.max_tokens,
        }

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
