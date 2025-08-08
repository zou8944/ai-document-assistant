"""
Prompt templates for RAG question answering with source citation.
Optimized for document assistant use case with clear source attribution.
"""

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

# System prompt for RAG question answering
RAG_SYSTEM_PROMPT = """你是一个专业的AI文档助手，专门帮助用户从提供的文档中查找和总结信息。

你的职责是：
1. 基于提供的文档内容准确回答用户问题
2. 在回答中明确引用具体的来源
3. 如果文档中没有相关信息，明确说明
4. 保持回答简洁、准确、有用

重要规则：
- 只基于提供的文档内容回答问题
- 不要添加文档中没有的信息
- 始终在回答中引用相关的来源
- 如果问题无法从文档中找到答案，请如实说明"""

# Main RAG prompt template
RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", RAG_SYSTEM_PROMPT),
    ("human", """基于以下文档内容回答问题：

相关文档片段：
{context}

问题：{question}

请提供详细的回答，并在回答中明确标注信息来源。如果无法从提供的文档中找到答案，请明确说明。""")
])

# Contextual compression prompt (for filtering relevant chunks)
COMPRESSION_PROMPT = PromptTemplate.from_template("""
给定以下问题和文档片段，请判断该文档片段是否包含与问题相关的信息。

问题：{question}

文档片段：
{context}

如果相关，返回"相关"，如果不相关，返回"不相关"。
""")

# Source citation template
SOURCE_CITATION_TEMPLATE = """

**信息来源：**
{sources}
"""

# Follow-up question prompt
FOLLOWUP_PROMPT_TEMPLATE = PromptTemplate.from_template("""
基于以下对话历史和最新问题，生成一个优化的搜索查询来查找相关文档：

对话历史：
{chat_history}

最新问题：{question}

优化的搜索查询：
""")

def get_rag_prompt() -> ChatPromptTemplate:
    """Get the main RAG prompt template"""
    return RAG_PROMPT_TEMPLATE

def get_compression_prompt() -> PromptTemplate:
    """Get the contextual compression prompt"""
    return COMPRESSION_PROMPT

def get_followup_prompt() -> PromptTemplate:
    """Get the follow-up question prompt"""
    return FOLLOWUP_PROMPT_TEMPLATE

def format_sources(sources: list) -> str:
    """Format source citations for display"""
    if not sources:
        return ""

    formatted_sources = []
    for i, source in enumerate(sources, 1):
        source_info = f"{i}. **{source.get('source', 'Unknown')}**"
        if source.get('start_index'):
            source_info += f" (位置: {source['start_index']})"
        if source.get('score'):
            source_info += f" (相关度: {source['score']:.2f})"
        formatted_sources.append(source_info)

    return SOURCE_CITATION_TEMPLATE.format(sources="\n".join(formatted_sources))
