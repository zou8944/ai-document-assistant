"""Configuration data classes for TOML-based configuration."""

import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

import toml


@dataclass
class LLMEndpointConfig:
    """LLM endpoint configuration for a specific purpose."""

    provider: str = "openai"  # openai | anthropic
    api_key: str = ""
    base_url: str = ""
    model: str = ""

    def validate(self, supported_providers: list[str] | None = None) -> None:
        """Validate endpoint configuration."""
        if not self.provider:
            raise ValueError("Provider must be set")
        if not self.api_key:
            raise ValueError(f"{self.provider} API key must be set")
        if not self.model:
            raise ValueError("Model must be set")
        if supported_providers and self.provider not in supported_providers:
            raise ValueError(
                f"Unsupported provider '{self.provider}'. "
                f"Supported: {', '.join(supported_providers)}"
            )

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict):
        return cls(**data)


@dataclass
class LLMConfig:
    crawl: LLMEndpointConfig = field(default_factory=LLMEndpointConfig)
    agent: LLMEndpointConfig = field(
        default_factory=lambda: LLMEndpointConfig(
            provider="anthropic",
            model="claude-sonnet-4-20250514",
        )
    )
    max_tokens: Optional[int] = 8192

    def to_dict(self) -> dict:
        return {
            "crawl": self.crawl.to_dict(),
            "agent": self.agent.to_dict(),
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            crawl=LLMEndpointConfig.from_dict(data.get("crawl", {})),
            agent=LLMEndpointConfig.from_dict(data.get("agent", {})),
            max_tokens=data.get("max_tokens", 8192),
        )

    @classmethod
    def from_env(cls):
        """Load configuration from environment variables."""
        return cls(
            crawl=LLMEndpointConfig(
                provider=os.getenv("CRAWL_PROVIDER", "openai"),
                api_key=os.getenv("CRAWL_API_KEY", ""),
                base_url=os.getenv("CRAWL_BASE_URL", ""),
                model=os.getenv("CRAWL_MODEL", "gpt-4o"),
            ),
            agent=LLMEndpointConfig(
                provider=os.getenv("AGENT_PROVIDER", "anthropic"),
                api_key=os.getenv("AGENT_API_KEY", ""),
                base_url=os.getenv("AGENT_BASE_URL", ""),
                model=os.getenv("AGENT_MODEL", "claude-sonnet-4-20250514"),
            ),
            max_tokens=int(os.getenv("LLM_MAX_TOKENS", "8192"))
            if os.getenv("LLM_MAX_TOKENS")
            else 8192,
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
            api_key=os.getenv("EMBEDDING_API_KEY", ""),
            base_url=os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1"),
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

    max_iterations: int = 500
    context_window: int = 200_000
    compact_threshold: float = 0.8
    keep_recent_tool_results: int = 2
    transcript_dir: str = field(
        default_factory=lambda: str(AppConfig.get_transcript_dir())
    )
    model: str = "standard"  # frontend display label

    # Loop detector configuration
    loop_detector_enabled: bool = True
    loop_max_consecutive_failures: int = 3
    loop_similar_call_window: int = 5
    loop_similar_call_threshold: int = 2
    loop_stagnation_window: int = 4

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
            system=SystemConfig.from_dict(data.get("system", {})),
            agent=AgentConfig.from_dict(data.get("agent", {})),
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
    def get_transcript_dir(cls) -> Path:
        return cls.get_user_config_dir() / "agent_transcripts"

    @classmethod
    def get_chroma_dir(cls) -> Path:
        return cls.get_user_config_dir() / "chroma_db"

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
            llm=LLMConfig.from_dict(data.get("llm", {})),
            embedding=EmbeddingConfig.from_dict(data.get("embedding", {})),
            knowledge_base=KnowledgeBaseConfig.from_dict(data.get("knowledge_base", {})),
            system=SystemConfig.from_dict(data.get("system", {})),
            agent=AgentConfig.from_dict(data.get("agent", {})),
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
            self.get_transcript_dir(),
        ]

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def get_openai_embeddings_kwargs(self) -> dict:
        """Get kwargs for OpenAIEmbeddings initialization."""
        return {
            "model": self.embedding.model,
            "api_key": self.embedding.api_key,
            "base_url": self.embedding.base_url,
        }

    def validate(self) -> None:
        """Validate configuration values."""
        # Validate agent provider (currently only anthropic is supported)
        self.llm.agent.validate(supported_providers=["anthropic"])

        # Validate crawl provider (currently only openai is supported)
        self.llm.crawl.validate(supported_providers=["openai"])

        # Validate embedding configuration (required, no fallback)
        if not self.embedding.api_key:
            raise ValueError("Embedding API key must be set")
        if not self.embedding.base_url:
            raise ValueError("Embedding base URL must be set")

        if self.knowledge_base.max_file_size_mb <= 0:
            raise ValueError("max_file_size_mb must be positive")
