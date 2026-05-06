from abc import ABC, abstractmethod

from chat.models import SearchResult


class BaseIndex(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def search(self, query: str, top_k: int = 10,
                     filters: dict | None = None,
                     collection_ids: list[str] | None = None) -> SearchResult:
        pass

    @abstractmethod
    def index_document(self, document_id: str, title: str = "", summary: str = "",
                       keywords: list[str] | None = None, **metadata) -> None:
        pass
