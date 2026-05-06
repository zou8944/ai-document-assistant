import asyncio
import logging
from collections import defaultdict

from chat.models import RetrievedDocument
from repository.document import DocumentRepository

logger = logging.getLogger(__name__)


class ContextExpander:
    def __init__(self, document_repo: DocumentRepository):
        self.document_repo = document_repo

    async def expand(
        self,
        documents: list[RetrievedDocument],
        token_budget: int
    ) -> list[RetrievedDocument]:
        """
        对过滤后的文档，将 chunk 片段替换为完整 Markdown。
        按 relevance_score 降序处理，超出 token_budget 时停止。
        """
        if not documents:
            return []

        # 按 document_id 分组
        doc_groups: dict[str, list[RetrievedDocument]] = defaultdict(list)
        for doc in documents:
            doc_groups[doc.document_id].append(doc)

        # 按文档最高 relevance_score 降序排列
        sorted_doc_ids = sorted(
            doc_groups.keys(),
            key=lambda did: max(d.relevance_score for d in doc_groups[did]),
            reverse=True
        )

        remaining_budget = token_budget
        expanded: list[RetrievedDocument] = []

        for doc_id in sorted_doc_ids:
            chunks = doc_groups[doc_id]
            max_score = max(d.relevance_score for d in chunks)

            doc_dto = await asyncio.to_thread(self.document_repo.get_by_id, doc_id)
            if not doc_dto or not doc_dto.content:
                expanded.extend(chunks)
                continue

            full_content = doc_dto.content
            estimated_tokens = len(full_content) // 4

            if estimated_tokens <= remaining_budget:
                expanded.append(
                    RetrievedDocument(
                        document_id=doc_id,
                        document_name=chunks[0].document_name,
                        document_uri=chunks[0].document_uri,
                        content=full_content,
                        relevance_score=max_score,
                        source_type="full_document",
                        chunk_index=None
                    )
                )
                remaining_budget -= estimated_tokens
            else:
                chunk_tokens = sum(len(d.content) // 4 for d in chunks)
                expanded.extend(chunks)
                remaining_budget -= chunk_tokens

        logger.info(
            "ContextExpander: expanded %d documents, budget=%d, remaining=%d",
            len(expanded), token_budget, remaining_budget
        )
        return expanded
