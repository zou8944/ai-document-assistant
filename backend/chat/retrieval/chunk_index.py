import logging

from chat.models import RetrievedDocument, SearchResult
from chat.retrieval.base import BaseIndex

logger = logging.getLogger(__name__)


class ChunkIndex(BaseIndex):
    def __init__(self, chroma_client, embedding_model, collection_name: str = "default"):
        self.chroma = chroma_client
        self.embedding_model = embedding_model
        self.collection_name = collection_name

    @property
    def name(self) -> str:
        return "chunk_vector"

    async def search(self, query: str, top_k: int = 5, filters: dict = None) -> SearchResult:
        try:
            collection = self.chroma.get_collection(self.collection_name)
            results = collection.query(
                query_texts=[query],
                n_results=top_k,
                where=filters
            )
        except Exception as e:
            logger.error(f"ChunkIndex search failed for query '{query}': {e}")
            return SearchResult(
                documents=[],
                search_type="chunk_vector",
                total_found=0
            )

        documents = []
        ids = results.get("ids", [[]])[0] if results.get("ids") else []
        metadatas = results.get("metadatas", [[]])[0] if results.get("metadatas") else []
        distances = results.get("distances", [[]])[0] if results.get("distances") else []
        docs = results.get("documents", [[]])[0] if results.get("documents") else []

        # Defensive: iterate only over indices that exist in all arrays
        for i in range(len(ids)):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 0.5
            doc_text = docs[i] if i < len(docs) else ""
            relevance_score = 1.0 - distance
            documents.append(RetrievedDocument(
                document_id=metadata.get("document_id", ""),
                document_name=metadata.get("document_name", ""),
                document_uri=metadata.get("document_uri", ""),
                content=doc_text,
                relevance_score=relevance_score,
                source_type="chunk_vector",
                chunk_index=metadata.get("chunk_index")
            ))

        return SearchResult(
            documents=documents,
            search_type="chunk_vector",
            total_found=len(documents)
        )

    async def index_document(self, document_id: str, title: str, summary: str,
                            keywords: list[str], **metadata) -> None:
        """No-op: chunks are already indexed by TaskService during document processing."""
        pass
