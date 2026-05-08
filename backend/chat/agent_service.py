"""Agent-based chat service replacing legacy ChatService."""

import json
import logging
import uuid
from collections.abc import AsyncIterator

from chat.agent import AgentConfig, AgentDeps, AgentRuntime, build_default_registry
from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import ToolCallingBackend
from chat.agent.trace import TranscriptWriter
from chat.models import SSEEvent
from repository.chat import ChatMessageRepository, ChatRepository
from repository.collection import CollectionRepository
from repository.document import DocumentRepository

logger = logging.getLogger(__name__)

# Global cancellation registry: (chat_id, message_id) -> CancellationToken
_cancel_registry: dict[tuple[str, str], CancellationToken] = {}


class AgentChatService:
    """Service that wraps AgentRuntime for production use."""

    def __init__(
        self,
        backend: ToolCallingBackend,
        fast_backend: ToolCallingBackend,
        config: AgentConfig,
        chat_repo: ChatRepository,
        chat_message_repo: ChatMessageRepository,
        document_repo: DocumentRepository,
        collection_repo: CollectionRepository,
    ):
        self.backend = backend
        self.fast_backend = fast_backend
        self.config = config
        self.chat_repo = chat_repo
        self.chat_message_repo = chat_message_repo
        self.document_repo = document_repo
        self.collection_repo = collection_repo

    async def process(
        self,
        chat_id: str,
        query: str,
    ) -> AsyncIterator[SSEEvent]:
        message_id = str(uuid.uuid4())
        token = CancellationToken()
        _cancel_registry[(chat_id, message_id)] = token

        # Persist user message with engine marker so _load_history includes it
        self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=query,
            metadata=json.dumps({"engine": "agent"}),
        )

        # Placeholder message
        placeholder = self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="assistant",
            content="",
            metadata=json.dumps({"status": "pending", "engine": "agent"}),
        )
        placeholder_id = placeholder.id

        transcript = TranscriptWriter(
            self.config.transcript_dir, chat_id, message_id
        )

        try:
            with transcript:
                history = self._load_history(chat_id)
                collection_ids = self._get_collection_ids(chat_id)

                deps = AgentDeps(
                    collection_repo=self.collection_repo,
                    document_repo=self.document_repo,
                )
                registry = build_default_registry(deps)
                runtime = AgentRuntime(
                    backend=self.backend,
                    fast_backend=self.fast_backend,
                    registry=registry,
                    config=self.config,
                )

                thinking_buffer = ""
                sources: list[dict] = []
                agent_trace: dict = {
                    "version": 1,
                    "engine": "agent",
                    "model": self.config.model,
                    "iterations": 0,
                    "stop_reason": "",
                    "messages": [],
                    "tool_call_summary": [],
                    "compactions": [],
                    "usage": {"input_tokens": 0, "output_tokens": 0},
                    "timings": {},
                }

                first_event = True
                async for event in runtime.run(
                    chat_id=chat_id,
                    query=query,
                    history=history,
                    collection_ids=collection_ids,
                    cancellation=token,
                    deps=deps,
                    emit=_noop_emit,
                    transcript=transcript,
                ):
                    if first_event and event.type == "agent_start":
                        event.data["message_id"] = message_id
                        first_event = False

                    if event.type == "agent_thinking":
                        thinking_buffer += event.data.get("delta", "")
                    elif event.type == "sources":
                        docs = event.data.get("documents", [])
                        if isinstance(docs, list):
                            sources.extend(docs)
                    elif event.type == "done":
                        agent_trace["iterations"] = event.data.get("iterations", 0)
                        agent_trace["stop_reason"] = (
                            "halted" if event.data.get("halted") else "end_turn"
                        )
                        usage = event.data.get("usage", {})
                        agent_trace["usage"] = {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                        }

                    yield event

                # Snapshot messages into agent_trace before persisting
                # runtime.run() does not expose its internal messages array,
                # so we reconstruct from the yielded events and history.
                agent_trace["messages"] = self._reconstruct_messages(history, query, thinking_buffer, sources)

                # Persist final answer
                self.chat_message_repo.update(
                    placeholder_id,
                    content=thinking_buffer,
                    sources=json.dumps(sources),
                    message_metadata=json.dumps(agent_trace),
                )
        finally:
            _cancel_registry.pop((chat_id, message_id), None)

    def _load_history(self, chat_id: str) -> list[dict]:
        """Load conversation history for agent mode.

        Only loads messages written by the agent (engine=='agent'),
        stripping intermediate tool_use/tool_result blocks.
        """
        messages: list[dict] = []
        try:
            msgs = self.chat_message_repo.get_by_chat(chat_id, max_messages=50)
        except Exception:
            logger.exception("Failed to load history for chat %s", chat_id)
            return messages

        for msg in msgs:
            if msg.role not in ("user", "assistant"):
                continue
            try:
                meta = json.loads(msg.message_metadata or "{}")
            except json.JSONDecodeError:
                meta = {}
            if meta.get("engine") != "agent":
                continue
            content = msg.content or ""
            messages.append({"role": msg.role, "content": content})

        return messages

    def _get_collection_ids(self, chat_id: str) -> list[str]:
        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if chat is None:
                return []
            raw = chat.collection_ids or "[]"
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return parsed
        except Exception:
            logger.exception("Failed to get collection_ids for chat %s", chat_id)
        return []

    def _reconstruct_messages(
        self,
        history: list[dict],
        query: str,
        thinking_buffer: str,
        sources: list[dict],
    ) -> list[dict]:
        """Reconstruct the full message array for agent_trace.

        This approximates the internal messages array that the runtime built,
        including the user query and final assistant text.
        """
        messages: list[dict] = [dict(m) for m in history]
        messages.append({"role": "user", "content": query})
        if thinking_buffer:
            messages.append({"role": "assistant", "content": thinking_buffer})
        elif sources:
            messages.append({"role": "assistant", "content": json.dumps({"sources": sources})})
        else:
            messages.append({"role": "assistant", "content": ""})
        return messages


async def _noop_emit(event: SSEEvent) -> None:
    """No-op emit for runtime (events are yielded directly)."""
    pass


def get_cancel_token(chat_id: str, message_id: str) -> CancellationToken | None:
    return _cancel_registry.get((chat_id, message_id))
