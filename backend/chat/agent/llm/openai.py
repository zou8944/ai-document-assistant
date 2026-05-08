"""OpenAI tool backend (placeholder)."""

from chat.agent.llm.base import ToolCallingBackend


class OpenAIToolBackend(ToolCallingBackend):
    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
        cancellation,
        on_text_delta=None,
    ):
        raise NotImplementedError("OpenAI tool backend not yet implemented")
