"""Loop detector for agent tool-use cycles."""

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from models.config import AgentConfig

logger = logging.getLogger(__name__)


@dataclass
class LoopDetectionResult:
    is_loop: bool
    reason: str = ""
    confidence: str = "low"


class LoopDetector:
    """Detects ineffective search loops by analyzing agent message history."""

    EMPTY_PATTERNS = (
        "no matches",
        "no documents matched",
        "not found",
    )

    def __init__(self, config: "AgentConfig") -> None:
        self.config = config

    def analyze(self, messages: list[dict], current_iteration: int) -> LoopDetectionResult:
        """Analyze message history for loop patterns."""
        reasons: list[str] = []
        triggered = 0

        count, reason = self._count_consecutive_failures(messages)
        if count >= self.config.loop_max_consecutive_failures:
            reasons.append(reason)
            triggered += 1

        count, reason = self._count_repeated_tool_calls(messages)
        if count >= self.config.loop_similar_call_threshold:
            reasons.append(reason)
            triggered += 1

        count, reason = self._count_stagnation_turns(messages)
        if count >= self.config.loop_stagnation_window:
            reasons.append(reason)
            triggered += 1

        if not reasons:
            return LoopDetectionResult(is_loop=False)

        confidence = "high" if triggered >= 2 else "medium"
        return LoopDetectionResult(
            is_loop=True,
            reason="; ".join(reasons),
            confidence=confidence,
        )

    def _is_empty_or_error(self, block: dict) -> bool:
        """Check if a tool_result block indicates failure or empty result."""
        if block.get("is_error"):
            return True
        content = str(block.get("content", "")).lower().strip()
        if not content:
            return True
        return any(p in content for p in self.EMPTY_PATTERNS)

    def _count_consecutive_failures(self, messages: list[dict]) -> tuple[int, str]:
        """Count consecutive user turns where all tool results are empty/error."""
        count = 0
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            tool_results = [
                b for b in content
                if isinstance(b, dict) and b.get("type") == "tool_result"
            ]
            if not tool_results:
                continue

            if all(self._is_empty_or_error(tr) for tr in tool_results):
                count += 1
            else:
                count = 0

        if count > 0:
            return count, f"连续 {count} 次工具调用未获得有效结果"
        return 0, ""

    def _count_repeated_tool_calls(self, messages: list[dict]) -> tuple[int, str]:
        """Count max repeated similar calls of the same tool in recent window."""
        tool_calls: list[tuple[str, dict]] = []
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls.append((block.get("name", ""), block.get("input", {})))

        window = self.config.loop_similar_call_window
        if len(tool_calls) < 2:
            return 0, ""

        recent = tool_calls[-window:]
        max_group = 0
        best_name = ""

        for i, (name_i, input_i) in enumerate(recent):
            group = 1
            for j in range(i + 1, len(recent)):
                name_j, input_j = recent[j]
                if name_i == name_j and self._inputs_similar(input_i, input_j):
                    group += 1
            if group > max_group:
                max_group = group
                best_name = name_i

        if max_group >= self.config.loop_similar_call_threshold:
            return max_group, f"最近 {len(recent)} 轮中 {best_name} 被重复调用 {max_group} 次"

        return 0, ""

    @staticmethod
    def _inputs_similar(a: dict, b: dict) -> bool:
        """Check if two tool input dicts are similar."""
        if a == b:
            return True

        str_a = " ".join(str(v).lower() for v in a.values() if isinstance(v, str))
        str_b = " ".join(str(v).lower() for v in b.values() if isinstance(v, str))

        if not str_a or not str_b:
            return a == b

        # Substring check only when both strings are long enough to avoid
        # false positives (e.g. "a" in "ab").
        if len(str_a) >= 3 and len(str_b) >= 3 and (str_a in str_b or str_b in str_a):
            return True

        set_a = set(str_a.split())
        set_b = set(str_b.split())
        intersection = len(set_a & set_b)
        union = len(set_a | set_b)
        if union == 0:
            return False
        return intersection / union > 0.5

    def _count_stagnation_turns(self, messages: list[dict]) -> tuple[int, str]:
        """Count recent turns with no useful information."""
        empty_turns = 0
        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", [])
            if not isinstance(content, list):
                continue

            tool_results = [
                b for b in content
                if isinstance(b, dict) and b.get("type") == "tool_result"
            ]
            if not tool_results:
                continue

            has_useful = any(not self._is_empty_or_error(tr) for tr in tool_results)
            if not has_useful:
                empty_turns += 1
            else:
                empty_turns = 0

        if empty_turns >= self.config.loop_stagnation_window:
            return empty_turns, f"最近 {empty_turns} 轮检索均未获得新信息"

        return 0, ""
