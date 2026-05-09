"""Tests for chat.agent.tools._formatting."""

import pytest

from chat.agent.tools._formatting import format_doc_summary, format_grep_match, parse_json_keywords


class TestParseJsonKeywords:
    def test_valid_json_list(self):
        result = parse_json_keywords('["a", "b", "c"]')
        assert result == ["a", "b", "c"]

    def test_valid_json_list_with_integers(self):
        result = parse_json_keywords('[1, 2, 3]')
        assert result == ["1", "2", "3"]

    def test_empty_string(self):
        result = parse_json_keywords("")
        assert result is None

    def test_none(self):
        result = parse_json_keywords(None)
        assert result is None

    def test_invalid_json(self):
        result = parse_json_keywords("not json")
        assert result is None

    def test_json_string_not_list(self):
        result = parse_json_keywords('"just a string"')
        assert result is None

    def test_json_dict_not_list(self):
        result = parse_json_keywords('{"key": "value"}')
        assert result is None

    def test_empty_list(self):
        result = parse_json_keywords("[]")
        assert result == []


class TestFormatDocSummary:
    def test_basic(self):
        result = format_doc_summary("d1", "Title", None, None, None)
        assert result == '[id=d1] "Title" | '

    def test_with_category_and_keywords(self):
        result = format_doc_summary("d1", "Title", "guide", "Summary", ["kw1", "kw2"])
        assert "[id=d1]" in result
        assert '"Title"' in result
        assert "category=guide" in result
        assert "keywords=kw1, kw2" in result
        assert "Summary" in result

    def test_title_with_quotes_escaped(self):
        result = format_doc_summary("d1", 'Title "quoted"', None, None, None)
        assert '"Title \'quoted\'"' in result

    def test_summary_truncated(self):
        long_summary = "x" * 300
        result = format_doc_summary("d1", "Title", None, long_summary, None)
        assert len(result.split(" | ")[-1]) == 200


class TestFormatGrepMatch:
    def test_basic(self):
        result = format_grep_match("d1", "file.md", 5, "context")
        assert "[id=d1, line=5]" in result
        assert 'doc="file.md"' in result
        assert "context" in result
