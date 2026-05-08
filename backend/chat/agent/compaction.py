"""Context compaction for agent conversations."""

import json
import logging
from typing import TYPE_CHECKING

from chat.agent.prompts import COMPACT_SUMMARY_PROMPT

if TYPE_CHECKING:
    from chat.agent.llm.base import ToolCallingBackend
    from chat.agent.registry import ToolRegistry

logger = logging.getLogger(__name__)


def estimate_tokens(messages: list[dict], backend: "ToolCallingBackend | None" = None) -> int:
    """Estimate token count for a messages array.

    Tries count_tokens API first, falls back to len/4 heuristic.
    """
    if backend is not None and hasattr(backend, "count_tokens"):
        try:
            return backend.count_tokens(messages)
        except Exception:
            pass
    # Fallback heuristic: ~4 chars per token for CJK/code mix
    text = json.dumps(messages, ensure_ascii=False)
    return len(text) // 4


def micro_compact(
    messages: list[dict],
    registry: "ToolRegistry",
    keep_recent: int = 2,
) -> None:
    """Lightweight compaction: replace old non-preserve tool results with placeholders.

    Operates in-place on *messages*.
    """
    preserve = registry.get_preserve_set()

    # Build (msg_index, part_index) -> tool_name mapping by scanning assistant turns
    tool_use_names: dict[str, str] = {}
    for msg in messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                tool_use_names[block.get("id", "")] = block.get("name", "")

    # Count total assistant/tool_use turns to determine "old" threshold
    assistant_turns = sum(
        1 for m in messages if m.get("role") == "assistant"
    )
    old_threshold = assistant_turns - keep_recent

    current_assistant_turn = 0
    for msg in messages:
        if msg.get("role") == "assistant":
            current_assistant_turn += 1

        if msg.get("role") != "user":
            continue

        content = msg.get("content", [])
        if not isinstance(content, list):
            continue

        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            tu_id = block.get("tool_use_id", "")
            tool_name = tool_use_names.get(tu_id, "")

            if tool_name in preserve:
                continue

            # This tool_result is "old" if its corresponding assistant turn
            # is before the threshold. We approximate by counting assistant turns
            # up to this message.
            turns_before = sum(
                1
                for m in messages[: messages.index(msg)]
                if m.get("role") == "assistant"
            )
            if turns_before < old_threshold:
                block["content"] = (
                    f"[Compacted: tool '{tool_name}' was called, "
                    f"result omitted to save context]"
                )
                block["is_error"] = False


def _format_messages_for_summary(messages: list[dict]) -> str:
    """Format messages into a text string for LLM summarisation."""
    parts: list[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            # Extract text from blocks
            texts = []
            for block in content:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        texts.append(block.get("text", ""))
                    elif block.get("type") == "tool_result":
                        texts.append(f"[tool_result: {block.get('content', '')[:200]}]")
                    elif block.get("type") == "tool_use":
                        texts.append(
                            f"[tool_use: {block.get('name', '')} "
                            f"input={block.get('input', {})}]"
                        )
            content = "\n".join(texts)
        parts.append(f"{role}: {content[:500]}")
    return "\n\n".join(parts)


async def auto_compact(
    messages: list[dict],
    fast_backend: "ToolCallingBackend",
    original_query: str,
) -> list[dict]:
    """Heavy compaction: summarise middle portion into a single user message.

    Returns a new messages list. Preserves first user message and last
    assistant+user pair; everything in between is summarised.
    """
    if len(messages) <= 3:
        # Too short to compact meaningfully
        return messages

    first = messages[0]
    last_pair = messages[-2:] if len(messages) >= 2 else []
    middle = messages[1:-2] if len(messages) >= 3 else []

    summary_input = _format_messages_for_summary(middle)
    prompt = (
        f"{COMPACT_SUMMARY_PROMPT}\n\n"
        f"Original user question: {original_query}\n\n"
        f"Agent work log:\n{summary_input}"
    )

    try:
        turn = await fast_backend.generate_with_tools(
            system=prompt,
            messages=[{"role": "user", "content": "Please summarise."}],
            tools=[],
            max_tokens=4096,
            temperature=0.0,
            cancellation=None,  # type: ignore[arg-type]
        )
        # Extract text from assistant turn
        summary_text = ""
        for block in turn.raw_content:
            if isinstance(block, dict) and block.get("type") == "text":
                summary_text += block.get("text", "")
    except Exception:
        logger.exception("auto_compact LLM call failed")
        summary_text = "[Auto-compact failed: context too large]"

    compacted = [first]
    compacted.append(
        {"role": "user", "content": f"[Context summary]\n\n{summary_text}"}
    )
    compacted.extend(last_pair)
    return compacted
