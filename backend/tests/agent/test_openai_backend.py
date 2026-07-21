"""Tests for chat.agent.llm.openai.OpenAIToolBackend."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.llm.openai import OpenAIToolBackend, _convert_messages, _convert_tools


# -- Fake objects for streaming --


class _FakeChoiceDelta:
    def __init__(self, content=None, tool_calls=None, finish_reason=None):
        self.content = content
        self.tool_calls = tool_calls
        self.finish_reason = finish_reason


class _FakeDeltaToolCall:
    def __init__(self, index, id=None, function=None):
        self.index = index
        self.id = id
        self.function = function


class _FakeDeltaFunction:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _FakeChoice:
    def __init__(self, delta, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _FakeChunk:
    def __init__(self, choices, usage=None):
        self.choices = choices
        self.usage = usage


class _FakeUsage:
    def __init__(self, prompt_tokens=10, completion_tokens=5):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens


def _make_stream(chunks):
    """Create an async iterable that yields chunks."""
    async def _aiter():
        for chunk in chunks:
            yield chunk
    return _aiter()


# -- Test _convert_messages --


class TestConvertMessages:
    def test_simple_user_message(self):
        result = _convert_messages("sys", [{"role": "user", "content": "hi"}])
        assert result[0] == {"role": "system", "content": "sys"}
        assert result[1] == {"role": "user", "content": "hi"}

    def test_assistant_text_message(self):
        result = _convert_messages("sys", [{"role": "assistant", "content": "hello"}])
        assert result[1] == {"role": "assistant", "content": "hello"}

    def test_assistant_content_blocks_text(self):
        messages = [{"role": "assistant", "content": [{"type": "text", "text": "hi"}]}]
        result = _convert_messages("sys", messages)
        assert result[1]["role"] == "assistant"
        assert result[1]["content"] == "hi"
        assert "tool_calls" not in result[1]

    def test_assistant_content_blocks_tool_use(self):
        messages = [{"role": "assistant", "content": [
            {"type": "text", "text": "Let me search"},
            {"type": "tool_use", "id": "tu_1", "name": "search", "input": {"q": "test"}},
        ]}]
        result = _convert_messages("sys", messages)
        msg = result[1]
        assert msg["role"] == "assistant"
        assert msg["content"] == "Let me search"
        assert len(msg["tool_calls"]) == 1
        assert msg["tool_calls"][0]["id"] == "tu_1"
        assert msg["tool_calls"][0]["type"] == "function"
        assert msg["tool_calls"][0]["function"]["name"] == "search"
        assert json.loads(msg["tool_calls"][0]["function"]["arguments"]) == {"q": "test"}

    def test_tool_result_message(self):
        messages = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "result text"},
        ]}]
        result = _convert_messages("sys", messages)
        assert result[1] == {"role": "tool", "tool_call_id": "tu_1", "content": "result text"}

    def test_multiple_tool_results(self):
        messages = [{"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "tu_1", "content": "a"},
            {"type": "tool_result", "tool_use_id": "tu_2", "content": "b"},
        ]}]
        result = _convert_messages("sys", messages)
        assert result[1]["role"] == "tool"
        assert result[1]["tool_call_id"] == "tu_1"
        assert result[2]["role"] == "tool"
        assert result[2]["tool_call_id"] == "tu_2"

    def test_full_conversation_flow(self):
        """Simulate a multi-turn conversation with tool use."""
        messages = [
            {"role": "user", "content": "search for X"},
            {"role": "assistant", "content": [
                {"type": "text", "text": "Searching..."},
                {"type": "tool_use", "id": "tu_1", "name": "search", "input": {"q": "X"}},
            ]},
            {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "tu_1", "content": "found it"},
            ]},
            {"role": "assistant", "content": "Here are the results"},
        ]
        result = _convert_messages("sys", messages)
        # system + user + assistant(tool_calls) + tool + assistant(text) = 5
        assert len(result) == 5
        assert result[0]["role"] == "system"
        assert result[1]["role"] == "user"
        assert result[2]["role"] == "assistant"
        assert "tool_calls" in result[2]
        assert result[3]["role"] == "tool"
        assert result[4]["role"] == "assistant"
        assert result[4]["content"] == "Here are the results"


# -- Test _convert_tools --


class TestConvertTools:
    def test_basic_conversion(self):
        anthropic_tools = [{
            "name": "search",
            "description": "Search documents",
            "input_schema": {
                "type": "object",
                "properties": {"q": {"type": "string"}},
                "required": ["q"],
            },
        }]
        result = _convert_tools(anthropic_tools)
        assert len(result) == 1
        assert result[0]["type"] == "function"
        assert result[0]["function"]["name"] == "search"
        assert result[0]["function"]["description"] == "Search documents"
        assert result[0]["function"]["parameters"]["properties"]["q"]["type"] == "string"

    def test_missing_description(self):
        tools = [{"name": "x", "input_schema": {"type": "object", "properties": {}}}]
        result = _convert_tools(tools)
        assert result[0]["function"]["description"] == ""

    def test_missing_input_schema(self):
        tools = [{"name": "x"}]
        result = _convert_tools(tools)
        assert result[0]["function"]["parameters"] == {"type": "object", "properties": {}}


# -- Test OpenAIToolBackend --


class TestOpenAIToolBackend:
    async def test_text_only_response(self):
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="Hello "))]),
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="world", finish_reason="stop"))]),
            _FakeChunk([], usage=_FakeUsage(prompt_tokens=20, completion_tokens=5)),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
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
        assert turn.usage.input_tokens == 20
        assert turn.usage.output_tokens == 5
        # raw_content should have text block
        assert len(turn.raw_content) == 1
        assert turn.raw_content[0]["type"] == "text"
        assert turn.raw_content[0]["text"] == "Hello world"

    async def test_tool_call_response(self):
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                content=None,
                tool_calls=[_FakeDeltaToolCall(
                    index=0,
                    id="call_abc",
                    function=_FakeDeltaFunction(name="search", arguments='{"q":"test"}'),
                )],
            ), finish_reason="tool_calls")]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "search"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert turn.stop_reason == "tool_use"
        assert len(turn.tool_uses) == 1
        assert turn.tool_uses[0].id == "call_abc"
        assert turn.tool_uses[0].name == "search"
        assert turn.tool_uses[0].input == {"q": "test"}

    async def test_streaming_tool_call_assembly(self):
        """Tool call arguments arrive in multiple chunks."""
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                tool_calls=[_FakeDeltaToolCall(index=0, id="call_1", function=_FakeDeltaFunction(name="grep"))],
            ))]),
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                tool_calls=[_FakeDeltaToolCall(index=0, function=_FakeDeltaFunction(arguments='{"pat'))],
            ))]),
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                tool_calls=[_FakeDeltaToolCall(index=0, function=_FakeDeltaFunction(arguments='tern":"x"}'))],
            ), finish_reason="tool_calls")]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "grep"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert turn.tool_uses[0].input == {"pattern": "x"}

    async def test_on_text_delta_called(self):
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="Hi "))]),
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="there", finish_reason="stop"))]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        deltas = []
        async def _on_delta(text: str) -> None:
            deltas.append(text)

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
            on_text_delta=_on_delta,
        )

        assert deltas == ["Hi ", "there"]

    async def test_cancellation_raises_cancelled_error(self):
        mock_client = MagicMock()

        async def _slow_stream():
            await asyncio.sleep(10)
            yield _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="x", finish_reason="stop"))])
            yield _FakeChunk([], usage=_FakeUsage())

        mock_client.chat.completions.create = AsyncMock(return_value=_slow_stream())

        token = CancellationToken()
        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")

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

    async def test_multiple_tool_calls(self):
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                tool_calls=[
                    _FakeDeltaToolCall(index=0, id="call_1", function=_FakeDeltaFunction(name="search", arguments='{"q":"a"}')),
                    _FakeDeltaToolCall(index=1, id="call_2", function=_FakeDeltaFunction(name="grep", arguments='{"pattern":"b"}')),
                ],
            ), finish_reason="tool_calls")]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "do both"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert len(turn.tool_uses) == 2
        assert turn.tool_uses[0].name == "search"
        assert turn.tool_uses[1].name == "grep"

    async def test_text_and_tool_call_together(self):
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="Let me check "))]),
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(
                content=None,
                tool_calls=[_FakeDeltaToolCall(index=0, id="call_x", function=_FakeDeltaFunction(name="get_doc", arguments='{"id":"d1"}'))],
            ), finish_reason="tool_calls")]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        turn = await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "get doc"}],
            tools=[],
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        assert turn.stop_reason == "tool_use"
        assert len(turn.raw_content) == 2  # text + tool_use
        assert turn.raw_content[0]["type"] == "text"
        assert turn.raw_content[0]["text"] == "Let me check "
        assert turn.tool_uses[0].name == "get_doc"

    async def test_tools_passed_to_api(self):
        """Verify that tools are converted and passed to the OpenAI API."""
        mock_client = MagicMock()
        chunks = [
            _FakeChunk([_FakeChoice(_FakeChoiceDelta(content="ok", finish_reason="stop"))]),
            _FakeChunk([], usage=_FakeUsage()),
        ]
        mock_client.chat.completions.create = AsyncMock(return_value=_make_stream(chunks))

        anthropic_tools = [{
            "name": "search",
            "description": "Search docs",
            "input_schema": {"type": "object", "properties": {"q": {"type": "string"}}},
        }]

        backend = OpenAIToolBackend(client=mock_client, model="gpt-4o")
        await backend.generate_with_tools(
            system="sys",
            messages=[{"role": "user", "content": "hi"}],
            tools=anthropic_tools,
            max_tokens=100,
            temperature=0.0,
            cancellation=CancellationToken(),
        )

        call_kwargs = mock_client.chat.completions.create.call_args
        openai_tools = call_kwargs.kwargs["tools"]
        assert openai_tools[0]["type"] == "function"
        assert openai_tools[0]["function"]["name"] == "search"
        assert openai_tools[0]["function"]["parameters"]["properties"]["q"]["type"] == "string"
