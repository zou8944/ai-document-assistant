import logging
from collections.abc import AsyncIterator

from anthropic import AsyncAnthropic

from chat.generation.base import BaseLLMService

logger = logging.getLogger(__name__)


class ClaudeLLMService(BaseLLMService):
    """Anthropic Claude 实现"""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6",
                 base_url: str | None = None):
        self.client = AsyncAnthropic(api_key=api_key, base_url=base_url)
        self.model = model

    @property
    def name(self) -> str:
        return f"claude-{self.model}"

    @property
    def max_context_tokens(self) -> int:
        return 1000000  # 1M

    async def generate(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7, max_tokens: int = 4096) -> str:
        response = await self.client.messages.create(
            model=self.model,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        # Defensive: handle empty content blocks
        if not response.content:
            logger.warning("Claude API returned empty content blocks")
            return ""
        return response.content[0].text

    async def stream_generate(self, system_prompt: str, messages: list[dict],
                             temperature: float = 0.7,
                             max_tokens: int = 4096) -> AsyncIterator[str]:
        async with self.client.messages.stream(
            model=self.model,
            system=system_prompt,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def close(self) -> None:
        """Close the Anthropic HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass
