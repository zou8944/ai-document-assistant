"""Citation tool: lets the LLM declare the documents it referenced."""

from chat.agent.tools.base import Tool, ToolContext, ToolResult


class CiteSourcesTool(Tool):
    """Record the documents the LLM declares as references for its final answer."""

    name = "cite_sources"
    description = (
        "在你输出最终回答前必须调用此工具,声明本次回答实际引用了哪些文档。"
        "传入 document_ids 列表(可为空数组,表示未引用任何文档)。"
        "只允许传入你在本轮中已经通过 search_documents / grep_documents / "
        "get_document / get_document_summary 接触过的 document_id。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "document_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "要声明引用的文档 ID 列表",
            },
        },
        "required": ["document_ids"],
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        raw_ids = kwargs.get("document_ids", []) or []
        if not isinstance(raw_ids, list):
            return ToolResult(
                content="Error: document_ids must be a list of strings",
                is_error=True,
            )

        sources: list[dict] = []
        rejected: list[str] = []

        for raw_id in raw_ids:
            doc_id = str(raw_id or "").strip()
            if doc_id.startswith("doc_"):
                doc_id = doc_id[4:]
            if not doc_id:
                continue

            if doc_id not in ctx.visited_doc_ids:
                rejected.append(doc_id)
                continue

            ctx.cancellation.raise_if_cancelled()
            try:
                summary = ctx.deps.document_repo.get_summary_only(doc_id)
            except Exception:
                rejected.append(doc_id)
                continue

            if summary is None:
                rejected.append(doc_id)
                continue

            name = summary.get("name") or "(unnamed)"
            doc_summary = summary.get("summary") or ""
            uri = summary.get("uri") or ""
            sources.append(
                {
                    "document_id": doc_id,
                    "document_name": name,
                    "document_uri": uri,
                    "chunk_index": 0,
                    "content_preview": doc_summary[:300],
                    "relevance_score": 1.0,
                }
            )

        parts = [f"Recorded {len(sources)} citation(s)."]
        if rejected:
            rejected_text = ", ".join(rejected)
            parts.append(
                f"Rejected {len(rejected)} id(s) (not visited this turn): {rejected_text}"
            )

        return ToolResult(
            content=" ".join(parts),
            structured={"sources": sources},
        )
