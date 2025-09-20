"""
用户查询意图分析模块
基于关键词匹配和语义分析识别查询类型
"""

import json
import logging
from dataclasses import dataclass
from enum import Enum

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from markdown_it import MarkdownIt

logger = logging.getLogger(__name__)

INTENT_ANALYSIS_PROMPT = PromptTemplate.from_template("""
你是一个意图识别助手，任务是根据用户问题，判断其意图类别，并给出适合 RAG 系统的处理策略和检索 query。

意图类别一共 15 种：
1. 定义/解释
2. 特点/属性
3. 分类/类型
4. 实例/例子
5. 对比/区别
6. 优缺点/利弊
7. 推荐/选择
8. 操作/方法
9. 步骤/流程
10. 错误排查/问题解决
11. 优化/改进
12. 原因/解释现象
13. 影响/结果/后果
14. 总结/归纳
15. 生成/改写/创意
16. 元认知（关于AI助手本身的功能、使用等问题）
17. 其它（不属于上面的所有问题）

输出格式要求（JSON 格式）：
{{
  "intent": "意图类别",
  "reason": "为什么判定为该意图类别",
  "strategy": "RAG 的处理策略，说明是否需要 query 重写，以及如何检索",
  "queries": ["具体的检索 query 1", "具体的检索 query 2", "..."]
}}

示例 1：
用户问题: "Redis 和 Memcached 有什么区别？"

输出:
{{
  "intent": "对比/区别",
  "reason": "问题包含 '有什么区别'，明确是对比两个对象",
  "strategy": "需要 query 重写，分别检索两者特点，再由 LLM 总结差异",
  "queries": ["Redis 的特点和应用场景", "Memcached 的特点和应用场景"]
}}

示例 2：
用户问题: "如何在 Linux 上安装 PostgreSQL？"

输出:
{{
  "intent": "操作/方法",
  "reason": "问题是 '如何安装'，属于操作步骤问题",
  "strategy": "直接检索安装方法相关内容",
  "queries": ["在 Linux 系统上安装 PostgreSQL 的方法", "PostgreSQL Linux 安装步骤"]
}}
------
用户问题: {query}
""")

class QueryIntent(Enum):
    """查询意图枚举"""
    DEFINITION = "定义/解释"
    FEATURES = "特点/属性"
    CLASSIFICATION = "分类/类型"
    EXAMPLES = "实例/例子"
    COMPARISON = "对比/区别"
    PROS_CONS = "优缺点/利弊"
    RECOMMENDATION = "推荐/选择"
    HOW_TO = "操作/方法"
    STEPS = "步骤/流程"
    TROUBLESHOOTING = "错误排查/问题解决"
    OPTIMIZATION = "优化/改进"
    CAUSES = "原因/解释现象"
    IMPACT = "影响/结果/后果"
    SUMMARY = "总结/归纳"
    GENERATION = "生成/改写/创意"
    META_COGNITION = "元认知"
    OTHER = "其它"


@dataclass
class AnalysisResult:
    intent: QueryIntent
    reason: str
    strategy: str
    queries: list[str]

    @staticmethod
    def from_dict(data: dict) -> "AnalysisResult":
        return AnalysisResult(
            intent=QueryIntent(data["intent"]),
            reason=data["reason"],
            strategy=data["strategy"],
            queries=data["queries"],
        )


class IntentAnalyzer:

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.markdown_it = MarkdownIt()
        self.fallback_intent = AnalysisResult(
            intent=QueryIntent.OTHER,
            reason="无法识别具体意图，归类为其它",
            strategy="不进行 query 重写，直接使用原始查询",
            queries=[],
        )

    def _extract_code_block(self, md_text, lang="json"):
        tokens = self.markdown_it.parse(md_text)
        for token in tokens:
            if token.type == "fence" and token.info.strip() == lang:
                return token.content
        return None

    async def analyze(self, query: str) -> AnalysisResult:
        chain = INTENT_ANALYSIS_PROMPT | self.llm | StrOutputParser()

        ai_res = await chain.ainvoke({
            "query": query
        })

        try:
            res_dict = json.loads(self._extract_code_block(ai_res) or ai_res)
            return AnalysisResult.from_dict(res_dict)
        except Exception as e:
            logger.error(f"Failed to parse intent analysis result: {e}", exc_info=True)
            return self.fallback_intent


def create_intent_analyzer(llm: ChatOpenAI) -> IntentAnalyzer:
    return IntentAnalyzer(llm)

if __name__ == "__main__":
    import asyncio

    from langchain_openai import ChatOpenAI

    async def main():
        args = {
            "model": "deepseek-ai/DeepSeek-V3",
            "temperature": 0.1,
            "api_key": "CCC",
            "base_url": "DDD"
        }
        llm = ChatOpenAI(**args)
        analyzer = IntentAnalyzer(llm)

        queries = [
            "Redis 和 Memcached 有什么区别？",
            "如何在 Linux 上安装 PostgreSQL？",
            "Python 的主要特点有哪些？",
            "给我推荐几本学习机器学习的书籍。",
            "什么是量子计算？",
            "请总结一下人工智能的发展历程。",
            "帮我写一首关于春天的诗。",
            "AI 助手能做什么？",
            "今天的天气怎么样？",
            "简单介绍一下当前的知识库",
        ]

        for query in queries:
            result = await analyzer.analyze(query)
            print(f"Query: {query}")
            print(f"Intent: {result.intent.value}")
            print(f"Reason: {result.reason}")
            print(f"Strategy: {result.strategy}")
            print(f"Queries: {result.queries}")
            print("-" * 40)

    asyncio.run(main())
