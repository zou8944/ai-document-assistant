"""Agent tools for querying collection / knowledge-base metadata."""

import json

from chat.agent.tools._formatting import format_doc_summary, parse_json_keywords
from chat.agent.tools.base import Tool, ToolContext, ToolResult


class ListCollectionsTool(Tool):
    """List the collections bound to the current chat."""

    name = "list_collections"
    description = (
        "列出当前会话绑定的所有可用知识库。"
        "在会话开始时调用，以便了解用户可以访问哪些文档集合。"
    )
    input_schema = {
        "type": "object",
        "properties": {},
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        try:
            if not ctx.collection_ids:
                return ToolResult(content="No collections bound to this chat.")

            collections = []
            for cid in ctx.collection_ids:
                col = ctx.deps.collection_repo.get_by_id(cid)
                if col:
                    collections.append(col)

            if not collections:
                return ToolResult(content="No collections bound to this chat.")

            lines = [f"Available collections ({len(collections)}):"]
            for col in collections:
                doc_count = col.document_count or 0
                summary = (col.summary or "")[:60]
                lines.append(
                    f'- id={col.id} | name="{col.name}" | docs={doc_count} | "{summary}..."'
                )

            return ToolResult(content="\n".join(lines))
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)


class GetCollectionOverviewTool(Tool):
    """Get detailed overview for a single collection."""

    name = "get_collection_overview"
    description = "获取单个知识库的详细概览，包括简介、分类、文档数量及示例文档。"
    input_schema = {
        "type": "object",
        "properties": {
            "collection_id": {"type": "string"},
        },
        "required": ["collection_id"],
    }
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        collection_id = kwargs.get("collection_id")
        if not collection_id:
            return ToolResult(content="Error: collection_id is required", is_error=True)

        try:
            col = ctx.deps.collection_repo.get_by_id(collection_id)
            if col is None:
                return ToolResult(
                    content=f"Error: collection {collection_id} not found",
                    is_error=True,
                )

            lines = [f"# Collection: {col.name}", ""]

            readme = (col.readme_content or "")[:2000]
            if readme:
                lines.append(f"## Readme\n{readme}")
                lines.append("")

            categories = []
            if col.categories_json:
                try:
                    parsed = json.loads(col.categories_json)
                    if isinstance(parsed, list):
                        categories = [str(c) for c in parsed]
                except json.JSONDecodeError:
                    pass
            if categories:
                lines.append("## Categories\n- " + "\n- ".join(categories))
                lines.append("")

            doc_count = col.document_count or 0
            vec_count = col.vector_count or 0
            lines.append(f"## Stats\n- documents: {doc_count}\n- vectors: {vec_count}")
            lines.append("")

            try:
                docs = ctx.deps.document_repo.get_by_collection(
                    collection_id, limit=5
                )
            except Exception:
                docs = []

            if docs:
                lines.append("## Sample documents")
                for doc in docs:
                    lines.append(
                        format_doc_summary(
                            doc_id=doc.id or "",
                            title=doc.name or "",
                            category=doc.category,
                            summary=doc.summary,
                            keywords=parse_json_keywords(doc.keywords),
                        )
                    )
            else:
                lines.append("## Sample documents\nNo documents found.")

            return ToolResult(content="\n".join(lines))
        except Exception as exc:
            return ToolResult(content=f"Error: {exc}", is_error=True)
