"""
Prompt templates for RAG question answering with source citation.
Optimized for document assistant use case with clear source attribution.
Enhanced with intent-specific templates for different query types.
"""

from typing import Union

from langchain_core.prompts import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    HumanMessagePromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
)

from models.rag import ChatMessageRoleEnum, CollectionSummary, DocChunk, HistoryItem

# 文档摘要提示词模板
DOC_SUMMARY_PROMPT = PromptTemplate.from_template("""
请基于以下文档内容生成一段 20-30 字的摘要，突出主要主题和关键信息：
{document_content}
""")

# System prompt for RAG question answering
RAG_SYSTEM_PROMPT = SystemMessagePromptTemplate.from_template("""
你是一个专业的AI文档助手，基于知识库内的内容进行回答。

知识库内容为:
{collection_contents}

你的职责是：
1. 基于提供的文档内容准确回答用户问题
2. 在回答中使用角标序号(如[1]、[2])引用具体的来源
3. 如果文档中没有相关信息，明确说明
4. 保持回答简洁、准确、有用

重要规则：
- 只基于提供的文档内容回答问题
- 不要添加文档中没有的信息
- 始终在回答中使用角标序号引用相关的来源，不要包含完整的文档名称
- 如果问题无法从文档中找到答案，请如实说明
""")

RAG_HUMAN_PROMPT = HumanMessagePromptTemplate.from_template("""
当前文档上下文:
{source_contents}

用户问题: {question}
""")


def build_rag_prompt(
    collections: list[CollectionSummary],
    histories: list[HistoryItem],
    reference_chunks: list[DocChunk],
    user_query: str,
) -> str:
    """
    构建完整的 RAG 提示词模板
    """
    collection_contents = []
    for collection in collections:
        collection_contents.append(f"- {collection.name}：{collection.summary}")
    collection_contents = "\n".join(collection_contents) if collection_contents else "无"

    source_contents = []
    for i, chunk in enumerate(reference_chunks, 1):
        source_contents.append(
            f"[{i}] {chunk.doc_name}（来自 {chunk.collection_name}）：{chunk.content}"
        )
    source_contents = "\n".join(source_contents) if source_contents else "无"

    # 构建提示词模板
    messages: list[
        Union[SystemMessagePromptTemplate, HumanMessagePromptTemplate, AIMessagePromptTemplate]
    ] = []
    messages.append(RAG_SYSTEM_PROMPT)
    for his_item in histories:
        if his_item.role == ChatMessageRoleEnum.USER:
            messages.append(HumanMessagePromptTemplate.from_template(his_item.message))
        else:
            messages.append(AIMessagePromptTemplate.from_template(his_item.message))
    messages.append(RAG_HUMAN_PROMPT)
    prompt = ChatPromptTemplate.from_messages(messages)

    # 生成提示词
    return prompt.format(
        collection_contents=collection_contents,
        source_contents=source_contents,
        question=user_query,
    )
