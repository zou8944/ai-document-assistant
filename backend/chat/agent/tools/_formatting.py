"""Shared formatting helpers for tool outputs."""


def format_doc_summary(doc_id: str, title: str, category: str | None,
                       summary: str | None, keywords: list[str] | None) -> str:
    """Format a single document summary line."""
    kw = f" | keywords={keywords}" if keywords else ""
    cat = f" | category={category}" if category else ""
    sm = (summary or "")[:200]
    return f"[doc:{doc_id}] {title}{cat} | {sm}{kw}"


def format_grep_match(doc_id: str, doc_name: str, line_num: int,
                      context: str) -> str:
    """Format a single grep match line."""
    return f"[doc_{doc_id}:L{line_num}] | doc=\"{doc_name}\" | \"{context}\""
