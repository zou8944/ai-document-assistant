"""
Prompt templates for RAG question answering with source citation.
Optimized for document assistant use case with clear source attribution.
Enhanced with intent-specific templates for different query types.
"""

from langchain_core.prompts import ChatPromptTemplate, PromptTemplate

from rag.intent_analyzer import QueryIntent

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


# ============ 意图特定的提示词模板 ============

# 概述类查询的专用提示词
OVERVIEW_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的文档分析师，擅长从多个文档片段中提取和综合信息。

你的任务是基于提供的文档片段，生成一个全面的概述性回答。

重要规则：
1. 从提供的所有文档片段中提取关键信息
2. 按逻辑顺序组织信息，形成结构化的概述
3. 突出主要主题、关键概念和重要细节
4. 使用清晰的段落结构和层次化表达
5. 确保概述的完整性和连贯性
6. 在适当位置引用文档来源
7. 如果内容涉及多个方面，使用**小标题**进行分组
8. 长度控制在800-1200字，确保全面而精炼"""),

    ("human", """基于以下文档片段，请提供一个全面的概述：

{context}

用户问题：{question}

请提供结构化的概述，包括：
1. 主要内容总结
2. 关键主题和概念
3. 重要细节和特点
4. 整体结构或逻辑关系

请确保回答全面、有条理，并在适当位置标注信息来源。""")
])

# 操作指南类查询的专用提示词
HOW_TO_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的技术文档编写专家，擅长将分散的信息整合成清晰的操作指南。

你的任务是基于文档片段中的信息，提供详细、准确的操作指导。

重要规则：
1. 按照逻辑顺序组织操作步骤
2. 确保步骤的完整性和连贯性
3. 提供必要的背景信息和前提条件
4. 包含重要的注意事项和警告
5. 使用清晰的步骤编号和格式
6. 在每个步骤中引用相关文档来源
7. 如果步骤复杂，可以使用子步骤分解
8. 提供预期结果和验证方法"""),

    ("human", """基于以下文档片段，请提供详细的操作指南：

{context}

用户问题：{question}

请按以下格式提供操作指南：

## 前提条件
[列出必要的前提条件]

## 操作步骤
1. [第一步详细说明]
2. [第二步详细说明]
...

## 注意事项
[重要提醒和警告]

## 预期结果
[操作完成后的预期状态]

请确保步骤清晰、完整，并标注信息来源。""")
])

# 比较类查询的专用提示词
COMPARISON_PROMPT_TEMPLATE = ChatPromptTemplate.from_messages([
    ("system", """你是一个专业的分析师，擅长进行客观、全面的比较分析。

你的任务是基于文档内容，提供平衡、准确的比较分析。

重要规则：
1. 客观呈现各方面的特点和差异
2. 使用结构化的比较格式
3. 突出关键差异点和相似处
4. 提供具体的例子和证据
5. 保持中立和平衡的观点
6. 在比较中引用相关文档来源
7. 使用表格或列表形式组织比较内容
8. 提供基于比较结果的建议（如适用）"""),

    ("human", """基于以下文档片段，请进行详细的比较分析：

{context}

用户问题：{question}

请按以下格式提供比较分析：

## 相似点
[列出主要相似特征]

## 主要差异
| 比较维度 | 选项A | 选项B |
|---------|-------|-------|
| 特征1    | ...   | ...   |
| 特征2    | ...   | ...   |

## 优缺点分析
**选项A：**
- 优点：...
- 缺点：...

**选项B：**
- 优点：...
- 缺点：...

## 适用场景
[分别说明不同选择的适用情况]

## 总结建议
[基于比较结果的建议]

请确保比较客观、全面，并标注信息来源。""")
])


def get_prompt_by_intent(intent: QueryIntent) -> ChatPromptTemplate:
    """根据意图返回相应的提示词模板"""
    prompt_map = {
        QueryIntent.OVERVIEW: OVERVIEW_PROMPT_TEMPLATE,
        QueryIntent.HOW_TO: HOW_TO_PROMPT_TEMPLATE,
        QueryIntent.COMPARISON: COMPARISON_PROMPT_TEMPLATE,
        QueryIntent.FACTUAL: RAG_PROMPT_TEMPLATE  # 保持现有的事实查询模板
    }
    return prompt_map.get(intent, RAG_PROMPT_TEMPLATE)
