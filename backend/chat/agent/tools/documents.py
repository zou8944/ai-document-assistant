"""Document read tools for the agent."""

from chat.agent.tools.base import Tool, ToolContext, ToolResult


class GetDocumentTool(Tool):
    """Fetch full document content with pagination."""

    name = "get_document"
    description = (
        "按 document_id 取整篇 Markdown 内容。"
        "只在已通过 search_documents 或 grep_documents 定位到关键文档后才调用。"
        "支持分页，避免单次塞爆上下文。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
            "page": {"type": "integer", "default": 1},
            "page_size_tokens": {"type": "integer", "default": 2000},
        },
        "required": ["document_id"],
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        document_id: str = kwargs.get("document_id", "")
        page: int = kwargs.get("page", 1)
        page_size_tokens: int = kwargs.get("page_size_tokens", 2000)

        # Defensive: strip "doc_" prefix if LLM hallucinates it (legacy format or misread)
        if document_id.startswith("doc_"):
            document_id = document_id[4:]

        if not document_id:
            return ToolResult(content="Error: document_id is required", is_error=True)

        try:
            ctx.cancellation.raise_if_cancelled()
            doc = ctx.deps.document_repo.get_by_id(document_id)
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)

        if doc is None:
            return ToolResult(
                content=f"Error: document {document_id} not found",
                is_error=True,
            )

        content = doc.content or ""
        if not content:
            return ToolResult(
                content=f"Error: document {document_id} has no content",
                is_error=True,
            )

        # Approximate token pagination using chars (avg 4 chars/token for CJK/code mix)
        avg_chars_per_token = 4
        page_size_chars = page_size_tokens * avg_chars_per_token
        total_pages = max(1, (len(content) + page_size_chars - 1) // page_size_chars)

        if page < 1:
            page = 1
        if page > total_pages:
            page = total_pages

        start = (page - 1) * page_size_chars
        end = start + page_size_chars
        chunk = content[start:end]

        lines = [
            f'Document {doc.id} "{doc.name}" (page {page}/{total_pages}, ~{page_size_tokens} tokens):',
            "---",
            chunk,
        ]
        if page < total_pages:
            lines.append(f"\n(... page {page + 1}/{total_pages} available via get_document)")

        return ToolResult(content="\n".join(lines))


class GetDocumentSummaryTool(Tool):
    """Fetch lightweight summary for a document."""

    name = "get_document_summary"
    description = (
        "只取文档的 summary、keywords、category、字数；"
        "用于判断一篇文档是否值得调用 get_document 拉全文。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "document_id": {"type": "string"},
        },
        "required": ["document_id"],
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        document_id: str = kwargs.get("document_id", "")

        # Defensive: strip "doc_" prefix if LLM hallucinates it (legacy format or misread)
        if document_id.startswith("doc_"):
            document_id = document_id[4:]

        if not document_id:
            return ToolResult(content="Error: document_id is required", is_error=True)

        try:
            ctx.cancellation.raise_if_cancelled()
            summary = ctx.deps.document_repo.get_summary_only(document_id)
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)

        if summary is None:
            return ToolResult(
                content=f"Error: document {document_id} not found",
                is_error=True,
            )

        from chat.agent.tools._formatting import parse_json_keywords

        name = summary.get("name") or "(unnamed)"
        category = summary.get("category") or "(none)"
        keywords_raw = summary.get("keywords")
        kw_list = parse_json_keywords(keywords_raw)
        keywords = ", ".join(kw_list) if kw_list else "(none)"
        total_tokens = summary.get("total_tokens") or 0
        doc_summary = summary.get("summary") or "(no summary)"

        lines = [
            f'Summary for {document_id} "{name}":',
            f"- category: {category}",
            f"- keywords: {keywords}",
            f"- total_tokens: {total_tokens}",
            f"- summary: {doc_summary}",
        ]

        return ToolResult(content="\n".join(lines))


class ListDocumentsTool(Tool):
    """List documents in a collection."""

    name = "list_documents"
    description = (
        "列出指定知识库中的文档，支持按名称筛选和分页。"
        "当用户问'有哪些文档'、'列一下文档'或想浏览知识库内容时使用。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "collection_id": {
                "type": "string",
                "description": "知识库 ID。不传则列出当前会话绑定的所有知识库中的文档。",
            },
            "search": {
                "type": "string",
                "description": "按文档名称模糊筛选（可选）。",
            },
            "offset": {"type": "integer", "default": 0},
            "limit": {"type": "integer", "default": 30},
        },
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        collection_id = kwargs.get("collection_id")
        search = kwargs.get("search")
        offset = kwargs.get("offset", 0)
        limit = kwargs.get("limit", 30)

        try:
            # Determine which collections to query
            if collection_id:
                collection_ids = [collection_id]
            else:
                collection_ids = ctx.collection_ids

            if not collection_ids:
                return ToolResult(content="当前会话未绑定任何知识库。", is_error=True)

            all_docs: list = []
            for cid in collection_ids:
                docs = ctx.deps.document_repo.get_by_collection(
                    cid, exclude_statuses=["failed"], search=search,
                    offset=offset, limit=limit,
                )
                for doc in docs:
                    status_icon = {"indexed": "✓", "processing": "⏳", "pending": "○"}.get(
                        doc.status or "", "?"
                    )
                    all_docs.append(f"  {status_icon} {doc.name} (id: {doc.id})")

            if not all_docs:
                return ToolResult(content="未找到任何文档。")

            lines = [f"共 {len(all_docs)} 篇文档："]
            lines.extend(all_docs)
            return ToolResult(content="\n".join(lines))
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)
