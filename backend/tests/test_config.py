"""
Tests for config module.
"""

import pytest

from config import Config


class TestConfig:

    def test_config_creation_with_defaults(self):
        """Test creating config with default values"""
        config = Config()

        assert config.openai_chat_model == "gpt-3.5-turbo"
        assert config.embedding_model == "text-embedding-ada-002"
        assert config.qdrant_host == "localhost"
        assert config.qdrant_port == 6334
        assert config.max_file_size_mb == 50.0
        assert config.chunk_size == 1000
        assert config.chunk_overlap == 200
        assert config.log_level == "INFO"

    def test_config_creation_with_custom_values(self):
        """Test creating config with custom values"""
        config = Config(
            openai_api_key="test-key",
            openai_api_base="https://test-api.com/v1",
            openai_chat_model="custom-chat-model",
            embedding_model="custom-embedding-model",
            max_file_size_mb=25.0,
            chunk_size=500,
            chunk_overlap=100
        )

        assert config.openai_api_key == "test-key"
        assert config.openai_api_base == "https://test-api.com/v1"
        assert config.openai_chat_model == "custom-chat-model"
        assert config.embedding_model == "custom-embedding-model"
        assert config.max_file_size_mb == 25.0
        assert config.chunk_size == 500
        assert config.chunk_overlap == 100

    def test_config_from_env(self, monkeypatch):
        """Test creating config from environment variables"""
        # Set test environment variables
        monkeypatch.setenv("OPENAI_API_KEY", "env-test-key")
        monkeypatch.setenv("OPENAI_API_BASE", "https://env-api.com/v1")
        monkeypatch.setenv("OPENAI_CHAT_MODEL", "env-chat-model")
        monkeypatch.setenv("EMBEDDING_MODEL", "env-embedding-model")
        monkeypatch.setenv("MAX_FILE_SIZE_MB", "30.0")
        monkeypatch.setenv("CHUNK_SIZE", "800")
        monkeypatch.setenv("CHUNK_OVERLAP", "150")
        monkeypatch.setenv("QDRANT_HOST", "env-qdrant-host")
        monkeypatch.setenv("QDRANT_PORT", "7777")

        config = Config.from_env()

        assert config.openai_api_key == "env-test-key"
        assert config.openai_api_base == "https://env-api.com/v1"
        assert config.openai_chat_model == "env-chat-model"
        assert config.embedding_model == "env-embedding-model"
        assert config.max_file_size_mb == 30.0
        assert config.chunk_size == 800
        assert config.chunk_overlap == 150
        assert config.qdrant_host == "env-qdrant-host"
        assert config.qdrant_port == 7777

    def test_config_validation_success(self):
        """Test successful config validation"""
        config = Config(openai_api_key="valid-key")

        # Should not raise any exception
        config.validate()

    def test_config_validation_no_api_key(self):
        """Test config validation fails without API key"""
        config = Config()  # No API keys set

        with pytest.raises(ValueError, match="Either OPENAI_API_KEY or EMBEDDING_API_KEY must be set"):
            config.validate()

    def test_config_validation_invalid_port(self):
        """Test config validation fails with invalid port"""
        config = Config(openai_api_key="test-key", qdrant_port=-1)

        with pytest.raises(ValueError, match="QDRANT_PORT must be a positive integer"):
            config.validate()

    def test_config_validation_invalid_file_size(self):
        """Test config validation fails with invalid file size"""
        config = Config(openai_api_key="test-key", max_file_size_mb=-1.0)

        with pytest.raises(ValueError, match="MAX_FILE_SIZE_MB must be positive"):
            config.validate()

    def test_config_validation_invalid_chunk_overlap(self):
        """Test config validation fails when chunk overlap >= chunk size"""
        config = Config(
            openai_api_key="test-key",
            chunk_size=100,
            chunk_overlap=100  # Equal to chunk size
        )

        with pytest.raises(ValueError, match="CHUNK_OVERLAP must be less than CHUNK_SIZE"):
            config.validate()

    def test_get_openai_embeddings_kwargs_basic(self):
        """Test getting OpenAI embeddings kwargs with basic config"""
        config = Config(
            openai_api_key="test-key",
            embedding_model="test-embedding-model"
        )

        kwargs = config.get_openai_embeddings_kwargs()

        assert kwargs["model"] == "test-embedding-model"
        assert kwargs["api_key"] == "test-key"
        assert "base_url" not in kwargs

    def test_get_openai_embeddings_kwargs_with_base_url(self):
        """Test getting OpenAI embeddings kwargs with base URL"""
        config = Config(
            openai_api_key="test-key",
            openai_api_base="https://test-api.com/v1",
            embedding_model="test-embedding-model"
        )

        kwargs = config.get_openai_embeddings_kwargs()

        assert kwargs["model"] == "test-embedding-model"
        assert kwargs["api_key"] == "test-key"
        assert kwargs["base_url"] == "https://test-api.com/v1"

    def test_get_openai_embeddings_kwargs_separate_config(self):
        """Test getting OpenAI embeddings kwargs with separate embedding config"""
        config = Config(
            openai_api_key="chat-key",
            openai_api_base="https://chat-api.com/v1",
            embedding_api_key="embedding-key",
            embedding_api_base="https://embedding-api.com/v1",
            embedding_model="custom-embedding-model"
        )

        kwargs = config.get_openai_embeddings_kwargs()

        assert kwargs["model"] == "custom-embedding-model"
        assert kwargs["api_key"] == "embedding-key"  # Uses embedding-specific key
        assert kwargs["base_url"] == "https://embedding-api.com/v1"  # Uses embedding-specific URL

    def test_get_openai_embeddings_kwargs_fallback(self):
        """Test getting OpenAI embeddings kwargs with fallback to chat config"""
        config = Config(
            openai_api_key="chat-key",
            openai_api_base="https://chat-api.com/v1",
            embedding_model="custom-embedding-model"
            # No embedding-specific config
        )

        kwargs = config.get_openai_embeddings_kwargs()

        assert kwargs["model"] == "custom-embedding-model"
        assert kwargs["api_key"] == "chat-key"  # Fallback to chat key
        assert kwargs["base_url"] == "https://chat-api.com/v1"  # Fallback to chat URL

    def test_get_openai_chat_kwargs_basic(self):
        """Test getting OpenAI chat kwargs"""
        config = Config(
            openai_api_key="test-key",
            openai_chat_model="test-chat-model"
        )

        kwargs = config.get_openai_chat_kwargs()

        assert kwargs["model"] == "test-chat-model"
        assert kwargs["api_key"] == "test-key"
        assert kwargs["temperature"] == 0.1
        assert "base_url" not in kwargs

    def test_get_openai_chat_kwargs_with_base_url(self):
        """Test getting OpenAI chat kwargs with base URL"""
        config = Config(
            openai_api_key="test-key",
            openai_api_base="https://test-api.com/v1",
            openai_chat_model="test-chat-model"
        )

        kwargs = config.get_openai_chat_kwargs()

        assert kwargs["model"] == "test-chat-model"
        assert kwargs["api_key"] == "test-key"
        assert kwargs["base_url"] == "https://test-api.com/v1"
        assert kwargs["temperature"] == 0.1

    def test_get_config_info(self):
        """Test getting configuration information"""
        config = Config(
            openai_api_key="chat-key",
            openai_api_base="https://chat-api.com/v1",
            openai_chat_model="chat-model",
            embedding_api_key="embedding-key",
            embedding_api_base="https://embedding-api.com/v1",
            embedding_model="embedding-model",
            qdrant_host="test-host",
            qdrant_port=7777
        )

        info = config.get_config_info()

        # Chat config
        assert info["chat_config"]["api_base"] == "https://chat-api.com/v1"
        assert info["chat_config"]["model"] == "chat-model"
        assert info["chat_config"]["has_api_key"] is True

        # Embedding config
        assert info["embedding_config"]["api_base"] == "https://embedding-api.com/v1"
        assert info["embedding_config"]["model"] == "embedding-model"
        assert info["embedding_config"]["has_api_key"] is True
        assert info["embedding_config"]["using_fallback"] is False

        # Qdrant config
        assert info["qdrant"]["host"] == "test-host"
        assert info["qdrant"]["port"] == 7777

    def test_get_config_info_fallback(self):
        """Test getting configuration information with fallback"""
        config = Config(
            openai_api_key="chat-key",
            openai_api_base="https://chat-api.com/v1",
            embedding_model="embedding-model"
            # No embedding-specific config
        )

        info = config.get_config_info()

        # Embedding should fallback to chat config
        assert info["embedding_config"]["api_base"] == "https://chat-api.com/v1"
        assert info["embedding_config"]["using_fallback"] is True
