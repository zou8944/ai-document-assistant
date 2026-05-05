import logging
from dataclasses import replace

from chat.models import AssembledContext, ProcessingMode, SearchResult
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
    def __init__(self, tokenizer=None):
        self.tokenizer = tokenizer

    def _count_tokens(self, text: str) -> int:
        if self.tokenizer:
            return self.tokenizer(text)
        return len(text) // 4

    def assemble(self, mode: ProcessingMode, query: str, search_result: SearchResult,
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

        context_docs = []
        context_text = ""
        for doc in search_result.documents:
            doc_text = f"\n[来源: {doc.document_name}]\n{doc.content}\n"
            doc_tokens = self._count_tokens(doc_text)
            if available - doc_tokens >= 0:
                context_text += doc_text
                context_docs.append(doc)
                available -= doc_tokens
            else:
                # Try to fit a truncated version
                max_chars = max(0, available * 4 - 20)
                if max_chars > 0:
                    truncated = doc.content[:max_chars] + "..."
                    truncated_text = f"\n[来源: {doc.document_name}]\n{truncated}\n"
                    truncated_tokens = self._count_tokens(truncated_text)
                    if truncated_tokens <= available:
                        context_text += truncated_text
                        context_docs.append(replace(doc, content=truncated))
                        available = max(0, available - truncated_tokens)
                        continue
                # Cannot fit even truncated version
                break

        user_content_parts = []
        if collection_context:
            user_content_parts.append(f"以下是你正在协助用户查阅的知识库概览：\n{collection_context}")
        if context_text:
            user_content_parts.append(f"以下是与问题相关的文档内容：\n{context_text}")
        user_content_parts.append(f"请基于以上内容回答问题：{query}")
        user_content_parts.append('如果文档中没有相关信息，请明确说明"在现有文档中未找到相关信息"。')

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
        return """你是一个专业的文档助手。你的任务是基于提供的文档内容回答用户问题。

规则：
1. 只基于提供的文档内容回答，不要编造信息
2. 如果文档中没有相关信息，明确说"在现有文档中未找到相关信息"
3. 使用 [来源: 文档名] 格式标注引用来源
4. 回答简洁准确，不要过度发挥
"""
