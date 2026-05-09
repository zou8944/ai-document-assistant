"""Agent runtime: main tool-use loop."""

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from chat.agent.cancellation import CancellationToken
from chat.agent.compaction import auto_compact, estimate_tokens, micro_compact
from chat.agent.loop_detector import LoopDetector
from chat.agent.prompts import LOOP_WARNING_PROMPT, MAX_ITER_PROMPT_SUFFIX, RAG_SYSTEM_PROMPT
from chat.agent.registry import ToolRegistry
from chat.agent.trace import TranscriptWriter
from chat.models import SSEEvent, SSEEventType
from models.config import AgentConfig

if TYPE_CHECKING:
    from chat.agent.llm.base import ToolCallingBackend
    from chat.agent.tools.base import AgentDeps, ToolContext

logger = logging.getLogger(__name__)


@dataclass
class IterationTiming:
    iteration: int
    llm_ms: int = 0
    tools_ms: int = 0


class AgentRuntime:
    """Runs the tool-use agent loop."""

    def __init__(
        self,
        backend: "ToolCallingBackend",
        registry: ToolRegistry,
        config: AgentConfig,
    ):
        self.backend = backend
        self.registry = registry
        self.config = config

    async def run(
        self,
        *,
        chat_id: str,
        query: str,
        history: list[dict],
        collection_ids: list[str],
        cancellation: CancellationToken,
        deps: "AgentDeps",
        emit: Callable[[SSEEvent], Awaitable[None]],
        transcript: TranscriptWriter | None = None,
    ) -> AsyncIterator[SSEEvent]:
        messages: list[dict] = [dict(m) for m in history]
        messages.append({"role": "user", "content": query})

        yield SSEEvent(
            type=SSEEventType.AGENT_START,
            data={"max_iter": self.config.max_iterations, "model": self.config.model},
        )
        if transcript:
            transcript.write_event("agent_start", {"query": query})

        timings: list[IterationTiming] = []
        original_query = query
        loop_detector = LoopDetector(self.config) if self.config.loop_detector_enabled else None
        warning_issued = False

        for iteration in range(1, self.config.max_iterations + 1):
            cancellation.raise_if_cancelled()

            # ---- compaction ----
            token_est = estimate_tokens(messages, self.backend)
            threshold = int(self.config.compact_threshold * self.config.context_window)
            if token_est > threshold:
                yield SSEEvent(
                    type=SSEEventType.COMPACT_TRIGGERED,
                    data={"kind": "auto", "before_tokens": token_est},
                )
                if transcript:
                    transcript.write_event("compact_triggered", {"kind": "auto", "before_tokens": token_est})
                messages = await auto_compact(messages, self.backend, original_query)
            else:
                micro_compact(
                    messages,
                    registry=self.registry,
                    keep_recent=self.config.keep_recent_tool_results,
                )

            yield SSEEvent(type=SSEEventType.ITERATION_START, data={"iteration": iteration})
            if transcript:
                transcript.write_event("iteration_start", {"iteration": iteration})

            # ---- LLM call (streaming) ----
            t0 = time.monotonic()
            text_queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

            async def _on_text_delta(
                delta: str, it: int = iteration, queue: asyncio.Queue = text_queue
            ) -> None:
                await queue.put(
                    SSEEvent(type=SSEEventType.AGENT_THINKING, data={"delta": delta, "iteration": it})
                )

            turn = await self.backend.generate_with_tools(
                system=self._system_prompt(collection_ids),
                messages=messages,
                tools=self.registry.schemas(),
                max_tokens=8192,
                temperature=0.7,
                cancellation=cancellation,
                on_text_delta=_on_text_delta,
            )
            llm_ms = int((time.monotonic() - t0) * 1000)

            # Drain queued text deltas (yield them so caller/frontend sees stream)
            while not text_queue.empty():
                yield text_queue.get_nowait()

            # Critical: append assistant raw_content verbatim (includes tool_use blocks)
            messages.append({"role": "assistant", "content": turn.raw_content})
            if transcript:
                transcript.write_event("assistant_turn", {
                    "iteration": iteration,
                    "stop_reason": turn.stop_reason,
                    "usage": {
                        "input_tokens": turn.usage.input_tokens,
                        "output_tokens": turn.usage.output_tokens,
                    },
                })

            if turn.stop_reason != "tool_use":
                yield SSEEvent(type=SSEEventType.FINAL_TEXT_PROMOTE, data={"iteration": iteration})
                if transcript:
                    transcript.write_event("final_text_promote", {"iteration": iteration})

                yield SSEEvent(
                    type=SSEEventType.DONE,
                    data={
                        "iterations": iteration,
                        "usage": {
                            "input_tokens": turn.usage.input_tokens,
                            "output_tokens": turn.usage.output_tokens,
                        },
                    },
                )
                if transcript:
                    transcript.write_event("done", {"iterations": iteration})
                return

            # ---- run tools ----
            t1 = time.monotonic()
            tool_ctx = self._build_tool_context(
                chat_id=chat_id,
                collection_ids=collection_ids,
                cancellation=cancellation,
                emit=emit,
                deps=deps,
            )

            results: list[dict] = []
            for tu in turn.tool_uses:
                yield SSEEvent(
                    type=SSEEventType.TOOL_CALL,
                    data={"id": tu.id, "name": tu.name, "input": tu.input},
                )
                if transcript:
                    transcript.write_event("tool_call", {"id": tu.id, "name": tu.name, "input": tu.input})

                try:
                    cancellation.raise_if_cancelled()
                    tool = self.registry.handler(tu.name)
                    out = await tool.run(ctx=tool_ctx, **tu.input)

                    yield SSEEvent(
                        type=SSEEventType.TOOL_RESULT,
                        data={
                            "id": tu.id,
                            "name": tu.name,
                            "preview": out.content[:500],
                            "structured": out.structured,
                            "is_error": out.is_error,
                            "ms": int((time.monotonic() - t1) * 1000),
                        },
                    )
                    if transcript:
                        transcript.write_event("tool_result", {
                            "id": tu.id,
                            "name": tu.name,
                            "is_error": out.is_error,
                        })
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": out.content,
                            "is_error": out.is_error,
                        }
                    )
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    logger.exception("tool %s failed", tu.name)
                    err_msg = f"Error: {type(exc).__name__}: {exc}"
                    yield SSEEvent(
                        type=SSEEventType.TOOL_RESULT,
                        data={
                            "id": tu.id,
                            "name": tu.name,
                            "preview": err_msg,
                            "is_error": True,
                        },
                    )
                    if transcript:
                        transcript.write_event("tool_result", {"id": tu.id, "name": tu.name, "is_error": True})
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": tu.id,
                            "content": err_msg,
                            "is_error": True,
                        }
                    )

            tools_ms = int((time.monotonic() - t1) * 1000)
            timings.append(IterationTiming(iteration=iteration, llm_ms=llm_ms, tools_ms=tools_ms))
            messages.append({"role": "user", "content": results})

            # ---- loop detection ----
            if loop_detector is not None:
                detection = loop_detector.analyze(messages, iteration)
                if detection.is_loop:
                    if not warning_issued:
                        warning_issued = True
                        messages.append({"role": "user", "content": LOOP_WARNING_PROMPT})
                        yield SSEEvent(
                            type=SSEEventType.AGENT_HALTED,
                            data={"reason": "loop_warning", "iteration": iteration, "detail": detection.reason},
                        )
                        if transcript:
                            transcript.write_event("loop_warning", {"iteration": iteration, "reason": detection.reason})
                    else:
                        yield SSEEvent(
                            type=SSEEventType.AGENT_HALTED,
                            data={"reason": "loop_detected", "iteration": iteration, "detail": detection.reason},
                        )
                        if transcript:
                            transcript.write_event("agent_halted", {"reason": "loop_detected"})
                        async for event in self._force_final_answer(
                            messages, collection_ids, cancellation, iteration, "loop_detected", transcript
                        ):
                            yield event
                        return

        # max_iterations reached
        yield SSEEvent(
            type=SSEEventType.AGENT_HALTED,
            data={"reason": "max_iterations", "iterations": self.config.max_iterations},
        )
        if transcript:
            transcript.write_event("agent_halted", {"reason": "max_iterations"})
        async for event in self._force_final_answer(
            messages, collection_ids, cancellation, self.config.max_iterations, "max_iterations", transcript
        ):
            yield event

    async def _force_final_answer(
        self,
        messages: list[dict],
        collection_ids: list[str],
        cancellation: CancellationToken,
        iteration: int,
        reason: str,
        transcript: TranscriptWriter | None,
    ) -> AsyncIterator[SSEEvent]:
        """Force a final answer without tools."""
        text_queue: asyncio.Queue[SSEEvent] = asyncio.Queue()

        async def _on_final_delta(d: str) -> None:
            await text_queue.put(
                SSEEvent(type=SSEEventType.AGENT_THINKING, data={"delta": d, "iteration": -1})
            )

        final_turn = await self.backend.generate_with_tools(
            system=self._system_prompt(collection_ids) + MAX_ITER_PROMPT_SUFFIX,
            messages=messages,
            tools=[],
            max_tokens=4096,
            temperature=0.7,
            cancellation=cancellation,
            on_text_delta=_on_final_delta,
        )

        # Drain queued text deltas so caller/frontend sees the stream
        while not text_queue.empty():
            yield text_queue.get_nowait()

        messages.append({"role": "assistant", "content": final_turn.raw_content})

        yield SSEEvent(type=SSEEventType.FINAL_TEXT_PROMOTE, data={"iteration": -1})
        if transcript:
            transcript.write_event("final_text_promote", {"iteration": -1})

        yield SSEEvent(
            type=SSEEventType.DONE,
            data={
                "iterations": iteration,
                "halted": True,
                "reason": reason,
                "usage": {
                    "input_tokens": final_turn.usage.input_tokens,
                    "output_tokens": final_turn.usage.output_tokens,
                },
            },
        )
        if transcript:
            transcript.write_event("done", {"iterations": iteration, "halted": True, "reason": reason})

    def _system_prompt(self, collection_ids: list[str]) -> str:
        return RAG_SYSTEM_PROMPT

    def _build_tool_context(
        self,
        chat_id: str,
        collection_ids: list[str],
        cancellation: CancellationToken,
        emit: Callable[[SSEEvent], Awaitable[None]],
        deps: "AgentDeps",
    ) -> "ToolContext":
        from chat.agent.tools.base import ToolContext

        return ToolContext(
            chat_id=chat_id,
            collection_ids=collection_ids,
            cancellation=cancellation,
            emit=emit,
            deps=deps,
        )
