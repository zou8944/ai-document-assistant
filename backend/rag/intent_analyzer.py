"""
用户查询意图分析模块
基于关键词匹配和语义分析识别查询类型
"""

import logging
import re
from enum import Enum
from typing import Optional

from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """查询意图枚举"""
    OVERVIEW = "overview"      # 概述类：总结、概览、整体介绍
    HOW_TO = "how_to"         # 操作指南类：如何做、步骤、教程
    FACTUAL = "factual"       # 事实查询类：具体问题、定义、细节
    COMPARISON = "comparison"  # 比较类：对比、区别、优缺点


class IntentAnalyzer:
    """用户查询意图分析器"""

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        初始化意图分析器

        Args:
            llm: 可选的LLM实例，用于语义分析
        """
        self.llm = llm

        # 关键词模式匹配（中英文混合）
        self.keyword_patterns = {
            QueryIntent.OVERVIEW: [
                r'总体|整体|概述|概览|总结|主要内容|讲了什么|介绍了什么|都有什么|包含什么|涵盖了',
                r'全面|综合|整个|所有|全部内容|主要讲|主题是什么|核心内容',
                r'overall|summary|overview|introduction|what.*about|main.*content|comprehensive',
                r'tell.*me.*about|give.*me.*overview|what.*does.*cover|what.*is.*about'
            ],
            QueryIntent.HOW_TO: [
                r'如何|怎么|怎样|怎么做|如何做|怎样做|步骤|教程|操作|实现|配置|设置|安装',
                r'方法|流程|过程|执行|运行|使用|部署|建立|创建|制作',
                r'how\s+to|step.*step|tutorial|guide|implement|configure|setup|install',
                r'how.*do|how.*can|process.*of|way.*to|method.*of|instructions'
            ],
            QueryIntent.COMPARISON: [
                r'区别|差异|差别|对比|比较|优缺点|优劣|vs|versus|和.*的不同|与.*区别',
                r'哪个好|哪种好|选择|更好|更适合|不同点|相同点|异同',
                r'difference|compare|comparison|versus|vs|pros.*cons|better.*than',
                r'which.*better|what.*difference|contrast.*with|similar.*different'
            ]
        }

        # 负面模式（减分项）- 如果包含这些模式，降低对应意图的匹配度
        self.negative_patterns = {
            QueryIntent.OVERVIEW: [
                r'具体|详细|特定|某个|单独|个别',  # 这些暗示不是要概述
                r'specific|particular|individual|detailed|exact'
            ],
            QueryIntent.HOW_TO: [
                r'是什么|定义|含义|概念|理论|原理',  # 这些暗示不是要操作指南
                r'what.*is|definition|concept|theory|principle'
            ]
        }

    def _calculate_keyword_score(self, query: str, intent: QueryIntent) -> float:
        """
        计算关键词匹配分数

        Args:
            query: 查询文本
            intent: 意图类型

        Returns:
            匹配分数 (0-1)
        """
        query_lower = query.lower()
        patterns = self.keyword_patterns.get(intent, [])
        negative_patterns = self.negative_patterns.get(intent, [])

        # 正面匹配分数
        positive_score = 0
        total_patterns = len(patterns)

        for pattern in patterns:
            if re.search(pattern, query_lower):
                positive_score += 1

        if total_patterns == 0:
            return 0.0

        positive_ratio = positive_score / total_patterns

        # 负面模式减分
        negative_score = 0
        for pattern in negative_patterns:
            if re.search(pattern, query_lower):
                negative_score += 0.2  # 每个负面模式减0.2分

        # 最终分数
        final_score = max(0.0, positive_ratio - negative_score)

        logger.debug(f"Intent {intent.value}: positive={positive_ratio:.2f}, negative={negative_score:.2f}, final={final_score:.2f}")
        return final_score

    def analyze_intent_by_keywords(self, query: str) -> dict[QueryIntent, float]:
        """
        基于关键词分析查询意图

        Args:
            query: 查询文本

        Returns:
            各个意图的匹配分数字典
        """
        scores = {}

        for intent in QueryIntent:
            score = self._calculate_keyword_score(query, intent)
            scores[intent] = score

        return scores

    def analyze_intent(self, query: str, use_llm_fallback: bool = True) -> QueryIntent:
        """
        分析查询意图

        Args:
            query: 查询文本
            use_llm_fallback: 是否使用LLM作为后备方案

        Returns:
            识别出的查询意图
        """
        logger.debug(f"分析查询意图: {query[:100]}...")

        # 1. 基于关键词的分析
        keyword_scores = self.analyze_intent_by_keywords(query)

        # 找到最高分数的意图
        max_score = max(keyword_scores.values())
        best_intent = max(keyword_scores.items(), key=lambda x: x[1])[0]

        logger.debug(f"关键词分析结果: {dict((k.value, f'{v:.2f}') for k, v in keyword_scores.items())}")

        # 2. 如果关键词匹配分数足够高，直接返回
        if max_score >= 0.3:  # 阈值可调
            logger.info(f"基于关键词识别意图: {best_intent.value} (score: {max_score:.2f})")
            return best_intent

        # 3. 如果关键词匹配分数较低，且有LLM可用，使用语义分析
        if use_llm_fallback and self.llm and max_score < 0.3:
            try:
                semantic_intent = self._semantic_analysis(query)
                logger.info(f"基于语义分析识别意图: {semantic_intent.value}")
                return semantic_intent
            except Exception as e:
                logger.warning(f"语义分析失败，使用关键词结果: {e}")

        # 4. 默认处理逻辑
        if max_score > 0:
            logger.info(f"使用最佳关键词匹配: {best_intent.value} (score: {max_score:.2f})")
            return best_intent

        # 5. 无明确匹配，返回默认意图
        logger.info("无明确意图匹配，默认为事实查询")
        return QueryIntent.FACTUAL

    def _semantic_analysis(self, query: str) -> QueryIntent:
        """
        使用LLM进行语义分析

        Args:
            query: 查询文本

        Returns:
            识别出的查询意图
        """
        prompt = PromptTemplate.from_template("""
分析以下查询的意图类型，从以下选项中选择一个最合适的：

1. overview（概述类）- 用户想要了解某个主题的整体情况、总体介绍、主要内容概览
2. how_to（操作指南类）- 用户想要学习如何做某事、需要步骤指导、操作教程
3. comparison（比较类）- 用户想要比较不同选项、了解区别、优缺点对比
4. factual（事实查询类）- 用户想要了解具体事实、定义、细节信息

查询：{query}

请仔细分析查询的语义和用户真实意图，只返回对应的意图类型（overview/how_to/comparison/factual），不要包含其他内容：
""")

        try:
            response = self.llm.invoke(prompt.format(query=query))
            intent_str = response.content.strip().lower()

            # 解析LLM返回的意图
            for intent in QueryIntent:
                if intent.value in intent_str:
                    return intent

            # 如果解析失败，记录并返回默认值
            logger.warning(f"无法解析LLM返回的意图: {intent_str}")
            return QueryIntent.FACTUAL

        except Exception as e:
            logger.error(f"语义分析调用失败: {e}")
            raise

    def get_intent_description(self, intent: QueryIntent) -> str:
        """
        获取意图的中文描述

        Args:
            intent: 查询意图

        Returns:
            意图的中文描述
        """
        descriptions = {
            QueryIntent.OVERVIEW: "概述查询 - 用户想要了解整体情况和主要内容",
            QueryIntent.HOW_TO: "操作指南查询 - 用户需要步骤指导和实践方法",
            QueryIntent.COMPARISON: "比较查询 - 用户想要对比不同选项的差异",
            QueryIntent.FACTUAL: "事实查询 - 用户想要了解具体事实和详细信息"
        }
        return descriptions.get(intent, "未知意图类型")

    def analyze_with_confidence(self, query: str) -> dict[str, any]:
        """
        分析查询意图并返回详细信息

        Args:
            query: 查询文本

        Returns:
            包含意图、置信度和详细分析的字典
        """
        keyword_scores = self.analyze_intent_by_keywords(query)
        intent = self.analyze_intent(query)

        max_score = max(keyword_scores.values())
        confidence = "high" if max_score >= 0.5 else "medium" if max_score >= 0.3 else "low"

        return {
            "intent": intent,
            "confidence": confidence,
            "confidence_score": max_score,
            "keyword_scores": dict((k.value, v) for k, v in keyword_scores.items()),
            "description": self.get_intent_description(intent),
            "analysis_method": "keyword" if max_score >= 0.3 else "semantic" if self.llm else "default"
        }


# 便捷函数
def create_intent_analyzer(llm: Optional[ChatOpenAI] = None) -> IntentAnalyzer:
    """创建意图分析器实例"""
    return IntentAnalyzer(llm)
