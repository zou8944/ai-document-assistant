import json
import logging

from chat.generation.base import BaseLLMService
from chat.models import ProcessingMode, QueryIntent, RouterResult

logger = logging.getLogger(__name__)

ROUTER_SYSTEM_PROMPT = """你是一个查询分析专家。你的任务是分析用户的问题，判断其意图类别、复杂度，并推荐处理模式。

## 意图类别（8种）

1. direct_answer - 直接回答：用户询问某个概念、属性、值，答案通常在某一段落中
2. locate - 定位/存在：用户想知道某个信息"在哪里"、"有没有"，需要指出文档位置
3. recommend - 推荐/导航：用户问"应该先看什么"、"推荐哪个"，需要基于文档目录做推荐
4. summarize - 总结概括：用户要求总结某篇或某类文档的核心内容
5. compare - 比较/对比：用户对比两个或多个对象，需要分别检索后对比
6. procedure - 步骤/流程：用户问"怎么做"、"如何操作"，需要找到步骤说明
7. synthesize - 跨文档整合：用户要求整合多个文档中关于同一主题的内容
8. analyze - 分析/判断：用户问"一致吗"、"完整吗"、"有风险吗"，需要分析判断

## 处理模式

- fast: 简单事实查询，预计上下文 < 8k，用轻量模型
- standard: 标准查询，预计上下文 8k-50k，用中等模型
- deep: 复杂查询，预计上下文 > 50k 或需要跨文档分析，用大上下文模型

## 输出格式（JSON）

{
  "intent": "意图类别",
  "confidence": 0.95,
  "reason": "判定理由",
  "suggested_mode": "fast|standard|deep",
  "complexity_score": 5,
  "rewritten_queries": ["检索query1", "检索query2"]
}

规则：
- confidence 必须 0.0-1.0
- complexity_score 必须 1-10
- rewritten_queries 必须至少有一个，针对原问题优化为适合检索的 query
- 如果涉及多个对象（如 A 和 B 的区别），rewritten_queries 应分别针对每个对象
"""


def _strip_markdown_code_fences(text: str) -> str:
    """Remove markdown code fences (```json ... ```) from LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        elif lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


class QueryRouter:
    def __init__(self, llm: BaseLLMService):
        self.llm = llm

    async def analyze(self, query: str, chat_history: list[dict] = None) -> RouterResult:
        logger.info(f"QueryRouter.analyze() started for query: {query[:50]}...")
        history_text = ""
        if chat_history:
            history_lines = []
            for msg in chat_history[-5:]:
                if hasattr(msg, "role"):
                    role = msg.role.value if hasattr(msg.role, "value") else str(msg.role)
                    content = msg.message if hasattr(msg, "message") else getattr(msg, "content", "")
                else:
                    role = msg.get("role", "")
                    content = msg.get("content", "") or msg.get("message", "")
                label = "用户" if role in ("user", "USER") else "助手"
                history_lines.append(f"{label}: {content}")
            history_text = "\n".join(history_lines)

        prompt = f"""历史对话：
{history_text}

当前问题：{query}

请分析上述问题，按要求的 JSON 格式输出。"""

        logger.info(f"QueryRouter.analyze() calling llm.generate() with model={getattr(self.llm, 'model', 'unknown')}")
        response = await self.llm.generate(
            system_prompt=ROUTER_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024
        )
        logger.info(f"QueryRouter.analyze() llm.generate() completed, response length={len(response)}")

        cleaned = _strip_markdown_code_fences(response)

        try:
            result = json.loads(cleaned)
            # Validate required fields
            intent = result.get("intent", "direct_answer")
            confidence = float(result.get("confidence", 0.5))
            reason = result.get("reason", "")
            suggested_mode = result.get("suggested_mode", "standard")
            complexity_score = int(result.get("complexity_score", 5))
            rewritten_queries = result.get("rewritten_queries", [query])
            if not isinstance(rewritten_queries, list):
                rewritten_queries = [query]
            return RouterResult(
                intent=QueryIntent(intent),
                confidence=confidence,
                reason=reason,
                suggested_mode=ProcessingMode(suggested_mode),
                complexity_score=complexity_score,
                rewritten_queries=rewritten_queries
            )
        except Exception as e:
            logger.error(f"Router JSON parse failed: {e}, raw: {response}")
            return RouterResult(
                intent=QueryIntent.DIRECT_ANSWER,
                confidence=0.5,
                reason=f"解析失败，回退到默认: {e}",
                suggested_mode=ProcessingMode.STANDARD,
                complexity_score=5,
                rewritten_queries=[query]
            )
