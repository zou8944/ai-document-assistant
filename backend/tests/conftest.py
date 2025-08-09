"""
Pytest configuration and fixtures for backend tests.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# Test fixtures
@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests"""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)

@pytest.fixture
def sample_text_file(temp_dir):
    """Create a sample text file for testing"""
    file_path = temp_dir / "sample.txt"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("This is a sample text file for testing.\n")
        f.write("It contains multiple lines of text.\n")
        f.write("This helps test document processing functionality.")
    return str(file_path)

@pytest.fixture
def sample_markdown_file(temp_dir):
    """Create a sample markdown file for testing"""
    file_path = temp_dir / "sample.md"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Sample Markdown\n\n")
        f.write("This is a **sample** markdown file.\n\n")
        f.write("## Features\n\n")
        f.write("- Item 1\n")
        f.write("- Item 2\n")
    return str(file_path)

@pytest.fixture
def mock_embeddings():
    """Mock embeddings for testing"""
    mock = MagicMock()
    mock.aembed_documents = AsyncMock(return_value=[
        [0.1, 0.2, 0.3] * 128,  # 384-dimensional embedding
        [0.4, 0.5, 0.6] * 128,
    ])
    mock.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3] * 128)
    return mock

@pytest.fixture
def mock_qdrant_client():
    """Mock Qdrant client for testing"""
    mock = MagicMock()
    mock.get_collections = MagicMock()
    mock.get_collections.return_value.collections = []
    mock.create_collection = MagicMock()
    mock.upsert = MagicMock()
    mock.search = MagicMock(return_value=[])
    mock.close = MagicMock()
    return mock

@pytest.fixture
def sample_documents():
    """Sample documents for testing"""
    return [
        {
            "id": "doc1",
            "content": "This is the first test document. It contains information about testing.",
            "source": "test1.txt",
            "start_index": 0,
            "metadata": {"type": "test"}
        },
        {
            "id": "doc2",
            "content": "This is the second test document. It has different content for variety.",
            "source": "test2.txt",
            "start_index": 100,
            "metadata": {"type": "test"}
        }
    ]

# Test environment setup
@pytest.fixture(autouse=True)
def setup_test_env():
    """Setup test environment variables"""
    # Disable API key requirements for testing
    os.environ["OPENAI_API_KEY"] = "test-key"
    yield
    # Cleanup
    if "OPENAI_API_KEY" in os.environ and os.environ["OPENAI_API_KEY"] == "test-key":
        del os.environ["OPENAI_API_KEY"]

# Config fixtures
@pytest.fixture
def test_config():
    """Test configuration instance"""
    from config import Config
    return Config(
        openai_api_key="test-api-key",
        openai_api_base="https://test-api.com/v1",
        openai_chat_model="test-chat-model",
        embedding_model="test-embedding-model",
        max_file_size_mb=25.0,
        chunk_size=500,
        chunk_overlap=100,
        qdrant_host="test-qdrant",
        qdrant_port=6333
    )

# Async test support - removed custom event_loop fixture to avoid deprecation warning
# pytest-asyncio will handle event loop creation automatically
