"""Tests for TranscriptWriter."""

import json
from pathlib import Path

import pytest

from chat.agent.trace import TranscriptWriter


class TestWriteEvent:
    def test_writes_jsonl_lines(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-1", "msg-1")
        writer.write_event("agent_start", {"query": "hello"})
        writer.write_event("done", {"iterations": 1})
        writer.close()

        path = tmp_path / "chat-1_msg-1.jsonl"
        assert path.exists()

        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2

        first = json.loads(lines[0])
        assert first["type"] == "agent_start"
        assert first["data"] == {"query": "hello"}
        assert "ts" in first

        second = json.loads(lines[1])
        assert second["type"] == "done"
        assert second["data"] == {"iterations": 1}

    def test_creates_directory_if_missing(self, tmp_path):
        nested = tmp_path / "nested" / "dir"
        writer = TranscriptWriter(str(nested), "chat-2", "msg-2")
        writer.write_event("test", {})
        writer.close()

        assert (nested / "chat-2_msg-2.jsonl").exists()

    def test_open_is_idempotent(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-3", "msg-3")
        writer.open()
        writer.open()  # should not raise or reopen
        writer.write_event("x", {})
        writer.close()

        path = tmp_path / "chat-3_msg-3.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1


class TestClose:
    def test_closes_file(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-4", "msg-4")
        writer.write_event("x", {})
        writer.close()

        # After close, _open should be False
        assert writer._open is False

    def test_close_is_idempotent(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-5", "msg-5")
        writer.write_event("x", {})
        writer.close()
        writer.close()  # should not raise
        assert writer._open is False

    def test_write_after_close_opens_again(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-6", "msg-6")
        writer.write_event("before", {})
        writer.close()
        writer.write_event("after", {})
        writer.close()

        path = tmp_path / "chat-6_msg-6.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2


class TestContextManager:
    def test_enter_opens_and_returns_self(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-7", "msg-7")
        with writer as w:
            assert w is writer
            assert writer._open is True
            writer.write_event("inside", {})

        assert writer._open is False

    def test_exit_closes_on_exception(self, tmp_path):
        writer = TranscriptWriter(str(tmp_path), "chat-8", "msg-8")
        with pytest.raises(ValueError):
            with writer:
                writer.write_event("before_error", {})
                raise ValueError("boom")

        assert writer._open is False
        path = tmp_path / "chat-8_msg-8.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        assert json.loads(lines[0])["type"] == "before_error"
