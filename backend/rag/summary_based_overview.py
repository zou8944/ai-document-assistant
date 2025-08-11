"""
基于摘要的概述生成器
专门处理概述类查询，通过预生成的文档摘要提供高质量的概述回答
"""

import logging
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel

from .summary_manager import SummaryManager, SummaryPoint

logger = logging.getLogger(__name__)


class OverviewResponse(BaseModel):
    """概述回答模型"""
    answer: str
    sources: list[dict[str, Any]]
    confidence: float
    query: str
    method: str = "summary_based"  # 标识使用摘要方法
    summary_count: int = 0  # 使用的摘要数量


class SummaryBasedOverviewGenerator:
    """基于摘要的概述生成器"""

    def __init__(self, summary_manager: SummaryManager, llm: ChatOpenAI):
        """
        初始化概述生成器
        
        Args:
            summary_manager: 摘要管理器实例
            llm: 用于生成概述的语言模型
        """
        self.summary_manager = summary_manager
        self.llm = llm
        self.overview_prompt = self._create_overview_aggregation_prompt()

    def _create_overview_aggregation_prompt(self) -> ChatPromptTemplate:
        """创建概述聚合的提示词模板"""
        return ChatPromptTemplate.from_messages([
            ("system", """你是一个专业的信息整合专家。基于提供的多个文档摘要，生成一个全面、结构化的概述回答。

整合要求：
1. 综合分析所有相关摘要的信息，提取核心内容
2. 按逻辑结构组织内容，形成清晰的层次
3. 突出主要主题、关键概念和重要特点
4. 保持信息的准确性，不要添加摘要中没有的内容
5. 使用结构化的表述方式（可使用标题、列表等）
6. 如果涉及操作流程，要概括主要步骤
7. 长度控制在800-1500字之间，确保全面而精炼
8. 在适当位置提及信息来源（使用文档名称）

格式要求：
- 使用清晰的段落结构
- 重要信息可以使用**加粗**标注
- 如有多个主题，使用二级标题分组
- 保持客观中性的表述风格"""),

            ("human", """请基于以下文档摘要回答用户问题：

== 相关文档摘要 ==
{summary_context}

== 用户问题 ==
{question}

请提供结构化的综合概述：""")
        ])

    async def generate_overview(self,
                              question: str,
                              collection_name: str,
                              max_summaries: int = 20,
                              score_threshold: float = 0.15) -> OverviewResponse:
        """
        基于预生成摘要创建概述
        
        Args:
            question: 用户查询问题
            collection_name: 文档集合名称
            max_summaries: 最大摘要数量
            score_threshold: 相似度阈值
            
        Returns:
            概述回答对象
        """
        try:
            logger.info(f"开始生成基于摘要的概述 - 集合: {collection_name}, 查询: {question[:50]}...")

            # 1. 检索相关文档摘要
            relevant_summaries = await self.summary_manager.retrieve_relevant_summaries(
                collection_name=collection_name,
                query=question,
                limit=max_summaries,
                score_threshold=score_threshold
            )

            if not relevant_summaries:
                logger.warning(f"未找到相关摘要 - 集合: {collection_name}")
                return OverviewResponse(
                    answer="抱歉，没有找到与您的问题相关的文档摘要。请确认文档已正确处理，或尝试使用不同的关键词。",
                    sources=[],
                    confidence=0.0,
                    query=question,
                    summary_count=0
                )

            logger.info(f"检索到 {len(relevant_summaries)} 个相关摘要")

            # 2. 按文档类型和相关性排序摘要
            sorted_summaries = self._sort_summaries_by_relevance(relevant_summaries)

            # 3. 选择最相关的摘要（控制总长度）
            selected_summaries = self._select_summaries_by_length(sorted_summaries, max_length=8000)

            logger.info(f"选择了 {len(selected_summaries)} 个摘要用于生成概述")

            # 4. 构建摘要上下文
            summary_context = self._format_summary_context(selected_summaries)

            # 5. 生成聚合概述
            chain = self.overview_prompt | self.llm | StrOutputParser()
            answer = await chain.ainvoke({
                "summary_context": summary_context,
                "question": question
            })

            # 6. 计算置信度（基于摘要质量和数量）
            confidence = self._calculate_confidence(selected_summaries, question)

            # 7. 格式化来源信息
            sources = self._format_summary_sources(selected_summaries)

            logger.info(f"概述生成完成 - 置信度: {confidence:.2f}, 来源数: {len(sources)}")

            return OverviewResponse(
                answer=answer.strip(),
                sources=sources,
                confidence=confidence,
                query=question,
                summary_count=len(selected_summaries)
            )

        except Exception as e:
            logger.error(f"基于摘要的概述生成失败: {e}")
            return OverviewResponse(
                answer=f"概述生成过程中遇到错误：{str(e)}。请稍后重试。",
                sources=[],
                confidence=0.0,
                query=question,
                summary_count=0
            )

    def _sort_summaries_by_relevance(self, summaries: list[SummaryPoint]) -> list[SummaryPoint]:
        """
        按相关性和文档类型排序摘要
        
        Args:
            summaries: 原始摘要列表
            
        Returns:
            排序后的摘要列表
        """
        # 按相关性分数排序，同时考虑文档类型权重
        def sort_key(summary: SummaryPoint) -> tuple:
            score = summary.score or 0.0

            # 文档类型权重调整
            type_weight = {
                "document": 1.0,
                "technical": 1.1,  # 技术文档权重稍高
                "tutorial": 1.05   # 教程文档权重稍高
            }.get(summary.doc_type, 1.0)

            # 长度权重（更长的摘要通常信息更丰富）
            length_weight = min(1.2, 1.0 + len(summary.summary) / 5000)

            adjusted_score = score * type_weight * length_weight
            return (-adjusted_score,)  # 负号用于降序排列

        return sorted(summaries, key=sort_key)

    def _select_summaries_by_length(self,
                                  summaries: list[SummaryPoint],
                                  max_length: int = 8000) -> list[SummaryPoint]:
        """
        根据长度限制选择摘要
        
        Args:
            summaries: 排序后的摘要列表
            max_length: 最大总长度
            
        Returns:
            选择的摘要列表
        """
        selected = []
        current_length = 0

        for summary in summaries:
            summary_length = len(summary.summary)

            # 检查是否超过长度限制
            if current_length + summary_length > max_length:
                # 如果当前还没有选择任何摘要，至少选择一个
                if not selected:
                    selected.append(summary)
                break

            selected.append(summary)
            current_length += summary_length

        return selected

    def _format_summary_context(self, summaries: list[SummaryPoint]) -> str:
        """
        格式化摘要为上下文文本
        
        Args:
            summaries: 摘要列表
            
        Returns:
            格式化的上下文文本
        """
        if not summaries:
            return "未找到相关文档摘要。"

        context_parts = []

        for i, summary in enumerate(summaries, 1):
            # 格式化单个摘要
            formatted_summary = f"""【文档摘要 {i}】
来源: {summary.source}
文档类型: {summary.doc_type}
相似度分数: {summary.score:.3f}

{summary.summary}
"""
            context_parts.append(formatted_summary)

        return "\n" + "="*60 + "\n".join(context_parts) + "\n" + "="*60

    def _calculate_confidence(self, summaries: list[SummaryPoint], question: str) -> float:
        """
        计算概述回答的置信度
        
        Args:
            summaries: 使用的摘要列表
            question: 用户问题
            
        Returns:
            置信度分数 (0-1)
        """
        if not summaries:
            return 0.0

        # 基础置信度：基于平均相关性分数
        avg_score = sum(s.score or 0 for s in summaries) / len(summaries)
        base_confidence = min(avg_score * 2, 0.9)  # 限制最高0.9

        # 数量奖励：摘要数量越多，概述越全面
        quantity_bonus = min(len(summaries) / 10, 0.2)  # 最多加0.2

        # 多样性奖励：不同来源的摘要增加置信度
        unique_sources = len(set(s.source for s in summaries))
        diversity_bonus = min(unique_sources / 15, 0.15)  # 最多加0.15

        # 最终置信度
        final_confidence = min(base_confidence + quantity_bonus + diversity_bonus, 0.98)

        logger.debug(f"置信度计算: 基础={base_confidence:.3f}, 数量奖励={quantity_bonus:.3f}, "
                    f"多样性奖励={diversity_bonus:.3f}, 最终={final_confidence:.3f}")

        return final_confidence

    def _format_summary_sources(self, summaries: list[SummaryPoint]) -> list[dict[str, Any]]:
        """
        格式化摘要来源信息
        
        Args:
            summaries: 摘要列表
            
        Returns:
            来源信息列表
        """
        sources = []

        for i, summary in enumerate(summaries, 1):
            source_info = {
                "id": f"summary_{i}",
                "source": summary.source,
                "type": "document_summary",
                "doc_type": summary.doc_type,
                "score": summary.score,
                "content_preview": summary.summary[:200] + "..." if len(summary.summary) > 200 else summary.summary,
                "generated_at": summary.generated_at
            }
            sources.append(source_info)

        return sources

    async def get_collection_overview_stats(self, collection_name: str) -> Optional[dict[str, Any]]:
        """
        获取集合的概述统计信息
        
        Args:
            collection_name: 集合名称
            
        Returns:
            统计信息字典
        """
        try:
            stats = await self.summary_manager.get_collection_summary_stats(collection_name)
            if stats:
                return {
                    "collection_name": collection_name,
                    "summary_collection": stats["collection_name"],
                    "total_summaries": stats["summary_count"],
                    "status": stats["status"],
                    "overview_ready": stats["summary_count"] > 0
                }
            return None

        except Exception as e:
            logger.error(f"获取概述统计失败: {e}")
            return None


# 便捷函数
def create_summary_based_overview_generator(summary_manager: SummaryManager,
                                          llm: ChatOpenAI) -> SummaryBasedOverviewGenerator:
    """创建基于摘要的概述生成器实例"""
    return SummaryBasedOverviewGenerator(summary_manager, llm)
