"""
Tests for qdrant_client module.
"""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from vector_store.qdrant_client import QdrantManager, DocumentChunk, create_qdrant_manager

class TestQdrantManager:
    
    def test_create_qdrant_manager(self):
        """Test Qdrant manager creation"""
        with patch('vector_store.qdrant_client.QdrantClient') as mock_client:
            manager = create_qdrant_manager()
            assert isinstance(manager, QdrantManager)
            mock_client.assert_called_once_with(host="localhost", port=6334, prefer_grpc=True)
    
    @patch('vector_store.qdrant_client.QdrantClient')
    def test_qdrant_manager_init(self, mock_client_class):
        """Test QdrantManager initialization"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        manager = QdrantManager(host="test-host", port=1234)
        
        mock_client_class.assert_called_once_with(host="test-host", port=1234, prefer_grpc=True)
        assert manager.client == mock_client
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_ensure_collection_new(self, mock_client_class):
        """Test ensuring a new collection is created"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock no existing collections
        mock_collections = MagicMock()
        mock_collections.collections = []
        mock_client.get_collections.return_value = mock_collections
        
        manager = QdrantManager()
        result = await manager.ensure_collection("test_collection", 384)
        
        assert result is True
        mock_client.get_collections.assert_called_once()
        mock_client.create_collection.assert_called_once()
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_ensure_collection_exists(self, mock_client_class):
        """Test ensuring collection when it already exists"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock existing collection
        mock_collection = MagicMock()
        mock_collection.name = "test_collection"
        mock_collections = MagicMock()
        mock_collections.collections = [mock_collection]
        mock_client.get_collections.return_value = mock_collections
        
        manager = QdrantManager()
        result = await manager.ensure_collection("test_collection", 384)
        
        assert result is True
        mock_client.get_collections.assert_called_once()
        mock_client.create_collection.assert_not_called()
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_index_documents_success(self, mock_client_class, sample_documents):
        """Test successful document indexing"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Create DocumentChunk objects
        chunks = [
            DocumentChunk(
                id=doc["id"],
                content=doc["content"],
                source=doc["source"],
                start_index=doc["start_index"],
                metadata=doc["metadata"]
            )
            for doc in sample_documents
        ]
        
        embeddings = [[0.1, 0.2, 0.3] * 128, [0.4, 0.5, 0.6] * 128]
        
        # Mock successful upsert
        mock_operation_info = MagicMock()
        mock_client.upsert.return_value = mock_operation_info
        
        manager = QdrantManager()
        result = await manager.index_documents("test_collection", chunks, embeddings)
        
        assert result["status"] == "success"
        assert result["indexed_count"] == 2
        mock_client.upsert.assert_called_once()
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_index_documents_mismatch(self, mock_client_class):
        """Test document indexing with mismatched chunks and embeddings"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        chunks = [DocumentChunk(id="1", content="test", source="test", start_index=0)]
        embeddings = [[0.1, 0.2], [0.3, 0.4]]  # More embeddings than chunks
        
        manager = QdrantManager()
        result = await manager.index_documents("test_collection", chunks, embeddings)
        
        assert result["status"] == "error"
        assert "must match" in result["message"]
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_search_similar_success(self, mock_client_class):
        """Test successful similarity search"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock search results
        mock_result1 = MagicMock()
        mock_result1.id = "doc1"
        mock_result1.score = 0.9
        mock_result1.payload = {
            "content": "Test content 1",
            "source": "test1.txt",
            "start_index": 0,
            "metadata": {"type": "test"}
        }
        
        mock_result2 = MagicMock()
        mock_result2.id = "doc2"
        mock_result2.score = 0.7
        mock_result2.payload = {
            "content": "Test content 2", 
            "source": "test2.txt",
            "start_index": 100,
            "metadata": {"type": "test"}
        }
        
        mock_client.search.return_value = [mock_result1, mock_result2]
        
        manager = QdrantManager()
        query_embedding = [0.1, 0.2, 0.3] * 128
        results = await manager.search_similar("test_collection", query_embedding, limit=2)
        
        assert len(results) == 2
        assert results[0]["id"] == "doc1"
        assert results[0]["score"] == 0.9
        assert results[0]["content"] == "Test content 1"
        assert results[1]["id"] == "doc2"
        mock_client.search.assert_called_once()
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_search_similar_empty_results(self, mock_client_class):
        """Test similarity search with no results"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        mock_client.search.return_value = []
        
        manager = QdrantManager()
        query_embedding = [0.1, 0.2, 0.3] * 128
        results = await manager.search_similar("test_collection", query_embedding)
        
        assert len(results) == 0
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_delete_collection_success(self, mock_client_class):
        """Test successful collection deletion"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        manager = QdrantManager()
        result = await manager.delete_collection("test_collection")
        
        assert result is True
        mock_client.delete_collection.assert_called_once_with("test_collection")
    
    @patch('vector_store.qdrant_client.QdrantClient')
    @pytest.mark.asyncio
    async def test_get_collection_info_success(self, mock_client_class):
        """Test getting collection info successfully"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        # Mock collection info
        mock_info = MagicMock()
        mock_info.vectors_count = 100
        mock_info.status = "green"
        mock_info.config.params.vectors.distance.value = "Cosine"
        mock_info.config.params.vectors.size = 384
        mock_client.get_collection.return_value = mock_info
        
        manager = QdrantManager()
        result = await manager.get_collection_info("test_collection")
        
        assert result is not None
        assert result["name"] == "test_collection"
        assert result["vectors_count"] == 100
        assert result["status"] == "green"
        assert result["config"]["distance"] == "Cosine"
        assert result["config"]["size"] == 384
    
    @patch('vector_store.qdrant_client.QdrantClient')
    def test_close_connection(self, mock_client_class):
        """Test closing connection"""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client
        
        manager = QdrantManager()
        manager.close()
        
        mock_client.close.assert_called_once()