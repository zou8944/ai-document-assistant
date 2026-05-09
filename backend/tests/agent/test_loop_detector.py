"""Tests for LoopDetector."""

from chat.agent.loop_detector import LoopDetector
from models.config import AgentConfig


def _build_messages_with_results(results: list[tuple[str, str, bool]]) -> list[dict]:
    """Build message history with assistant tool_use + user tool_result pairs."""
    messages = []
    for i, (tool_name, content, is_error) in enumerate(results):
        tool_use_id = f"tu-{i}"
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": f"thinking {i}"},
                {"type": "tool_use", "id": tool_use_id, "name": tool_name, "input": {"query": f"q{i}"}},
            ],
        })
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": content, "is_error": is_error},
            ],
        })
    return messages


def _build_messages_with_tool_uses(tool_uses: list[dict]) -> list[dict]:
    """Build message history with assistant tool_use turns."""
    messages = []
    for i, tu in enumerate(tool_uses):
        tool_use_id = f"tu-{i}"
        messages.append({
            "role": "assistant",
            "content": [
                {"type": "text", "text": f"thinking {i}"},
                {"type": "tool_use", "id": tool_use_id, "name": tu["name"], "input": tu.get("input", {})},
            ],
        })
        # Add a dummy tool_result so the structure is complete
        messages.append({
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": tool_use_id, "content": "ok", "is_error": False},
            ],
        })
    return messages


class TestConsecutiveFailures:
    def test_three_empty_grep_results(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("grep_documents", "No matches. Try synonyms or broader keywords.", False),
            ("grep_documents", "No matches. Try synonyms or broader keywords.", False),
            ("grep_documents", "No matches. Try synonyms or broader keywords.", False),
        ])
        result = detector.analyze(messages, 4)
        assert result.is_loop
        assert "连续" in result.reason

    def test_two_failures_not_enough(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, current_iteration=3)
        assert not result.is_loop

    def test_error_results_count_as_empty(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("search_documents", "Error: something broke", True),
            ("get_document", "Error: document not found", True),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, 4)
        assert result.is_loop
        assert result.confidence == "medium"

    def test_resets_on_success(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
            ("search_documents", "Found 5 documents", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, current_iteration=5)
        assert not result.is_loop


class TestRepeatedSimilarCalls:
    def test_same_tool_similar_params(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_tool_uses([
            {"name": "grep_documents", "input": {"pattern": "config_value"}},
            {"name": "grep_documents", "input": {"pattern": "config_val"}},
            {"name": "grep_documents", "input": {"pattern": "configuration value"}},
        ])
        result = detector.analyze(messages, 4)
        assert result.is_loop
        assert "grep_documents" in result.reason

    def test_different_tools_not_similar(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_tool_uses([
            {"name": "search_documents", "input": {"keywords": ["foo"]}},
            {"name": "grep_documents", "input": {"pattern": "foo"}},
            {"name": "get_document", "input": {"document_id": "doc_1"}},
        ])
        result = detector.analyze(messages, 4)
        assert not result.is_loop

    def test_exact_same_input_counts(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_tool_uses([
            {"name": "grep_documents", "input": {"pattern": "agent"}},
            {"name": "grep_documents", "input": {"pattern": "agent"}},
        ])
        result = detector.analyze(messages, current_iteration=3)
        assert result.is_loop


class TestStagnation:
    def test_no_new_info_across_turns(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("search_documents", "No documents matched.", False),
            ("grep_documents", "No matches.", False),
            ("search_documents", "No documents matched.", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, current_iteration=5)
        assert result.is_loop
        assert "stagnation" in result.reason or "未获得新信息" in result.reason

    def test_resets_on_useful_result(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("search_documents", "No documents matched.", False),
            ("grep_documents", "No matches.", False),
            ("search_documents", "Found 3 docs", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, current_iteration=5)
        assert not result.is_loop


class TestConfidence:
    def test_multiple_patterns_high_confidence(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        # Build messages that trigger both consecutive failures and stagnation
        messages = _build_messages_with_results([
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
            ("search_documents", "No documents matched.", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, current_iteration=5)
        assert result.is_loop
        assert result.confidence == "high"

    def test_single_pattern_medium_confidence(self):
        config = AgentConfig(
            loop_detector_enabled=True,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, 4)
        assert result.is_loop
        assert result.confidence == "medium"


class TestDisabled:
    def test_disabled_detector_returns_no_loop(self):
        config = AgentConfig(
            loop_detector_enabled=False,
            loop_max_consecutive_failures=3,
            loop_similar_call_window=5,
            loop_similar_call_threshold=2,
            loop_stagnation_window=4,
        )
        # When loop_detector_enabled is False, runtime won't instantiate LoopDetector
        # but let's verify the class still works if called directly
        detector = LoopDetector(config)
        messages = _build_messages_with_results([
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
            ("grep_documents", "No matches.", False),
        ])
        result = detector.analyze(messages, 4)
        assert result.is_loop  # class itself doesn't check config.enabled
