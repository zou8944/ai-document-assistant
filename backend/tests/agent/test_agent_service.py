"""Tests for AgentChatService."""

import json
from unittest.mock import MagicMock

from chat.agent.llm.base import AssistantTurn, ToolCallingBackend, Usage
from chat.agent.runtime import AgentConfig
from chat.agent_service import AgentChatService
from chat.models import SSEEventType
from models.dto import ChatDTO, ChatMessageDTO


class _FakeBackend(ToolCallingBackend):
    """Fake backend that returns a single end_turn turn."""

    def __init__(self, turn: AssistantTurn | None = None):
        self.turn = turn or AssistantTurn(
            raw_content=[{"type": "text", "text": "hello world"}],
            stop_reason="end_turn",
            tool_uses=[],
            usage=Usage(input_tokens=10, output_tokens=5),
        )

    async def generate_with_tools(
        self,
        *,
        system,
        messages,
        tools,
        max_tokens,
        temperature,
        cancellation,
        on_text_delta=None,
    ):
        if on_text_delta:
            for chunk in ["hello ", "world"]:
                await on_text_delta(chunk)
        return self.turn


def _make_chat_repo(chat_id: str, collection_ids: list[str] | None = None):
    repo = MagicMock()
    dto = ChatDTO(
        id=chat_id,
        name="test-chat",
        collection_ids=json.dumps(collection_ids or ["col-1"]),
    )
    repo.get_by_id.return_value = dto
    return repo


def _make_message_repo(messages: list[ChatMessageDTO] | None = None):
    repo = MagicMock()
    repo.get_by_chat.return_value = messages or []

    def _add_message(chat_id, role, content, sources=None, metadata=None):
        return ChatMessageDTO(
            id=f"msg_{role}_{chat_id}",
            chat_id=chat_id,
            role=role,
            content=content,
            sources=sources or "[]",
            message_metadata=metadata or "{}",
        )

    repo.add_message.side_effect = _add_message
    repo.update.return_value = None
    return repo


def _make_document_repo():
    return MagicMock()


def _make_collection_repo():
    return MagicMock()


class TestProcessNormalFlow:
    async def test_yields_expected_event_sequence(self, tmp_path):
        backend = _FakeBackend()
        config = AgentConfig(
            max_iterations=3,
            transcript_dir=str(tmp_path / "transcripts"),
        )
        chat_repo = _make_chat_repo("chat-1")
        message_repo = _make_message_repo()
        service = AgentChatService(
            backend=backend,
            config=config,
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        events = []
        async for event in service.process(chat_id="chat-1", query="hi"):
            events.append(event)

        types = [e.type for e in events]
        assert types[0] == SSEEventType.AGENT_START
        assert "message_id" in events[0].data
        assert types[-1] == SSEEventType.DONE

    async def test_persists_user_message_with_engine_marker(self, tmp_path):
        backend = _FakeBackend()
        config = AgentConfig(
            max_iterations=3,
            transcript_dir=str(tmp_path / "transcripts"),
        )
        chat_repo = _make_chat_repo("chat-1")
        message_repo = _make_message_repo()
        service = AgentChatService(
            backend=backend,
            config=config,
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        async for _ in service.process(chat_id="chat-1", query="hi"):
            pass

        user_calls = [
            c for c in message_repo.add_message.call_args_list
            if c.kwargs.get("role") == "user"
        ]
        assert len(user_calls) == 1
        metadata = json.loads(user_calls[0].kwargs["metadata"])
        assert metadata.get("engine") == "agent"

    async def test_updates_placeholder_with_agent_trace(self, tmp_path):
        backend = _FakeBackend()
        config = AgentConfig(
            max_iterations=3,
            transcript_dir=str(tmp_path / "transcripts"),
        )
        chat_repo = _make_chat_repo("chat-1")
        message_repo = _make_message_repo()
        service = AgentChatService(
            backend=backend,
            config=config,
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        async for _ in service.process(chat_id="chat-1", query="hi"):
            pass

        update_calls = message_repo.update.call_args_list
        assert len(update_calls) == 1
        kwargs = update_calls[0].kwargs
        assert kwargs["content"] == "hello world"
        metadata = json.loads(kwargs["message_metadata"])
        assert metadata["engine"] == "agent"
        assert metadata["iterations"] == 1
        assert metadata["stop_reason"] == "end_turn"
        assert "messages" in metadata

    async def test_transcript_file_created(self, tmp_path):
        transcript_dir = tmp_path / "transcripts"
        backend = _FakeBackend()
        config = AgentConfig(
            max_iterations=3,
            transcript_dir=str(transcript_dir),
        )
        chat_repo = _make_chat_repo("chat-1")
        message_repo = _make_message_repo()
        service = AgentChatService(
            backend=backend,
            config=config,
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        async for _ in service.process(chat_id="chat-1", query="hi"):
            pass

        files = list(transcript_dir.glob("*.jsonl"))
        assert len(files) == 1
        lines = files[0].read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) >= 1
        first = json.loads(lines[0])
        assert first["type"] == "agent_start"


class TestLoadHistory:
    def test_loads_only_agent_engine_messages(self):
        messages = [
            ChatMessageDTO(
                id="m1", chat_id="c1", role="user", content="q1",
                message_metadata=json.dumps({"engine": "agent"}),
            ),
            ChatMessageDTO(
                id="m2", chat_id="c1", role="assistant", content="a1",
                message_metadata=json.dumps({"engine": "agent"}),
            ),
            ChatMessageDTO(
                id="m3", chat_id="c1", role="user", content="q2",
                message_metadata=json.dumps({"engine": "legacy"}),
            ),
            ChatMessageDTO(
                id="m4", chat_id="c1", role="assistant", content="a2",
                message_metadata="{}",
            ),
        ]
        chat_repo = _make_chat_repo("c1")
        message_repo = _make_message_repo(messages=messages)
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        history = service._load_history("c1")
        assert len(history) == 2
        assert history[0] == {"role": "user", "content": "q1"}
        assert history[1] == {"role": "assistant", "content": "a1"}

    def test_returns_empty_on_exception(self):
        chat_repo = _make_chat_repo("c1")
        message_repo = _make_message_repo()
        message_repo.get_by_chat.side_effect = RuntimeError("db error")
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=chat_repo,
            chat_message_repo=message_repo,
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        history = service._load_history("c1")
        assert history == []


class TestGetCollectionIds:
    def test_returns_parsed_list(self):
        chat_repo = _make_chat_repo("c1", collection_ids=["col-a", "col-b"])
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=chat_repo,
            chat_message_repo=_make_message_repo(),
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        result = service._get_collection_ids("c1")
        assert result == ["col-a", "col-b"]

    def test_returns_empty_when_chat_missing(self):
        chat_repo = MagicMock()
        chat_repo.get_by_id.return_value = None
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=chat_repo,
            chat_message_repo=_make_message_repo(),
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        result = service._get_collection_ids("missing")
        assert result == []

    def test_returns_empty_on_malformed_json(self):
        chat_repo = MagicMock()
        dto = ChatDTO(id="c1", name="chat", collection_ids="not-json")
        chat_repo.get_by_id.return_value = dto
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=chat_repo,
            chat_message_repo=_make_message_repo(),
            document_repo=_make_document_repo(),
            collection_repo=_make_collection_repo(),
        )

        result = service._get_collection_ids("c1")
        assert result == []


class TestReconstructMessages:
    def test_reconstructs_basic_conversation(self):
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=MagicMock(),
            chat_message_repo=MagicMock(),
            document_repo=MagicMock(),
            collection_repo=MagicMock(),
        )

        history = [{"role": "user", "content": "prev"}]
        messages = service._reconstruct_messages(history, "hi", "answer", [])
        assert messages == [
            {"role": "user", "content": "prev"},
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "answer"},
        ]

    def test_uses_sources_when_thinking_empty(self):
        service = AgentChatService(
            backend=MagicMock(spec=ToolCallingBackend),
            config=AgentConfig(),
            chat_repo=MagicMock(),
            chat_message_repo=MagicMock(),
            document_repo=MagicMock(),
            collection_repo=MagicMock(),
        )

        messages = service._reconstruct_messages([], "q", "", [{"id": "d1"}])
        assert messages[0] == {"role": "user", "content": "q"}
        assert messages[1]["role"] == "assistant"
        assert "sources" in messages[1]["content"]
