"""Search and grep tools for the agent."""

import re

from chat.agent.tools._formatting import format_doc_summary, format_grep_match, parse_json_keywords
from chat.agent.tools.base import Tool, ToolContext, ToolResult


class VectorSearchTool(Tool):
    """Semantic vector search over document chunks."""

    name = "vector_search"
    description = (
        "语义向量搜索：用自然语言描述你想找的内容，系统会返回语义最相关的文档片段。"
        "适合概念性、同义词或模糊查询，比关键词搜索更能理解意图。"
        "例如：「认证流程怎么工作」「性能优化相关的方法」。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "用自然语言描述你要搜索的内容",
            },
            "top_k": {
                "type": "integer",
                "default": 8,
                "description": "返回的最大结果数",
            },
        },
        "required": ["query"],
    }
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        query: str = kwargs.get("query", "")
        top_k: int = kwargs.get("top_k", 8)

        if not query.strip():
            return ToolResult(content="Error: query is empty", is_error=True)

        if ctx.deps.chunk_index is None:
            return ToolResult(
                content="Error: vector search is not configured (embedding service unavailable).",
                is_error=True,
            )

        try:
            ctx.cancellation.raise_if_cancelled()
            result = await ctx.deps.chunk_index.search(
                query=query,
                top_k=top_k,
                collection_ids=ctx.collection_ids or None,
            )
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)

        # Enforce @ document filter
        docs = result.documents
        if ctx.document_ids:
            allowed = set(ctx.document_ids)
            docs = [d for d in docs if d.document_id in allowed]

        if not docs:
            return ToolResult(
                content="No relevant chunks found. Try rephrasing your query or use search_documents for keyword-based search."
            )

        lines = [f"Found {len(docs)} semantically relevant chunks (query: \"{query}\"):"]
        seen_doc_ids: set[str] = set()
        for doc in docs:
            preview = (doc.content or "")[:300]
            lines.append(
                f'[id={doc.document_id}, chunk={doc.chunk_index}, score={doc.relevance_score:.2f}] '
                f'doc="{doc.document_name}"\n  {preview}'
            )
            if doc.document_id:
                seen_doc_ids.add(doc.document_id)

        return ToolResult(
            content="\n".join(lines),
            structured={"doc_ids": list(seen_doc_ids)},
        )


class SearchDocumentsTool(Tool):
    """Search documents by keywords across metadata fields."""

    name = "search_documents"
    description = (
        "按主题或类别筛选文档列表。当你需要了解有哪些文档与某个主题相关，"
        "或想按关键词/类别查找文档时调用此工具。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "keywords": {"type": "array", "items": {"type": "string"}},
            "collection_ids": {"type": "array", "items": {"type": "string"}},
            "category": {"type": "string"},
            "limit": {"type": "integer", "default": 15},
        },
        "required": ["keywords"],
    }
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        keywords: list[str] = kwargs.get("keywords", [])
        collection_ids: list[str] | None = kwargs.get("collection_ids")
        category: str | None = kwargs.get("category")
        limit: int = kwargs.get("limit", 15)

        # When user has @-ed specific documents, restrict search to those only
        if ctx.document_ids:
            collection_ids = None  # ignore any LLM-supplied collection_ids

        try:
            ctx.cancellation.raise_if_cancelled()
            docs = ctx.deps.document_repo.search_by_keywords(
                keywords=keywords,
                collection_ids=collection_ids or None,
                category=category or None,
                limit=limit,
            )
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)

        # Enforce document_ids filter on results
        if ctx.document_ids:
            allowed = set(ctx.document_ids)
            docs = [d for d in docs if d.id in allowed]

        if not docs:
            return ToolResult(
                content=(
                    "No documents matched. Try broader keywords "
                    "or use list_collections to browse available collections."
                )
            )

        lines = [f"Found {len(docs)} documents for keywords={keywords}:"]
        for doc in docs:
            lines.append(
                format_doc_summary(
                    doc_id=doc.id,
                    title=doc.name,
                    category=doc.category,
                    summary=doc.summary,
                    keywords=parse_json_keywords(doc.keywords),
                )
            )

        return ToolResult(
            content="\n".join(lines),
            structured={"doc_ids": [doc.id for doc in docs]},
        )


class GrepDocumentsTool(Tool):
    """Grep-like search inside document contents."""

    name = "grep_documents"
    description = (
        "定位具体术语、配置项、函数名或短语在哪几篇文档的什么位置出现。"
        "这是细粒度检索手段，适用于查找代码片段、配置示例或特定概念。"
    )
    input_schema = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string"},
            "collection_ids": {"type": "array", "items": {"type": "string"}},
            "category": {"type": "string"},
            "regex": {"type": "boolean", "default": False},
            "case_sensitive": {"type": "boolean", "default": False},
            "max_matches": {"type": "integer", "default": 20},
            "context_lines": {"type": "integer", "default": 2},
        },
        "required": ["pattern"],
    }
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        pattern: str = kwargs.get("pattern", "")
        collection_ids: list[str] | None = kwargs.get("collection_ids")
        category: str | None = kwargs.get("category")
        use_regex: bool = kwargs.get("regex", False)
        case_sensitive: bool = kwargs.get("case_sensitive", False)
        max_matches: int = kwargs.get("max_matches", 20)
        context_lines: int = kwargs.get("context_lines", 2)

        try:
            ctx.cancellation.raise_if_cancelled()
            if ctx.document_ids:
                # User @-ed specific documents — only grep those
                candidates = []
                for did in ctx.document_ids:
                    ctx.cancellation.raise_if_cancelled()
                    doc = ctx.deps.document_repo.get_by_id(did)
                    if doc:
                        candidates.append(doc)
            elif collection_ids:
                candidates: list = []
                for cid in collection_ids:
                    ctx.cancellation.raise_if_cancelled()
                    candidates.extend(
                        ctx.deps.document_repo.get_by_collection(collection_id=cid)
                    )
            else:
                ctx.cancellation.raise_if_cancelled()
                candidates = ctx.deps.document_repo.get_all(limit=1000)
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)

        if category:
            candidates = [d for d in candidates if d.category == category]

        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            if use_regex:
                compiled = re.compile(pattern, flags)
            else:
                compiled = re.compile(re.escape(pattern), flags)
        except re.error as exc:
            return ToolResult(
                content=f"Error: invalid regex: {exc}", is_error=True
            )

        matches: list[tuple] = []
        for doc in candidates:
            ctx.cancellation.raise_if_cancelled()
            content = doc.content or ""
            if not content:
                continue

            lines = content.splitlines()
            for idx, line in enumerate(lines, start=1):
                if compiled.search(line):
                    start = max(0, idx - context_lines - 1)
                    end = min(len(lines), idx + context_lines)
                    context = "\n".join(lines[start:end])
                    matches.append((doc.id, doc.name, idx, context))
                    if len(matches) >= max_matches:
                        break
            if len(matches) >= max_matches:
                break

        if not matches:
            return ToolResult(
                content="No matches. Try synonyms or broader keywords."
            )

        lines = [f'Found {len(matches)} matches for pattern "{pattern}":']
        for doc_id, doc_name, line_num, context in matches:
            lines.append(
                format_grep_match(
                    doc_id=doc_id,
                    doc_name=doc_name,
                    line_num=line_num,
                    context=context,
                )
            )

        if len(matches) >= max_matches:
            lines.append(
                f"\n(Results truncated to {max_matches} matches. "
                "Refine your pattern for more precise results.)"
            )

        unique_doc_ids: list[str] = []
        seen: set[str] = set()
        for doc_id, _doc_name, _line_num, _context in matches:
            if doc_id not in seen:
                seen.add(doc_id)
                unique_doc_ids.append(doc_id)

        return ToolResult(
            content="\n".join(lines),
            structured={"doc_ids": unique_doc_ids},
        )
