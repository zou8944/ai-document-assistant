"""Shared formatting helpers for tool outputs."""

import json


def parse_json_keywords(kw: str | None) -> list[str] | None:
    """Parse a JSON string of keywords into a list of strings."""
    if not isinstance(kw, str) or not kw:
        return None
    try:
        parsed = json.loads(kw)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except json.JSONDecodeError:
        pass
    return None


def format_doc_summary(doc_id: str, title: str, category: str | None,
                       summary: str | None, keywords: list[str] | None) -> str:
    """Format a single document summary with clear separation for relevance checking."""
    safe_title = title.replace('"', "'")
    kw = f" | keywords={', '.join(keywords)}" if keywords else ""
    cat = f" | category={category}" if category else ""
    sm = (summary or "")[:400]
    return f'[id={doc_id}] "{safe_title}"{cat}\n  summary: {sm}{kw}'


def format_grep_match(doc_id: str, doc_name: str, line_num: int,
                      context: str) -> str:
    """Format a single grep match line."""
    return f"[id={doc_id}, line={line_num}] | doc=\"{doc_name}\" | \"{context}\""
