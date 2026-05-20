"""Agent-based chat service replacing legacy ChatService."""

import json
import logging
import time
import uuid
from collections.abc import AsyncIterator

from chat.agent import AgentConfig, AgentDeps, AgentRuntime, build_default_registry
from chat.agent.cancellation import CancellationToken
from chat.agent.llm.base import ToolCallingBackend
from chat.agent.trace import TranscriptWriter
from chat.models import SSEEvent, SSEEventType
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
        config: AgentConfig,
        chat_repo: ChatRepository,
        chat_message_repo: ChatMessageRepository,
        document_repo: DocumentRepository,
        collection_repo: CollectionRepository,
    ):
        self.backend = backend
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
        user_message = self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=query,
            metadata=json.dumps({"engine": "agent"}),
        )
        user_message_id = user_message.id

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
                ui_state: dict = {
                    "steps": [],
                    "finalText": "",
                    "iterations": 0,
                    "status": "running",
                    "halted": False,
                    "answering": False,
                }
                start_time = time.monotonic()

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
                    if first_event and event.type == SSEEventType.AGENT_START:
                        event.data["message_id"] = message_id
                        first_event = False

                    # Update ui_state to mirror frontend AgentMessageState
                    if event.type == SSEEventType.ITERATION_START:
                        iteration = event.data.get("iteration", ui_state["iterations"] + 1)
                        ui_state["iterations"] = iteration
                        ui_state["steps"].append({"kind": "thinking", "iteration": iteration, "text": ""})
                    elif event.type == SSEEventType.AGENT_THINKING:
                        delta = event.data.get("delta", "")
                        iteration = event.data.get("iteration", ui_state["iterations"])
                        if not ui_state["answering"] and iteration != -1:
                            # Normal iteration: update trace step
                            for i in range(len(ui_state["steps"]) - 1, -1, -1):
                                step = ui_state["steps"][i]
                                if step["kind"] == "thinking" and step["iteration"] == iteration and not step.get("hidden"):
                                    step["text"] = step.get("text", "") + delta
                                    break
                            else:
                                ui_state["steps"].append({"kind": "thinking", "iteration": iteration, "text": delta})
                        # answering=True or iteration==-1: skip trace step, thinking_buffer accumulated below
                    elif event.type == SSEEventType.THINKING_DONE:
                        iteration = event.data.get("iteration", ui_state["iterations"])
                        for i in range(len(ui_state["steps"]) - 1, -1, -1):
                            step = ui_state["steps"][i]
                            if step["kind"] == "thinking" and step["iteration"] == iteration and not step.get("hidden"):
                                step["thinkingMs"] = event.data.get("ms")
                                break
                    elif event.type == SSEEventType.TOOL_CALL:
                        ui_state["steps"].append({
                            "kind": "tool",
                            "iteration": ui_state["iterations"],
                            "toolId": event.data.get("id", ""),
                            "toolName": event.data.get("name", ""),
                            "toolInput": event.data.get("input", {}),
                            "toolStatus": "running",
                        })
                    elif event.type == SSEEventType.TOOL_RESULT:
                        tool_id = event.data.get("id", "")
                        for i in range(len(ui_state["steps"]) - 1, -1, -1):
                            step = ui_state["steps"][i]
                            if step["kind"] == "tool" and step.get("toolId") == tool_id:
                                step["toolStatus"] = "error" if event.data.get("is_error") else "done"
                                step["toolPreview"] = event.data.get("preview", "")
                                step["toolMs"] = event.data.get("ms")
                                break
                    elif event.type == SSEEventType.COMPACT_TRIGGERED:
                        ui_state["steps"].append({
                            "kind": "compact",
                            "iteration": ui_state["iterations"],
                            "beforeTokens": event.data.get("before_tokens"),
                            "afterTokens": event.data.get("after_tokens"),
                        })
                    elif event.type == SSEEventType.START_ANSWER:
                        ui_state["answering"] = True
                    elif event.type == SSEEventType.FINAL_TEXT_PROMOTE:
                        iteration = event.data.get("iteration", ui_state["iterations"])
                        for i in range(len(ui_state["steps"]) - 1, -1, -1):
                            step = ui_state["steps"][i]
                            if step["kind"] == "thinking" and step["iteration"] == iteration and not step.get("hidden"):
                                promoted_text = step.get("text", "")
                                step["hidden"] = True
                                if promoted_text:
                                    # Normal flow: thinking text promoted from trace step
                                    ui_state["finalText"] = (
                                        ui_state["finalText"] + "\n\n" + promoted_text
                                        if ui_state["finalText"]
                                        else promoted_text
                                    )
                                    thinking_buffer = promoted_text
                                else:
                                    # Last iteration: thinking was streamed as iteration=-1
                                    # to bubble, thinking_buffer already has the answer
                                    ui_state["finalText"] = thinking_buffer
                                break
                    elif event.type == SSEEventType.AGENT_HALTED:
                        reason = event.data.get("reason")
                        if reason != "loop_warning":
                            ui_state["status"] = "done"
                            ui_state["halted"] = True
                    elif event.type == SSEEventType.DONE:
                        ui_state["status"] = "done"
                        total_ms = int((time.monotonic() - start_time) * 1000)
                        agent_timings = event.data.get("agent_timings", {})
                        ui_state["timings"] = {
                            "total_ms": total_ms,
                            "llm_total_ms": agent_timings.get("llm_total_ms", 0),
                            "tools_total_ms": agent_timings.get("tools_total_ms", 0),
                            "iteration_count": agent_timings.get("iteration_count", 0),
                        }
                        agent_trace["iterations"] = event.data.get("iterations", 0)
                        agent_trace["stop_reason"] = (
                            "halted" if event.data.get("halted") else "end_turn"
                        )
                        usage = event.data.get("usage", {})
                        agent_trace["usage"] = {
                            "input_tokens": usage.get("input_tokens", 0),
                            "output_tokens": usage.get("output_tokens", 0),
                        }

                    if event.type == SSEEventType.AGENT_THINKING:
                        thinking_buffer += event.data.get("delta", "")
                    elif event.type == SSEEventType.SOURCES:
                        docs = event.data.get("documents", [])
                        if isinstance(docs, list):
                            sources.extend(docs)

                    yield event

                # Snapshot messages into agent_trace before persisting
                # runtime.run() does not expose its internal messages array,
                # so we reconstruct from the yielded events and history.
                agent_trace["messages"] = self._reconstruct_messages(history, query, thinking_buffer, sources)
                agent_trace["ui_state"] = ui_state

                # Persist final answer
                self.chat_message_repo.update(
                    placeholder_id,
                    content=thinking_buffer,
                    sources=json.dumps(sources),
                    message_metadata=json.dumps(agent_trace),
                )
        except Exception:
            # Clean up: remove both user message and placeholder on failure
            self.chat_message_repo.delete(placeholder_id)
            self.chat_message_repo.delete(user_message_id)
            self.chat_repo.update_message_count(chat_id)
            raise
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
