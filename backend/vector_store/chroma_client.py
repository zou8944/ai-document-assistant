"""
ChromaDB vector store client wrapper for managing document embeddings.
Following 2024 best practices for LangChain integration.
"""

import logging
import uuid
from typing import Any, Optional

import chromadb
from chromadb.config import Settings
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class DocumentChunk(BaseModel):
    """Document chunk with metadata for vector storage"""
    id: str
    content: str
    source: str
    start_index: int
    metadata: dict[str, Any] = {}


class ChromaManager:
    """
    ChromaDB vector database manager with connection management and error handling.
    Optimized for AI document assistant use case.
    """

    def __init__(self, persist_directory: str = "./chroma_db"):
        """Initialize ChromaDB client with persistent storage"""
        try:
            self.persist_directory = persist_directory
            self.client = chromadb.PersistentClient(
                path=persist_directory,
                settings=Settings(
                    anonymized_telemetry=False,
                    allow_reset=True
                )
            )
            logger.info(f"Connected to ChromaDB at {persist_directory}")
        except Exception as e:
            logger.error(f"Failed to connect to ChromaDB: {e}")
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
            # Try to get existing collection
            try:
                self.client.get_collection(name=collection_name)
                logger.info(f"Collection '{collection_name}' already exists")
                return True
            except ValueError:
                # Collection doesn't exist, create it
                pass

            # Create new collection with cosine distance (default in ChromaDB)
            self.client.create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}  # Use cosine distance for text embeddings
            )

            logger.info(f"Created collection '{collection_name}'")
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

            collection = self.client.get_collection(name=collection_name)

            # Prepare data for insertion
            ids = []
            documents = []
            metadatas = []
            embeddings_list = []

            for chunk, embedding in zip(chunks, embeddings):
                chunk_id = chunk.id or str(uuid.uuid4())
                ids.append(chunk_id)
                documents.append(chunk.content)
                metadatas.append({
                    "source": chunk.source,
                    "start_index": chunk.start_index,
                    **chunk.metadata
                })
                embeddings_list.append(embedding)

            # Upsert documents (add or update)
            collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas,
                embeddings=embeddings_list
            )

            logger.info(f"Indexed {len(chunks)} documents in collection '{collection_name}'")

            return {
                "status": "success",
                "indexed_count": len(chunks),
                "collection_name": collection_name
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
            score_threshold: Minimum similarity score (distance threshold)

        Returns:
            list of similar documents with scores
        """
        try:
            collection = self.client.get_collection(name=collection_name)

            # Query the collection
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                include=["documents", "metadatas", "distances"]
            )

            # Format results
            formatted_results = []
            if results and results["ids"]:
                ids = results["ids"][0]
                documents = results["documents"][0] if results["documents"] else []
                metadatas = results["metadatas"][0] if results["metadatas"] else []
                distances = results["distances"][0] if results["distances"] else []

                for i, doc_id in enumerate(ids):
                    # Convert distance to similarity score (ChromaDB returns distances, not similarities)
                    distance = distances[i] if i < len(distances) else 1.0
                    # For cosine distance, similarity = 1 - distance
                    score = 1.0 - distance

                    # Apply score threshold
                    if score >= score_threshold:
                        metadata = metadatas[i] if i < len(metadatas) else {}
                        formatted_results.append({
                            "id": doc_id,
                            "score": score,
                            "content": documents[i] if i < len(documents) else "",
                            "source": metadata.get("source", ""),
                            "start_index": metadata.get("start_index", 0),
                            "metadata": {k: v for k, v in metadata.items()
                                       if k not in ["source", "start_index"]}
                        })

            logger.info(f"Found {len(formatted_results)} similar documents")
            return formatted_results

        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

    async def delete_collection(self, collection_name: str) -> bool:
        """Delete a collection and all its data"""
        try:
            self.client.delete_collection(name=collection_name)
            logger.info(f"Deleted collection '{collection_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to delete collection '{collection_name}': {e}")
            return False

    async def get_collection_info(self, collection_name: str) -> Optional[dict[str, Any]]:
        """Get information about a collection"""
        try:
            collection = self.client.get_collection(name=collection_name)
            count = collection.count()

            return {
                "name": collection_name,
                "vectors_count": count,
                "status": "active",
                "config": {
                    "distance": "cosine",
                    "persist_directory": self.persist_directory
                }
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return None

    def close(self):
        """Close the ChromaDB client connection (no-op for ChromaDB)"""
        try:
            # ChromaDB doesn't require explicit closing
            logger.info("ChromaDB connection closed")
        except Exception as e:
            logger.error(f"Error closing ChromaDB connection: {e}")


# Convenience function for creating manager instance
def create_chroma_manager(config=None) -> ChromaManager:
    """Create and return a ChromaManager instance"""
    if config and hasattr(config, 'chroma_persist_directory'):
        return ChromaManager(persist_directory=config.chroma_persist_directory)
    else:
        return ChromaManager(persist_directory="./chroma_db")
