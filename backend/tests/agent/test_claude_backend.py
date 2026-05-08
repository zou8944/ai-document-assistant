"""Tests for chat.agent.llm.claude.ClaudeToolBackend."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.claude import ClaudeToolBackend


class _FakeDelta:
    type = "text_delta"
    text = "hello"


class _FakeEvent:
    type = "content_block_delta"
    delta = _FakeDelta()


class _FakeToolUseBlock:
    type = "tool_use"
    id = "tu_1"
    name = "dummy"
    input = {"x": 1}


class _FakeTextBlock:
    type = "text"
    text = "hello"


class _FakeUsage:
    input_tokens = 10
    output_tokens = 5


class _FakeMessage:
    content = [_FakeTextBlock()]
    stop_reason = "end_turn"
    usage = _FakeUsage()


class _FakeMessageToolUse:
    content = [_FakeToolUseBlock()]
    stop_reason = "tool_use"
    usage = _FakeUsage()


def _make_stream_mock(events, final_message):
    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    async def _aiter():
        for ev in events:
            yield ev

    mock_stream.__aiter__ = lambda self: _aiter()
    mock_stream.get_final_message = AsyncMock(return_value=final_message)
    return mock_stream


class TestClaudeToolBackend:
    async def test_end_turn_no_tool_use(self):
        mock_client = MagicMock()
        mock_stream = _make_stream_mock([_FakeEvent()], _FakeMessage())
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        backend = ClaudeToolBackend(client=mock_client, model="claude-test")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert turn.stop_reason == "end_turn"
        assert turn.tool_uses == []
        assert turn.usage.input_tokens == 10
        assert turn.usage.output_tokens == 5

    async def test_tool_use_returns_tool_use_block(self):
        mock_client = MagicMock()
        mock_stream = _make_stream_mock([], _FakeMessageToolUse())
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        backend = ClaudeToolBackend(client=mock_client, model="claude-test")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert turn.stop_reason == "tool_use"
        assert len(turn.tool_uses) == 1
        assert turn.tool_uses[0].id == "tu_1"
        assert turn.tool_uses[0].name == "dummy"
        assert turn.tool_uses[0].input == {"x": 1}

    async def test_cancellation_raises_cancelled_error(self):
        mock_client = MagicMock()

        async def _slow_stream():
            await asyncio.sleep(10)
            yield _FakeEvent()

        mock_stream = AsyncMock()
        mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
        mock_stream.__aexit__ = AsyncMock(return_value=None)
        mock_stream.__aiter__ = lambda self: _slow_stream()
        mock_stream.get_final_message = AsyncMock(return_value=_FakeMessage())
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        token = CancellationToken()
        backend = ClaudeToolBackend(client=mock_client, model="claude-test")

        async def _cancel_after():
            await asyncio.sleep(0.01)
            token.cancel()

        asyncio.create_task(_cancel_after())

        with pytest.raises(asyncio.CancelledError):
            await backend.generate_with_tools(
                system="sys",
                messages=[{"role": "user", "content": "hi"}],
                tools=[],
                max_tokens=100,
                temperature=0.0,
                cancellation=token,
            )

    async def test_on_text_delta_called(self):
        mock_client = MagicMock()
        mock_stream = _make_stream_mock([_FakeEvent(), _FakeEvent()], _FakeMessage())
        mock_client.messages.stream = MagicMock(return_value=mock_stream)

        deltas = []

        async def _on_delta(text: str) -> None:
            deltas.append(text)

        backend = ClaudeToolBackend(client=mock_client, model="claude-test")
        await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
            on_text_delta=_on_delta,
        )

        assert deltas == ["hello", "hello"]
