"""
文档摘要生成器模块
基于LLM为文档生成高质量摘要，支持不同文档类型的专门化处理
"""

import logging
import re
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DocumentSummary(BaseModel):
    """文档摘要数据模型"""
    id: str = Field(default_factory=lambda: str(uuid4()))
    summary: str = Field(description="摘要内容")
    source: str = Field(description="文档来源")
    doc_type: str = Field(default="document", description="文档类型")
    original_length: int = Field(description="原文档长度")
    generated_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    error: bool = Field(default=False, description="是否有错误")
    error_message: Optional[str] = Field(default=None, description="错误信息")


class DocumentSummarizer:
    """文档摘要生成器"""

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.summary_prompts = {
            "document": self._get_document_summary_prompt(),
            "technical": self._get_technical_summary_prompt(),
            "tutorial": self._get_tutorial_summary_prompt()
        }

        # 内容提取模式
        self.important_section_patterns = [
            r'(#{1,6}\s+.*?)(?=\n|$)',  # Markdown标题
            r'(\d+\.\s+.*?)(?=\n|$)',   # 数字列表
            r'([-*+]\s+.*?)(?=\n|$)',   # 无序列表
            r'(```.*?```)',             # 代码块
            r'(\*\*.*?\*\*)',           # 粗体文本
            r'(__.*?__)',               # 下划线强调
            r'(第[一二三四五六七八九十\d]+[步章节部分])',  # 中文步骤/章节
            r'(步骤\s*[一二三四五六七八九十\d]+)',  # 步骤标识
        ]

    def _get_document_summary_prompt(self) -> ChatPromptTemplate:
        """通用文档摘要提示词"""
        return ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的文档分析师。请为以下文档生成一个简洁而全面的摘要。

摘要要求：
1. 长度控制在250-800字之间
2. 突出文档的主要内容和关键信息
3. 保持客观和准确
4. 包含重要的技术细节或步骤概述
5. 使用结构化的表述
6. 如果是操作指南，要概述主要步骤
7. 如果是概念介绍，要突出核心概念和定义
8. 使用中文输出

重要：请直接生成摘要，不要包含"摘要："、"总结："等前缀。"""),

            ("human", """文档来源：{source}
文档类型：{doc_type}
文档内容：
{content}

请生成结构化的文档摘要：""")
        ])

    def _get_technical_summary_prompt(self) -> ChatPromptTemplate:
        """技术文档摘要提示词"""
        return ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的技术文档分析师。请为以下技术文档生成摘要。

技术摘要要求：
1. 长度控制在300-1000字之间
2. 突出技术架构、关键组件和实现方式
3. 包含重要的配置参数和技术细节
4. 概述主要功能和特性
5. 提及技术依赖和环境要求
6. 包含关键的代码示例或配置示例（如有）
7. 使用技术专业术语，保持准确性

重要：请直接生成摘要，不要包含前缀。"""),

            ("human", """技术文档来源：{source}
文档类型：{doc_type}
文档内容：
{content}

请生成技术文档摘要：""")
        ])

    def _get_tutorial_summary_prompt(self) -> ChatPromptTemplate:
        """教程文档摘要提示词"""
        return ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的教程文档分析师。请为以下教程文档生成摘要。

教程摘要要求：
1. 长度控制在300-1000字之间
2. 突出教程的学习目标和主要内容
3. 按顺序概述主要的学习步骤或章节
4. 包含前置条件和准备工作
5. 提及关键的实践环节和练习
6. 突出重要的注意事项和常见问题
7. 概述预期的学习成果

重要：请直接生成摘要，不要包含前缀。"""),

            ("human", """教程文档来源：{source}
文档类型：{doc_type}
文档内容：
{content}

请生成教程文档摘要：""")
        ])

    async def _extract_key_sections(self, content: str, max_length: int = 8000) -> str:
        """从长文档中智能提取关键部分"""
        if len(content) <= max_length:
            return content

        logger.info(f"文档过长（{len(content)} 字符），正在进行智能提取...")

        # 1. 首先尝试提取有结构的重要部分
        important_sections = []

        for pattern in self.important_section_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE | re.DOTALL)
            for match in matches:
                section = match.group(1).strip()
                if len(section) > 10:  # 过滤太短的匹配
                    important_sections.append(section)

        # 2. 如果结构化提取足够，使用结构化内容
        if important_sections:
            structured_content = '\n\n'.join(important_sections)
            if len(structured_content) <= max_length:
                logger.info(f"使用结构化提取，长度：{len(structured_content)}")
                return structured_content
            else:
                # 截取结构化内容的前部分
                truncated = structured_content[:max_length]
                logger.info(f"结构化内容截取，长度：{len(truncated)}")
                return truncated

        # 3. 否则使用首尾策略
        head_length = max_length // 3 * 2  # 前2/3
        tail_length = max_length - head_length  # 后1/3

        head = content[:head_length]
        tail = content[-tail_length:]

        extracted = f"{head}\n\n[... 中间部分省略 ...]\n\n{tail}"
        logger.info(f"使用首尾策略提取，长度：{len(extracted)}")
        return extracted

    def _detect_document_type(self, content: str, source: str) -> str:
        """自动检测文档类型"""
        content_lower = content.lower()
        source_lower = source.lower()

        # 基于文件名/路径的判断
        if any(keyword in source_lower for keyword in ['tutorial', 'guide', 'howto', '教程', '指南', '入门']):
            return "tutorial"

        if any(keyword in source_lower for keyword in ['api', 'tech', 'technical', '技术', '开发', 'dev']):
            return "technical"

        # 基于内容的判断
        tutorial_indicators = ['步骤', '第一步', '第二步', '首先', '然后', '最后', 'step 1', 'step 2', 'tutorial', 'guide']
        technical_indicators = ['api', 'function', '函数', '接口', 'class', '类', '配置', 'config', 'import', 'install']

        tutorial_score = sum(1 for indicator in tutorial_indicators if indicator in content_lower)
        technical_score = sum(1 for indicator in technical_indicators if indicator in content_lower)

        if tutorial_score > technical_score and tutorial_score >= 3:
            return "tutorial"
        elif technical_score >= 3:
            return "technical"

        return "document"

    async def generate_document_summary(self,
                                      content: str,
                                      source: str,
                                      doc_type: Optional[str] = None) -> DocumentSummary:
        """生成文档摘要"""
        try:
            original_length = len(content)

            # 自动检测文档类型（如果未指定）
            if not doc_type:
                doc_type = self._detect_document_type(content, source)

            logger.info(f"开始生成摘要 - 来源: {source}, 类型: {doc_type}, 长度: {original_length}")

            # 如果文档过长，先进行智能提取
            processed_content = content
            if len(content) > 12000:  # 约3000 tokens
                processed_content = await self._extract_key_sections(content, 10000)

            # 选择合适的提示词模板
            prompt = self.summary_prompts.get(doc_type, self.summary_prompts["document"])

            # 生成摘要
            chain = prompt | self.llm | StrOutputParser()
            summary_text = await chain.ainvoke({
                "content": processed_content,
                "source": source,
                "doc_type": doc_type
            })

            # 清理摘要文本
            summary_text = summary_text.strip()

            # 验证摘要质量
            if len(summary_text) < 50:
                logger.warning(f"摘要过短（{len(summary_text)} 字符），可能生成质量不佳")
            elif len(summary_text) > 1500:
                logger.warning(f"摘要过长（{len(summary_text)} 字符），进行截取")
                summary_text = summary_text[:1500] + "..."

            logger.info(f"摘要生成成功 - 长度: {len(summary_text)}")

            return DocumentSummary(
                summary=summary_text,
                source=source,
                doc_type=doc_type,
                original_length=original_length
            )

        except Exception as e:
            logger.error(f"摘要生成失败 {source}: {e}")
            return DocumentSummary(
                summary=f"该文档摘要生成失败：{str(e)}",
                source=source,
                doc_type=doc_type or "document",
                original_length=len(content),
                error=True,
                error_message=str(e)
            )

    async def generate_batch_summaries(self,
                                     documents: list[dict[str, Any]],
                                     max_concurrent: int = 3) -> list[DocumentSummary]:
        """批量生成文档摘要"""
        import asyncio

        logger.info(f"开始批量生成摘要，文档数量: {len(documents)}")

        # 创建信号量限制并发数
        semaphore = asyncio.Semaphore(max_concurrent)

        async def generate_single_summary(doc: dict[str, Any]) -> DocumentSummary:
            async with semaphore:
                return await self.generate_document_summary(
                    content=doc.get("content", ""),
                    source=doc.get("source", "unknown"),
                    doc_type=doc.get("doc_type")
                )

        # 并发生成摘要
        tasks = [generate_single_summary(doc) for doc in documents]
        summaries = await asyncio.gather(*tasks, return_exceptions=True)

        # 处理异常结果
        processed_summaries = []
        for i, result in enumerate(summaries):
            if isinstance(result, Exception):
                logger.error(f"文档 {i} 摘要生成异常: {result}")
                processed_summaries.append(DocumentSummary(
                    summary=f"摘要生成异常：{str(result)}",
                    source=documents[i].get("source", "unknown"),
                    doc_type=documents[i].get("doc_type", "document"),
                    original_length=len(documents[i].get("content", "")),
                    error=True,
                    error_message=str(result)
                ))
            else:
                processed_summaries.append(result)

        successful_count = sum(1 for s in processed_summaries if not s.error)
        logger.info(f"批量摘要生成完成 - 成功: {successful_count}/{len(documents)}")

        return processed_summaries
