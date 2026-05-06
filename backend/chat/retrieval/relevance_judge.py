import json
import logging
from collections import defaultdict

from chat.generation.base import BaseLLMService
from chat.models import QueryIntent, RetrievedDocument
from database.connection import session_context
from database.models.document import Document

logger = logging.getLogger(__name__)

RELEVANCE_JUDGE_PROMPT = """你是一位文档相关性判断专家。请根据用户问题，判断每篇文档是否与问题相关。

用户问题：{query}

意图类型：{intent}

核心关键词：{keywords}

待判断文档：
{documents}

请对每篇文档进行评估，输出 JSON 数组格式：
[
  {
    "document_id": "文档ID",
    "relevance_score": 0.92,
    "is_relevant": true,
    "reason": "简要说明判断理由"
  }
]

判断标准：
1. 文档的主题或内容是否直接涉及用户问题的核心
2. 文档的摘要和关键词是否表明它能帮助回答该问题
3. 不要仅因为文档标题包含某个词就判定相关，要看整体内容方向
4. relevance_score 范围 0-1，is_relevant 为 true 表示该文档确实相关（建议 relevance_score >= 0.6）
"""


class RelevanceJudge:
    def __init__(self, llm: BaseLLMService):
        self.llm = llm

    async def filter_documents(
        self,
        query: str,
        documents: list[RetrievedDocument],
        intent: QueryIntent,
        core_keywords: list[str] | None = None,
        min_score: float = 0.6
    ) -> list[RetrievedDocument]:
        """
        按 document_id 对 chunk 聚类，用 LLM 判断每篇文档的 summary 是否相关。
        返回过滤后的 chunk 列表（保留通过过滤的文档的所有 chunk）。
        """
        if not documents:
            return []

        # 1. 按 document_id 分组
        doc_groups: dict[str, list[RetrievedDocument]] = defaultdict(list)
        for doc in documents:
            doc_groups[doc.document_id].append(doc)

        # 2. 从 Postgres 获取每篇文档的 name、summary、keywords
        doc_ids = list(doc_groups.keys())
        doc_infos = self._fetch_document_infos(doc_ids)

        # 如果没有获取到任何文档信息，直接返回原始结果
        if not doc_infos:
            return documents

        # 3. 构建 prompt
        docs_text = ""
        for doc_id in doc_ids:
            info = doc_infos.get(doc_id)
            if info:
                name = info.get("name", "")
                summary = info.get("summary", "") or ""
                keywords = info.get("keywords", "") or ""
                docs_text += f"\n---\n文档ID: {doc_id}\n标题: {name}\n摘要: {summary}\n关键词: {keywords}\n"
            else:
                docs_text += f"\n---\n文档ID: {doc_id}\n标题: (未知)\n摘要: (无)\n关键词: (无)\n"

        prompt = RELEVANCE_JUDGE_PROMPT.format(
            query=query,
            intent=intent.value,
            keywords=", ".join(core_keywords) if core_keywords else "无",
            documents=docs_text
        )

        # 4. 调用 LLM
        try:
            response = await self.llm.generate(
                system_prompt="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=2048
            )
            result = json.loads(response)
        except Exception as e:
            logger.warning(f"RelevanceJudge LLM call failed: {e}, returning all documents")
            return documents

        # 5. 解析结果，构建 document_id -> relevance_score 映射
        relevance_map: dict[str, float] = {}
        for item in result:
            if not isinstance(item, dict):
                continue
            doc_id = item.get("document_id", "")
            is_relevant = item.get("is_relevant", False)
            score = item.get("relevance_score", 0.0)
            if doc_id and is_relevant and score >= min_score:
                relevance_map[doc_id] = score

        # 6. 过滤并更新 relevance_score
        filtered = []
        for doc_id, score in relevance_map.items():
            chunks = doc_groups.get(doc_id, [])
            for chunk in chunks:
                filtered.append(
                    RetrievedDocument(
                        document_id=chunk.document_id,
                        document_name=chunk.document_name,
                        document_uri=chunk.document_uri,
                        content=chunk.content,
                        relevance_score=score,
                        source_type=chunk.source_type,
                        chunk_index=chunk.chunk_index
                    )
                )

        logger.info(
            "RelevanceJudge: %d documents passed filter out of %d, total chunks %d -> %d",
            len(relevance_map), len(doc_groups), len(documents), len(filtered)
        )
        return filtered

    async def _fetch_document_infos(self, doc_ids: list[str]) -> dict[str, dict]:
        """从 documents 表获取文档元数据。"""
        import asyncio

        if not doc_ids:
            return {}

        def _query():
            with session_context() as session:
                from sqlalchemy import select
                stmt = select(Document.id, Document.name, Document.summary, Document.keywords).where(
                    Document.id.in_(doc_ids)
                )
                result = session.execute(stmt)
                infos = {}
                for row in result:
                    infos[row[0]] = {
                        "name": row[1] or "",
                        "summary": row[2] or "",
                        "keywords": row[3] or ""
                    }
                return infos

        return await asyncio.to_thread(_query)
