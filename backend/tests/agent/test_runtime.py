"""Tests for AgentRuntime main loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, ToolUseBlock, Usage
from chat.agent.registry import ToolRegistry
from chat.agent.runtime import AgentConfig, AgentRuntime
from chat.agent.tools.base import AgentDeps, Tool, ToolContext, ToolResult
from chat.models import SSEEvent


class MockTool(Tool):
    name = "mock_tool"
    description = "A mock tool for testing."
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="mock result")


class PreserveTool(Tool):
    name = "preserve_tool"
    description = "A preserve tool for testing."
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="preserve result")


@pytest.fixture
def registry():
    reg = ToolRegistry()
    reg.register(MockTool())
    reg.register(PreserveTool())
    return reg


@pytest.fixture
def agent_deps():
    return AgentDeps(
        collection_repo=MagicMock(),
        document_repo=MagicMock(),
    )


@pytest.fixture
def config():
    return AgentConfig(max_iterations=3)


async def _collect_events(runtime, **kwargs):
    """Helper to collect all yielded events from AgentRuntime.run()."""
    events = []
    async for event in runtime.run(**kwargs):
        events.append(event)
    return events


def _make_backend_mock(*turns):
    """Create a mock ToolCallingBackend that returns turns in sequence."""
    mock = MagicMock(spec=ToolCallingBackend)
    turn_iter = iter(turns)

    async def mock_generate(*, on_text_delta=None, **kwargs):
        turn = next(turn_iter)
        if on_text_delta and turn.stop_reason == "end_turn":
            for chunk in ["hello ", "world"]:
                await on_text_delta(chunk)
        return turn

    mock.generate_with_tools = AsyncMock(side_effect=mock_generate)
    return mock


class TestSingleTurnEndTurn:
    async def test_event_sequence(self, registry, agent_deps, config):
        backend = _make_backend_mock(
            AssistantTurn(
                raw_content=[{"type": "text", "text": "hello world"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=10, output_tokens=5),
            )
        )
        fast_backend = MagicMock(spec=ToolCallingBackend)
        runtime = AgentRuntime(backend, fast_backend, registry, config)
        emit = AsyncMock()

        events = await _collect_events(
            runtime,
            chat_id="chat-1",
            query="say hello",
            history=[],
            collection_ids=["col-1"],
            cancellation=CancellationToken(),
            deps=agent_deps,
            emit=emit,
            transcript=None,
        )

        types = [e.type for e in events]
        assert types == [
            "agent_start",
            "iteration_start",
            "agent_thinking",
            "agent_thinking",
            "final_text_promote",
            "done",
        ]

        assert events[0].data == {"max_iter": 3, "model": "standard"}
        assert events[1].data == {"iteration": 1}
        assert events[2].data == {"delta": "hello ", "iteration": 1}
        assert events[3].data == {"delta": "world", "iteration": 1}
        assert events[4].data == {"iteration": 1}
        assert events[5].data["iterations"] == 1

        # emit should not be called for text deltas (runtime drains queue instead)
        emit_calls = [c for c in emit.call_args_list if c.args[0].type == "agent_thinking"]
        assert len(emit_calls) == 0

    async def test_messages_final_state(self, registry, agent_deps, config):
        backend = _make_backend_mock(
            AssistantTurn(
                raw_content=[{"type": "text", "text": "hello world"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=10, output_tokens=5),
            )
        )
        fast_backend = MagicMock(spec=ToolCallingBackend)
        runtime = AgentRuntime(backend, fast_backend, registry, config)
        emit = AsyncMock()

        # We need to inspect messages after run completes.
        # Patch auto_compact and micro_compact to avoid side effects.
        import chat.agent.runtime as runtime_mod

        original_micro = runtime_mod.micro_compact
        original_auto = runtime_mod.auto_compact
        runtime_mod.micro_compact = lambda *a, **k: None
        runtime_mod.auto_compact = lambda *a, **k: a[0]

        try:
            async for _ in runtime.run(
                chat_id="chat-1",
                query="say hello",
                history=[],
                collection_ids=["col-1"],
                cancellation=CancellationToken(),
                deps=agent_deps,
                emit=emit,
                transcript=None,
            ):
                pass
        finally:
            runtime_mod.micro_compact = original_micro
            runtime_mod.auto_compact = original_auto

        # Check backend was called with messages containing user query + assistant turn
        call_args = backend.generate_with_tools.call_args_list[0].kwargs
        messages = call_args["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "say hello"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == [{"type": "text", "text": "hello world"}]


class TestMultiRoundToolUse:
    async def test_tool_use_then_end_turn(self, registry, agent_deps, config):
        backend = _make_backend_mock(
            AssistantTurn(
                raw_content=[
                    {"type": "text", "text": "thinking"},
                    {
                        "type": "tool_use",
                        "id": "tu-1",
                        "name": "mock_tool",
                        "input": {},
                    },
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-1", name="mock_tool", input={})],
                usage=Usage(input_tokens=10, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[{"type": "text", "text": "done"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=15, output_tokens=3),
            ),
        )
        fast_backend = MagicMock(spec=ToolCallingBackend)
        runtime = AgentRuntime(backend, fast_backend, registry, config)
        emit = AsyncMock()

        import chat.agent.runtime as runtime_mod

        original_micro = runtime_mod.micro_compact
        original_auto = runtime_mod.auto_compact
        runtime_mod.micro_compact = lambda *a, **k: None
        runtime_mod.auto_compact = lambda *a, **k: a[0]

        try:
            events = await _collect_events(
                runtime,
                chat_id="chat-1",
                query="use tool",
                history=[],
                collection_ids=["col-1"],
                cancellation=CancellationToken(),
                deps=agent_deps,
                emit=emit,
                transcript=None,
            )
        finally:
            runtime_mod.micro_compact = original_micro
            runtime_mod.auto_compact = original_auto

        types = [e.type for e in events]
        assert "tool_call" in types
        assert "tool_result" in types

        # Find second iteration_start
        iter_starts = [i for i, e in enumerate(events) if e.type == "iteration_start"]
        assert len(iter_starts) == 2

        # After second iteration, final_text_promote and done
        final_promote_idx = next(
            i for i, e in enumerate(events) if e.type == "final_text_promote"
        )
        assert final_promote_idx > iter_starts[1]

        done_event = events[-1]
        assert done_event.type == "done"
        assert done_event.data["iterations"] == 2


class TestMaxIterations:
    async def test_max_iter_halts(self, registry, agent_deps, config):
        config.max_iterations = 2

        # Both turns return tool_use to force max_iter
        backend = _make_backend_mock(
            AssistantTurn(
                raw_content=[
                    {"type": "tool_use", "id": "tu-1", "name": "mock_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-1", name="mock_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[
                    {"type": "tool_use", "id": "tu-2", "name": "mock_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-2", name="mock_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            # Final forced turn (no tools)
            AssistantTurn(
                raw_content=[{"type": "text", "text": "halted"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=20, output_tokens=5),
            ),
        )
        fast_backend = MagicMock(spec=ToolCallingBackend)
        runtime = AgentRuntime(backend, fast_backend, registry, config)
        emit = AsyncMock()

        import chat.agent.runtime as runtime_mod

        original_micro = runtime_mod.micro_compact
        original_auto = runtime_mod.auto_compact
        runtime_mod.micro_compact = lambda *a, **k: None
        runtime_mod.auto_compact = lambda *a, **k: a[0]

        try:
            events = await _collect_events(
                runtime,
                chat_id="chat-1",
                query="loop forever",
                history=[],
                collection_ids=["col-1"],
                cancellation=CancellationToken(),
                deps=agent_deps,
                emit=emit,
                transcript=None,
            )
        finally:
            runtime_mod.micro_compact = original_micro
            runtime_mod.auto_compact = original_auto

        types = [e.type for e in events]
        assert "agent_halted" in types

        halted_idx = types.index("agent_halted")
        done_idx = types.index("done")
        assert done_idx > halted_idx

        done_event = events[done_idx]
        assert done_event.data.get("halted") is True
        assert done_event.data["iterations"] == 2

        # Verify the final generate call used empty tools list
        final_call = backend.generate_with_tools.call_args_list[-1]
        assert final_call.kwargs["tools"] == []


class TestCancellation:
    async def test_cancelled_on_second_iteration(self, registry, agent_deps, config):
        token = CancellationToken()

        async def mock_generate(*, on_text_delta=None, **kwargs):
            # Cancel on second call
            if backend.generate_with_tools.call_count >= 2:
                token.cancel()
                token.raise_if_cancelled()
            return AssistantTurn(
                raw_content=[
                    {"type": "tool_use", "id": f"tu-{backend.generate_with_tools.call_count}", "name": "mock_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[
                    ToolUseBlock(
                        id=f"tu-{backend.generate_with_tools.call_count}",
                        name="mock_tool",
                        input={},
                    )
                ],
                usage=Usage(input_tokens=5, output_tokens=5),
            )

        backend = MagicMock(spec=ToolCallingBackend)
        backend.generate_with_tools = AsyncMock(side_effect=mock_generate)
        fast_backend = MagicMock(spec=ToolCallingBackend)
        runtime = AgentRuntime(backend, fast_backend, registry, config)
        emit = AsyncMock()

        import chat.agent.runtime as runtime_mod

        original_micro = runtime_mod.micro_compact
        original_auto = runtime_mod.auto_compact
        runtime_mod.micro_compact = lambda *a, **k: None
        runtime_mod.auto_compact = lambda *a, **k: a[0]

        try:
            with pytest.raises(asyncio.CancelledError):
                async for _ in runtime.run(
                    chat_id="chat-1",
                    query="cancel me",
                    history=[],
                    collection_ids=["col-1"],
                    cancellation=token,
                    deps=agent_deps,
                    emit=emit,
                    transcript=None,
                ):
                    pass
        finally:
            runtime_mod.micro_compact = original_micro
            runtime_mod.auto_compact = original_auto
