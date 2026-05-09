"""Tests for context compaction utilities."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.compaction import auto_compact, estimate_tokens, micro_compact
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, Usage
from chat.agent.registry import ToolRegistry
from chat.agent.tools.base import Tool, ToolContext, ToolResult


class PreserveTool(Tool):
    name = "preserve_tool"
    description = "Preserved."
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="ok")


class DiscardTool(Tool):
    name = "discard_tool"
    description = "Discarded."
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="ok")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(PreserveTool())
    reg.register(DiscardTool())
    return reg


class TestEstimateTokens:
    def test_returns_positive_integer(self):
        messages = [
            {"role": "user", "content": "hello world"},
            {"role": "assistant", "content": "hi there"},
        ]
        result = estimate_tokens(messages)
        assert isinstance(result, int)
        assert result > 0

    def test_uses_backend_count_tokens_when_available(self):
        backend = MagicMock(spec=ToolCallingBackend)
        backend.count_tokens = MagicMock(return_value=42)
        messages = [{"role": "user", "content": "hello"}]
        result = estimate_tokens(messages, backend)
        assert result == 42
        backend.count_tokens.assert_called_once_with(messages)

    def test_fallback_on_backend_exception(self):
        backend = MagicMock(spec=ToolCallingBackend)
        backend.count_tokens = MagicMock(side_effect=RuntimeError("fail"))
        messages = [{"role": "user", "content": "hello"}]
        result = estimate_tokens(messages, backend)
        assert isinstance(result, int)
        assert result > 0


class TestMicroCompact:
    def test_replaces_old_non_preserve_tool_results(self, registry):
        # Need at least 2 assistant turns so with keep_recent=0 some are "old"
        messages = [
            {"role": "user", "content": "q1"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-1", "name": "discard_tool", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu-1",
                        "content": "old result",
                        "is_error": False,
                    },
                ],
            },
            {"role": "user", "content": "q2"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "answer"}],
            },
        ]
        micro_compact(messages, registry, keep_recent=0)

        tr_block = messages[2]["content"][0]
        assert tr_block["content"].startswith("[Compacted:")
        assert tr_block["is_error"] is False

    def test_preserves_preserve_tool_results(self, registry):
        messages = [
            {"role": "user", "content": "q1"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-1", "name": "preserve_tool", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu-1",
                        "content": "precious result",
                        "is_error": False,
                    },
                ],
            },
            {"role": "user", "content": "q2"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "answer"}],
            },
        ]
        micro_compact(messages, registry, keep_recent=0)

        tr_block = messages[2]["content"][0]
        assert tr_block["content"] == "precious result"

    def test_keep_recent_protects_recent_results(self, registry):
        # Three rounds to have enough assistant turns
        messages = [
            {"role": "user", "content": "q1"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-1", "name": "discard_tool", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu-1",
                        "content": "first result",
                        "is_error": False,
                    },
                ],
            },
            {"role": "user", "content": "q2"},
            {
                "role": "assistant",
                "content": [
                    {"type": "tool_use", "id": "tu-2", "name": "discard_tool", "input": {}},
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "tu-2",
                        "content": "second result",
                        "is_error": False,
                    },
                ],
            },
            {"role": "user", "content": "q3"},
            {
                "role": "assistant",
                "content": [{"type": "text", "text": "answer"}],
            },
        ]
        # keep_recent=1 means only the most recent assistant turn is protected
        micro_compact(messages, registry, keep_recent=1)

        # First result should be compacted (2 assistant turns, threshold=1,
        # turns_before for first result = 1, 1 < 1 is False... wait.
        # Actually with 3 assistant turns (indices 1, 4, 7), threshold = 3 - 1 = 2.
        # First result turns_before = 1, 1 < 2 is True -> compacted.
        # Second result turns_before = 2, 2 < 2 is False -> protected.
        assert messages[2]["content"][0]["content"].startswith("[Compacted:")
        assert messages[5]["content"][0]["content"] == "second result"


class TestAutoCompact:
    async def test_compresses_to_first_summary_last_pair(self):
        backend = MagicMock(spec=ToolCallingBackend)
        backend.generate_with_tools = AsyncMock(
            return_value=AssistantTurn(
                raw_content=[{"type": "text", "text": "summary text"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=50, output_tokens=10),
            )
        )

        messages = [
            {"role": "user", "content": "first question"},
            {"role": "assistant", "content": "first answer"},
            {"role": "user", "content": "second question"},
            {"role": "assistant", "content": "second answer"},
            {"role": "user", "content": "third question"},
            {"role": "assistant", "content": "third answer"},
        ]

        result = await auto_compact(messages, backend, "original query")

        # first + summary + last_pair = 1 + 1 + 2 = 4
        assert len(result) == 4
        assert result[0] == messages[0]
        assert result[1]["role"] == "user"
        assert "summary text" in result[1]["content"]
        assert result[2] == messages[-2]
        assert result[3] == messages[-1]

        # Verify backend was called
        backend.generate_with_tools.assert_awaited_once()
        call_kwargs = backend.generate_with_tools.call_args.kwargs
        assert call_kwargs["tools"] == []
        assert call_kwargs["max_tokens"] == 4096

    def test_too_short_returns_unchanged(self):
        backend = MagicMock(spec=ToolCallingBackend)
        messages = [
            {"role": "user", "content": "q1"},
            {"role": "assistant", "content": "a1"},
        ]
        # auto_compact is async but for too-short it returns before any await
        # We still need to run it in an async context
        import asyncio

        result = asyncio.run(auto_compact(messages, backend, "q"))
        assert result == messages
        backend.generate_with_tools.assert_not_called()
