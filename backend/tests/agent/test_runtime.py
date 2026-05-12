"""Tests for AgentRuntime main loop."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, ToolUseBlock, Usage
from chat.agent.registry import ToolRegistry
from chat.agent.runtime import AgentConfig, AgentRuntime
from chat.agent.tools.base import AgentDeps, Tool, ToolContext, ToolResult
from chat.models import SSEEventType


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
        runtime = AgentRuntime(backend, registry, config)
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
            SSEEventType.AGENT_START,
            SSEEventType.ITERATION_START,
            SSEEventType.AGENT_THINKING,
            SSEEventType.AGENT_THINKING,
            SSEEventType.THINKING_DONE,
            SSEEventType.FINAL_TEXT_PROMOTE,
            SSEEventType.DONE,
        ]

        assert events[0].data == {"max_iter": 3, "model": "standard"}
        assert events[1].data == {"iteration": 1}
        assert events[2].data == {"delta": "hello ", "iteration": 1}
        assert events[3].data == {"delta": "world", "iteration": 1}
        assert events[4].data["iteration"] == 1
        assert events[4].data["ms"] >= 0
        assert events[5].data == {"iteration": 1}
        assert events[6].data["iterations"] == 1

        # emit should not be called for text deltas (runtime drains queue instead)
        emit_calls = [c for c in emit.call_args_list if c.args[0].type == SSEEventType.AGENT_THINKING]
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
        runtime = AgentRuntime(backend, registry, config)
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
        runtime = AgentRuntime(backend, registry, config)
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
        assert SSEEventType.TOOL_CALL in types
        assert SSEEventType.TOOL_RESULT in types

        # Find second iteration_start
        iter_starts = [i for i, e in enumerate(events) if e.type == SSEEventType.ITERATION_START]
        assert len(iter_starts) == 2

        # After second iteration, final_text_promote and done
        final_promote_idx = next(
            i for i, e in enumerate(events) if e.type == SSEEventType.FINAL_TEXT_PROMOTE
        )
        assert final_promote_idx > iter_starts[1]

        done_event = events[-1]
        assert done_event.type == SSEEventType.DONE
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
        runtime = AgentRuntime(backend, registry, config)
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
        assert SSEEventType.AGENT_HALTED in types

        halted_idx = types.index(SSEEventType.AGENT_HALTED)
        done_idx = types.index(SSEEventType.DONE)
        assert done_idx > halted_idx

        done_event = events[done_idx]
        assert done_event.data.get("halted") is True
        assert done_event.data["iterations"] == 2

        # Verify the final generate call used empty tools list
        final_call = backend.generate_with_tools.call_args_list[-1]
        assert final_call.kwargs["tools"] == []


class EmptyResultTool(Tool):
    name = "empty_tool"
    description = "Returns empty result for loop testing."
    input_schema = {"type": "object", "properties": {}}

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="No matches. Try synonyms or broader keywords.")


class TestLoopDetection:
    @pytest.fixture
    def empty_registry(self):
        reg = ToolRegistry()
        reg.register(EmptyResultTool())
        return reg

    async def test_loop_warning_injected(self, empty_registry, agent_deps):
        # Threshold 1 so a single empty result triggers the warning
        config = AgentConfig(
            max_iterations=5,
            loop_detector_enabled=True,
            loop_max_consecutive_failures=1,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        backend = _make_backend_mock(
            # Iteration 1: tool_use with empty result -> triggers loop_warning
            AssistantTurn(
                raw_content=[
                    {"type": "text", "text": "thinking"},
                    {"type": "tool_use", "id": "tu-1", "name": "empty_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-1", name="empty_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            # Iteration 2: end_turn (heeds warning)
            AssistantTurn(
                raw_content=[{"type": "text", "text": "I cannot find enough information."}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=15, output_tokens=5),
            ),
        )
        runtime = AgentRuntime(backend, empty_registry, config)
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
                query="test loop",
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
        assert SSEEventType.AGENT_HALTED in types

        halted = [e for e in events if e.type == SSEEventType.AGENT_HALTED]
        assert halted[0].data["reason"] == "loop_warning"

        # After warning, LLM heeds and returns end_turn
        done_event = events[-1]
        assert done_event.type == SSEEventType.DONE
        # Should NOT be halted since LLM ended normally after warning
        assert done_event.data.get("halted") is None

    async def test_loop_force_termination(self, empty_registry, agent_deps):
        config = AgentConfig(
            max_iterations=5,
            loop_detector_enabled=True,
            loop_max_consecutive_failures=1,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        backend = _make_backend_mock(
            # Iteration 1: tool_use -> triggers loop_warning
            AssistantTurn(
                raw_content=[
                    {"type": "text", "text": "thinking"},
                    {"type": "tool_use", "id": "tu-1", "name": "empty_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-1", name="empty_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            # Iteration 2: still tool_use (ignores warning) -> triggers loop_detected -> force termination
            AssistantTurn(
                raw_content=[
                    {"type": "text", "text": "still searching"},
                    {"type": "tool_use", "id": "tu-2", "name": "empty_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-2", name="empty_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            # Final forced turn (no tools)
            AssistantTurn(
                raw_content=[{"type": "text", "text": "halted due to loop"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=20, output_tokens=5),
            ),
        )
        runtime = AgentRuntime(backend, empty_registry, config)
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
                query="test loop",
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
        assert SSEEventType.AGENT_HALTED in types

        halted_events = [e for e in events if e.type == SSEEventType.AGENT_HALTED]
        assert len(halted_events) == 2
        assert halted_events[0].data["reason"] == "loop_warning"
        assert halted_events[1].data["reason"] == "loop_detected"

        done_event = events[-1]
        assert done_event.type == SSEEventType.DONE
        assert done_event.data.get("halted") is True
        assert done_event.data.get("reason") == "loop_detected"

        # Verify the final generate call used empty tools list
        final_call = backend.generate_with_tools.call_args_list[-1]
        assert final_call.kwargs["tools"] == []

    async def test_loop_detector_disabled(self, empty_registry, agent_deps):
        config = AgentConfig(
            max_iterations=2,
            loop_detector_enabled=False,
        )
        backend = _make_backend_mock(
            AssistantTurn(
                raw_content=[
                    {"type": "tool_use", "id": "tu-1", "name": "empty_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-1", name="empty_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            AssistantTurn(
                raw_content=[
                    {"type": "tool_use", "id": "tu-2", "name": "empty_tool", "input": {}},
                ],
                stop_reason="tool_use",
                tool_uses=[ToolUseBlock(id="tu-2", name="empty_tool", input={})],
                usage=Usage(input_tokens=5, output_tokens=5),
            ),
            # Final forced turn after max_iterations reached
            AssistantTurn(
                raw_content=[{"type": "text", "text": "max iter halt"}],
                stop_reason="end_turn",
                tool_uses=[],
                usage=Usage(input_tokens=20, output_tokens=5),
            ),
        )
        runtime = AgentRuntime(backend, empty_registry, config)
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
                query="test loop",
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
        assert SSEEventType.AGENT_HALTED in types

        halted = [e for e in events if e.type == SSEEventType.AGENT_HALTED]
        assert halted[0].data["reason"] == "max_iterations"

        done_event = events[-1]
        assert done_event.data.get("halted") is True


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
        runtime = AgentRuntime(backend, registry, config)
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
