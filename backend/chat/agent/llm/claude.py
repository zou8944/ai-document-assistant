"""Claude tool_use backend implementing ToolCallingBackend."""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from anthropic import AsyncAnthropic

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, ToolUseBlock, Usage

logger = logging.getLogger(__name__)


class ClaudeToolBackend(ToolCallingBackend):
    def __init__(self, client: AsyncAnthropic, model: str):
        self.client = client
        self.model = model

    async def generate_with_tools(
        self,
        *,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int,
        temperature: float,
        cancellation: CancellationToken,
        on_text_delta: Callable[[str], Awaitable[None]] | None = None,
    ) -> AssistantTurn:
        async def stream_consumer() -> AssistantTurn:
            async with self.client.messages.stream(
                model=self.model,
                system=system,
                messages=messages,
                tools=tools,
                temperature=temperature,
                max_tokens=max_tokens,
            ) as stream:
                async for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                        and on_text_delta is not None
                    ):
                        await on_text_delta(event.delta.text)

                response = await stream.get_final_message()

            tool_uses: list[ToolUseBlock] = []
            for block in response.content:
                if block.type == "tool_use":
                    tool_uses.append(
                        ToolUseBlock(
                            id=block.id,
                            name=block.name,
                            input=block.input,
                        )
                    )

            usage = Usage(
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

            return AssistantTurn(
                raw_content=response.content,
                stop_reason=response.stop_reason or "",
                tool_uses=tool_uses,
                usage=usage,
            )

        stream_task = asyncio.create_task(stream_consumer())
        cancel_task = asyncio.create_task(cancellation.wait())
        done, pending = await asyncio.wait(
            [stream_task, cancel_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        if cancellation.cancelled():
            for task in pending:
                task.cancel()
            try:
                await stream_task
            except asyncio.CancelledError:
                pass
            raise asyncio.CancelledError()

        return stream_task.result()
