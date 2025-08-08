"""
Qdrant vector store client wrapper for managing document embeddings.
Following 2024 best practices for LangChain integration.
"""

import logging
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    """Document chunk with metadata for vector storage"""
    id: str
    content: str
    source: str
    start_index: int
    metadata: dict[str, Any] = {}


class QdrantManager:
    """
    Qdrant vector database manager with connection management and error handling.
    Optimized for AI document assistant use case.
    """

    def __init__(self, host: str = "localhost", port: int = 6334):
        """Initialize Qdrant client with gRPC preference for better performance"""
        try:
            # PATTERN: Use prefer_grpc for better performance
            self.client = QdrantClient(host=host, port=port, prefer_grpc=True)
            logger.info(f"Connected to Qdrant at {host}:{port}")
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant: {e}")
            raise

    async def ensure_collection(self, collection_name: str, vector_size: int = 384) -> bool:
        """
        Ensure collection exists, create if not found.

        Args:
            collection_name: Name of the collection
            vector_size: Dimension of embedding vectors (default 384 for all-MiniLM-L6-v2)

        Returns:
            True if collection exists or was created successfully
        """
        try:
            # GOTCHA: Check if collection exists before creating
            collections = self.client.get_collections()
            existing_names = [c.name for c in collections.collections]

            if collection_name in existing_names:
                logger.info(f"Collection '{collection_name}' already exists")
                return True

            # PATTERN: Use COSINE distance for text embeddings
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )

            logger.info(f"Created collection '{collection_name}' with vector size {vector_size}")
            return True

        except Exception as e:
            logger.error(f"Failed to ensure collection '{collection_name}': {e}")
            return False

    async def index_documents(self, collection_name: str, chunks: list[DocumentChunk],
                            embeddings: list[list[float]]) -> dict[str, Any]:
        """
        Index document chunks with their embeddings.

        Args:
            collection_name: Target collection name
            chunks: list of document chunks
            embeddings: Corresponding embeddings for each chunk

        Returns:
            Status dictionary with success/error information
        """
        try:
            if len(chunks) != len(embeddings):
                raise ValueError("Number of chunks must match number of embeddings")

            # Prepare points for insertion
            points = []
            for chunk, embedding in zip(chunks, embeddings):
                point = PointStruct(
                    id=chunk.id or str(uuid4()),
                    vector=embedding,
                    payload={
                        "content": chunk.content,
                        "source": chunk.source,
                        "start_index": chunk.start_index,
                        "metadata": chunk.metadata
                    }
                )
                points.append(point)

            # Batch insert points
            operation_info = self.client.upsert(
                collection_name=collection_name,
                points=points
            )

            logger.info(f"Indexed {len(points)} documents in collection '{collection_name}'")

            return {
                "status": "success",
                "indexed_count": len(points),
                "operation_info": operation_info
            }

        except Exception as e:
            logger.error(f"Failed to index documents: {e}")
            return {
                "status": "error",
                "message": str(e),
                "indexed_count": 0
            }

    async def search_similar(self, collection_name: str, query_embedding: list[float],
                           limit: int = 5, score_threshold: float = 0.5) -> list[dict[str, Any]]:
        """
        Search for similar documents using vector similarity.

        Args:
            collection_name: Collection to search in
            query_embedding: Query vector
            limit: Maximum number of results
            score_threshold: Minimum similarity score

        Returns:
            list of similar documents with scores
        """
        try:
            results = self.client.search(
                collection_name=collection_name,
                query_vector=query_embedding,
                limit=limit,
                score_threshold=score_threshold
            )

            # Format results
            formatted_results = []
            for result in results:
                payload = result.payload or {}
                formatted_results.append({
                    "id": result.id,
                    "score": result.score,
                    "content": payload.get("content", ""),
                    "source": payload.get("source", ""),
                    "start_index": payload.get("start_index", 0),
                    "metadata": payload.get("metadata", {})
                })

            logger.info(f"Found {len(formatted_results)} similar documents")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection and all its data"""
        try:
            self.client.delete_collection(collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False

    async def get_collection_info(self, collection_name: str) -> Optional[dict[str, Any]]:
        """Get information about a collection"""
        try:
            info = self.client.get_collection(collection_name)
            return {
                "name": collection_name,
                "vectors_count": info.vectors_count,
                "status": info.status,
                "config": {
                    "distance": info.config.params.vectors.distance.value,
                    "size": info.config.params.vectors.size
                }
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None

    def close(self):
        """Close the Qdrant client connection"""
        try:
            self.client.close()
            logger.info("Closed Qdrant connection")
        except Exception as e:
            logger.error(f"Error closing Qdrant connection: {e}")


# Convenience function for creating manager instance
def create_qdrant_manager(host: str = "localhost", port: int = 6334) -> QdrantManager:
    """Create and return a QdrantManager instance"""
    return QdrantManager(host=host, port=port)
