import logging

from chat.context.expander import ContextExpander
from chat.models import AssembledContext, CollectionInfo, ProcessingMode, QueryIntent, SearchResult
from models.rag import ChatMessageRoleEnum

logger = logging.getLogger(__name__)

MODE_BUDGETS = {
    ProcessingMode.FAST: 16000,
    ProcessingMode.STANDARD: 128000,
    ProcessingMode.DEEP: 1000000,
}

RESERVED_TOKENS = {
    ProcessingMode.FAST: 2000,
    ProcessingMode.STANDARD: 4000,
    ProcessingMode.DEEP: 8000,
}


class ContextAssembler:
    def __init__(self, tokenizer=None, expander: ContextExpander | None = None):
        self.tokenizer = tokenizer
        self.expander = expander

    def _count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return self.tokenizer(text)
        return len(text) // 4

    async def assemble(self, mode: ProcessingMode, query: str, search_result: SearchResult,
                       collection_info: list = None,
                       chat_history: list[dict] = None,
                       system_prompt_template: str = None) -> AssembledContext:
        budget = MODE_BUDGETS[mode]
        reserved = RESERVED_TOKENS[mode]
        available = budget - reserved

        # Clamp available to non-negative
        if available < 0:
            available = 0

        system_prompt = system_prompt_template or self._default_system_prompt()
        system_tokens = self._count_tokens(system_prompt)
        available -= system_tokens

        if available < 0:
            logger.warning(
                "System prompt (%d tokens) exceeds available budget (%d tokens). "
                "Truncating system prompt.",
                system_tokens, budget - reserved
            )
            available = 0

        collection_context = ""
        if collection_info:
            max_collection_tokens = {
                ProcessingMode.FAST: 500,
                ProcessingMode.STANDARD: 2000,
                ProcessingMode.DEEP: 5000,
            }[mode]
            for col in collection_info:
                col_text = self._format_collection_info(col, mode)
                col_tokens = self._count_tokens(col_text)
                if available - col_tokens >= 0 and self._count_tokens(collection_context + col_text) <= max_collection_tokens:
                    collection_context += col_text
                    available -= col_tokens
                else:
                    # Budget tight: add minimal summary and continue to next collection
                    summary = f"\n知识库: {col.name}\n"
                    if col.categories:
                        summary += "分组: " + ", ".join(
                            c.get("name", "") for c in col.categories[:5]
                        ) + "\n"
                    summary_tokens = self._count_tokens(summary)
                    if available - summary_tokens >= 0:
                        available -= summary_tokens
                        collection_context += summary
                    # Continue to next collection instead of breaking

        messages = []
        if chat_history:
            for item in reversed(chat_history):
                if hasattr(item, "role"):
                    role = item.role.value if hasattr(item.role, "value") else str(item.role)
                    content = item.message if hasattr(item, "message") else item.content
                else:
                    role = item.get("role", "")
                    content = item.get("content", "") or item.get("message", "")

                role_str = "user" if role in ("user", "USER", ChatMessageRoleEnum.USER) else "assistant"
                msg_text = f"{role_str}: {content}"
                msg_tokens = self._count_tokens(msg_text)
                if available - msg_tokens >= 0:
                    messages.insert(0, {"role": role_str, "content": content})
                    available -= msg_tokens
                else:
                    break

        # Expand documents to full markdown if possible
        if self.expander and search_result.documents:
            expanded = await self.expander.expand(
                documents=search_result.documents,
                token_budget=available
            )
            search_result = SearchResult(
                documents=expanded,
                search_type=search_result.search_type,
                total_found=search_result.total_found
            )
            # Recalculate available budget after expansion
            expanded_tokens = sum(len(d.content) // 4 for d in expanded)
            available = max(0, available - expanded_tokens)

        # Group chunks by document for structured formatting
        doc_groups: dict[str, list] = {}
        for doc in search_result.documents:
            if doc.document_id not in doc_groups:
                doc_groups[doc.document_id] = []
            doc_groups[doc.document_id].append(doc)

        context_docs = []
        context_text = ""
        for i, (_, docs) in enumerate(doc_groups.items(), 1):
            doc = docs[0]
            combined_content = "\n".join(d.content for d in docs)
            doc_text = f"\n[来源 {i}] 文档名: {doc.document_name}（相关度: {doc.relevance_score:.2f}）\n{combined_content}\n\n---\n"
            doc_tokens = self._count_tokens(doc_text)
            if available - doc_tokens >= 0:
                context_text += doc_text
                context_docs.extend(docs)
                available -= doc_tokens
            else:
                # Try to fit a truncated version
                max_chars = max(0, available * 4 - 50)
                if max_chars > 0:
                    truncated = combined_content[:max_chars] + "..."
                    truncated_text = f"\n[来源 {i}] 文档名: {doc.document_name}（相关度: {doc.relevance_score:.2f}）\n{truncated}\n\n---\n"
                    truncated_tokens = self._count_tokens(truncated_text)
                    if truncated_tokens <= available:
                        context_text += truncated_text
                        context_docs.extend(docs)
                        available = max(0, available - truncated_tokens)
                        continue
                # Cannot fit even truncated version
                break

        user_content_parts = []
        if collection_context:
            user_content_parts.append(f"以下是你正在协助用户查阅的知识库概览：\n{collection_context}")
        if context_text:
            user_content_parts.append(f"以下是相关的文档片段：\n{context_text}")
        user_content_parts.append(f"用户问题：{query}")

        final_messages = messages.copy()
        final_messages.append({
            "role": "user",
            "content": "\n\n".join(user_content_parts)
        })

        total_tokens = min(budget, budget - available)

        return AssembledContext(
            system_prompt=system_prompt,
            messages=final_messages,
            context_documents=context_docs,
            collection_info=collection_info or [],
            estimated_tokens=total_tokens,
            mode=mode
        )

    def _format_collection_info(self, col, mode: ProcessingMode = ProcessingMode.STANDARD) -> str:
        readme_limits = {
            ProcessingMode.FAST: 200,
            ProcessingMode.STANDARD: 1000,
            ProcessingMode.DEEP: 2000,
        }
        limit = readme_limits[mode]

        parts = [f"\n=== 知识库: {col.name} ==="]
        if col.description:
            parts.append(f"描述: {col.description}")
        if col.readme_content:
            readme = col.readme_content[:limit]
            if len(col.readme_content) > limit:
                readme += "..."
            parts.append(f"README:\n{readme}")
        if col.categories:
            parts.append("文档分组:")
            for cat in col.categories:
                cat_name = cat.get("name", "未命名")
                docs = cat.get("documents", [])
                parts.append(f"  - {cat_name}: {len(docs)} 篇文档")
        parts.append(f"总计: {col.document_count} 篇文档")
        return "\n".join(parts)

    def _default_system_prompt(self) -> str:
        return """你是一个专业的 AI 文档助手。基于文档内容回答用户问题。

规则：
1. 只基于文档内容回答，不要编造信息
2. 若文档未涉及该内容，直接说明文档中未涉及即可
3. 使用 [来源: 文档名] 格式标注引用来源
4. 回答简洁准确，不要过度发挥
5. 优先参考相关度更高的来源，相关度分数在来源标题中已标注
6. 如果文档片段不足以回答问题，诚实说明文档未覆盖该内容，不要推测
7. 涉及多个方面时，确保每个论断都有对应的文档来源支撑
"""

    def assemble_lite(self, intent: QueryIntent, query: str,
                      collection_info: list | None = None,
                      chat_history: list[dict] | None = None) -> AssembledContext:
        """Assemble context for chitchat/meta/off-topic queries: no document search."""
        budget = MODE_BUDGETS[ProcessingMode.FAST]
        reserved = RESERVED_TOKENS[ProcessingMode.FAST]
        available = budget - reserved
        if available < 0:
            available = 0

        system_prompt = self._lite_system_prompt(intent)
        available -= self._count_tokens(system_prompt)

        collection_context = ""
        if collection_info:
            for col in collection_info:
                brief = self._format_collection_info_brief(col)
                tokens = self._count_tokens(brief)
                if available - tokens >= 0:
                    collection_context += brief
                    available -= tokens

        messages: list[dict[str, str]] = []
        if chat_history:
            for item in reversed(chat_history):
                if hasattr(item, "role"):
                    role = item.role.value if hasattr(item.role, "value") else str(item.role)
                    content = item.message if hasattr(item, "message") else item.content
                else:
                    role = item.get("role", "")
                    content = item.get("content", "") or item.get("message", "")

                role_str = "user" if role in ("user", "USER", ChatMessageRoleEnum.USER) else "assistant"
                msg_text = f"{role_str}: {content}"
                msg_tokens = self._count_tokens(msg_text)
                if available - msg_tokens >= 0:
                    messages.insert(0, {"role": role_str, "content": content})
                    available -= msg_tokens
                else:
                    break

        user_parts = []
        if collection_context:
            user_parts.append(f"你当前正在协助用户查阅的知识库概况:\n{collection_context}")
        user_parts.append(f"用户消息:{query}")

        final_messages = messages.copy()
        final_messages.append({
            "role": "user",
            "content": "\n\n".join(user_parts)
        })

        total_tokens = min(budget, budget - available)

        return AssembledContext(
            system_prompt=system_prompt,
            messages=final_messages,
            context_documents=[],
            collection_info=collection_info or [],
            estimated_tokens=total_tokens,
            mode=ProcessingMode.FAST
        )

    def _lite_system_prompt(self, intent: QueryIntent) -> str:
        if intent and getattr(intent, "value", None) == "meta":
            return """你是一个友好的 AI 文档助手。当用户询问你的能力或当前知识库概况时:
- 友好简洁地回应,介绍自己是知识库问答助手
- 如果提供了知识库概况,顺带用一两句话介绍当前知识库的主题与范围
- 欢迎用户针对文档内容提问
- 不要捏造文档内容
"""
        return """你是一个友好的 AI 文档助手。当用户进行问候、寒暄或闲聊时:
- 友好、简洁地回应,语气自然
- 如果提供了知识库概况,顺带用一两句话介绍当前知识库的主题与范围,并欢迎用户提问
- 不要捏造文档内容
- 不要说"在文档中未找到相关信息"——用户此刻并未在提问知识点
"""

    def _format_collection_info_brief(self, col: CollectionInfo) -> str:
        parts = [f"\n- 知识库: {col.name}"]
        if col.description:
            parts.append(f"  描述: {col.description}")
        if col.readme_content:
            readme = col.readme_content[:200]
            if len(col.readme_content) > 200:
                readme += "..."
            parts.append(f"  README: {readme}")
        if col.categories:
            cats = ", ".join(c.get("name", "未命名") for c in col.categories[:5])
            parts.append(f"  分组: {cats}")
        parts.append(f"  共 {col.document_count} 篇文档")
        return "\n".join(parts)
