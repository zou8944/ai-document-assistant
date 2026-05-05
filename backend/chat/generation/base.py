from abc import ABC, abstractmethod
from collections.abc import AsyncIterator


class BaseLLMService(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @property
    @abstractmethod
    def max_context_tokens(self) -> int:
        pass

    @abstractmethod
    async def generate(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7, max_tokens: int = 4096) -> str:
        pass

    @abstractmethod
    async def stream_generate(self, system_prompt: str, messages: list[dict],
                             temperature: float = 0.7,
                             max_tokens: int = 4096) -> AsyncIterator[str]:
        pass

    @abstractmethod
    def close(self) -> None:
        """Close underlying HTTP clients and release resources."""
        pass
