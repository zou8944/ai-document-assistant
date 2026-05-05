import logging
from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from chat.generation.base import BaseLLMService

logger = logging.getLogger(__name__)


class OpenAILLMService(BaseLLMService):
    """OpenAI 兼容 API 实现"""

    def __init__(self, api_key: str, model: str = "gpt-4o",
                 base_url: str = "https://api.openai.com/v1"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    @property
    def name(self) -> str:
        return f"openai-{self.model}"

    @property
    def max_context_tokens(self) -> int:
        # 根据模型返回不同值
        if "gpt-4o" in self.model:
            return 128000
        return 16000

    async def generate(self, system_prompt: str, messages: list[dict],
                      temperature: float = 0.7, max_tokens: int = 4096) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        # Defensive: handle empty choices or missing content
        if not response.choices or not response.choices[0].message:
            logger.warning("OpenAI API returned empty choices")
            return ""
        return response.choices[0].message.content or ""

    async def stream_generate(self, system_prompt: str, messages: list[dict],
                             temperature: float = 0.7,
                             max_tokens: int = 4096) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system_prompt}] + messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def close(self) -> None:
        """Close the OpenAI HTTP client."""
        try:
            self.client.close()
        except Exception:
            pass
