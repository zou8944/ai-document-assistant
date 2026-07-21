"""OpenAI-compatible tool backend implementing ToolCallingBackend.

Supports any OpenAI-compatible API (GPT, DeepSeek, Gemini, local models, etc.)
by converting between Anthropic message format (used by the runtime) and
OpenAI chat completions format (used by the API).
"""

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, cast

import openai

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, ToolUseBlock, Usage

logger = logging.getLogger(__name__)


def _convert_messages(
    system: str,
    messages: list[dict],
) -> list[dict[str, Any]]:
    """Convert Anthropic-format messages to OpenAI format.

    The runtime stores messages in Anthropic format (content blocks with
    type "text", "tool_use", "tool_result"). This converts them to OpenAI
    format (flat content strings, tool_calls array, separate tool messages).
    """
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "user":
            # Tool results arrive as a user message with list content
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        out.append({
                            "role": "tool",
                            "tool_call_id": block["tool_use_id"],
                            "content": block.get("content") or "",
                        })
            else:
                out.append({"role": "user", "content": content})

        elif role == "assistant":
            if isinstance(content, str):
                out.append({"role": "assistant", "content": content})
            elif isinstance(content, list):
                # Extract text and tool_use blocks from Anthropic content format
                text_parts: list[str] = []
                tool_calls: list[dict[str, Any]] = []
                for block in content:
                    if not isinstance(block, dict):
                        continue
                    btype = block.get("type")
                    if btype == "text":
                        text_parts.append(block.get("text", ""))
                    elif btype == "tool_use":
                        tool_calls.append({
                            "id": block["id"],
                            "type": "function",
                            "function": {
                                "name": block["name"],
                                "arguments": json.dumps(block["input"]),
                            },
                        })
                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                }
                if tool_calls:
                    assistant_msg["tool_calls"] = tool_calls
                out.append(assistant_msg)

    return out


def _convert_tools(anthropic_tools: list[dict]) -> list[dict[str, Any]]:
    """Convert Anthropic tool schemas to OpenAI function-calling format.

    Anthropic: {"name": ..., "description": ..., "input_schema": {...}}
    OpenAI:    {"type": "function", "function": {"name": ..., "description": ..., "parameters": {...}}}
    """
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        }
        for t in anthropic_tools
    ]


def _map_stop_reason(finish_reason: str | None) -> str:
    """Map OpenAI finish_reason to Anthropic stop_reason."""
    return {
        "stop": "end_turn",
        "length": "max_tokens",
        "tool_calls": "tool_use",
        "content_filter": "end_turn",
    }.get(finish_reason or "", "end_turn")


class OpenAIToolBackend(ToolCallingBackend):
    def __init__(self, client: openai.AsyncOpenAI, model: str):
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
        openai_messages = _convert_messages(system, messages)
        openai_tools = _convert_tools(tools) if tools else cast(Any, openai.NOT_GIVEN)

        async def stream_consumer() -> AssistantTurn:
            # Accumulate streaming state
            text_parts: list[str] = []
            tool_call_acc: dict[int, dict[str, Any]] = {}  # index -> {id, name, arguments}
            finish_reason: str | None = None
            usage_data: Any = None

            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=openai_messages,  # type: ignore[arg-type]
                tools=openai_tools,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            async for chunk in stream:
                if cancellation.cancelled():
                    break

                if not chunk.choices and chunk.usage:
                    usage_data = chunk.usage
                    continue

                for choice in chunk.choices:
                    delta = choice.delta
                    if delta.content:
                        text_parts.append(delta.content)
                        if on_text_delta is not None:
                            await on_text_delta(delta.content)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_call_acc:
                                tool_call_acc[idx] = {"id": "", "name": "", "arguments": ""}
                            acc = tool_call_acc[idx]
                            if tc.id:
                                acc["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    acc["name"] = tc.function.name
                                if tc.function.arguments:
                                    acc["arguments"] += tc.function.arguments
                    if choice.finish_reason:
                        finish_reason = choice.finish_reason

            # Build response
            content: list[dict[str, Any]] = []
            if text_parts:
                content.append({"type": "text", "text": "".join(text_parts)})

            tool_uses: list[ToolUseBlock] = []
            for _idx in sorted(tool_call_acc):
                tc = tool_call_acc[_idx]
                content.append({
                    "type": "tool_use",
                    "id": tc["id"],
                    "name": tc["name"],
                    "input": json.loads(tc["arguments"]) if tc["arguments"] else {},
                })
                tool_uses.append(ToolUseBlock(
                    id=tc["id"],
                    name=tc["name"],
                    input=json.loads(tc["arguments"]) if tc["arguments"] else {},
                ))

            return AssistantTurn(
                raw_content=content,
                stop_reason=_map_stop_reason(finish_reason),
                tool_uses=tool_uses,
                usage=Usage(
                    input_tokens=usage_data.prompt_tokens if usage_data else 0,
                    output_tokens=usage_data.completion_tokens if usage_data else 0,
                ),
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
