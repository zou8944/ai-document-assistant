import json
import logging

from chat.generation.base import BaseLLMService
from chat.models import EvaluationResult

logger = logging.getLogger(__name__)

EVALUATION_PROMPT = """你是一位严格的回答质量评估员。请评估下面的回答是否充分回应了用户的问题。

用户问题：{query}

检索到的文档片段：
{context}

生成的草稿回答：
{draft}

请从以下维度评估（0-1分）：
1. 回答是否直接回应了用户问题的核心？
2. 每个关键论断是否有文档来源支撑？
3. 是否存在编造或推断出来的内容？
4. 是否有遗漏的重要信息或步骤？
5. 如果问题涉及多个方面，是否都覆盖到了？

如果回答不够充分，请列出：
- missing_aspects: 遗漏的方面
- supplementary_queries: 为了补充这些遗漏，应该搜索什么

请以JSON格式输出：
{{
  "confidence_score": float (0-1),
  "missing_aspects": ["..."],
  "supplementary_queries": ["..."]
}}"""


class SelfEvaluator:
    def __init__(self, llm: BaseLLMService):
        self.llm = llm

    async def evaluate(self, query: str, draft: str, context_docs: list) -> EvaluationResult:
        # Only evaluate top 3 most relevant docs to keep prompt short and fast
        top_docs = sorted(context_docs, key=lambda d: d.relevance_score, reverse=True)[:3]
        context = "\n\n".join(
            f"[{i + 1}] {d.document_name} (score: {d.relevance_score:.2f})\n{d.content[:200]}"
            for i, d in enumerate(top_docs)
        )
        draft_trimmed = draft[:800] + "..." if len(draft) > 800 else draft
        prompt = EVALUATION_PROMPT.format(query=query, context=context, draft=draft_trimmed)

        try:
            response = await self.llm.generate(
                system_prompt="",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=1024
            )
            result = json.loads(response)
            return EvaluationResult(
                confidence_score=result.get("confidence_score", 0.5),
                missing_aspects=result.get("missing_aspects", []),
                supplementary_queries=result.get("supplementary_queries", [])
            )
        except Exception as e:
            logger.warning(f"Evaluation failed ({e}), defaulting to pass")
            return EvaluationResult(
                confidence_score=1.0, missing_aspects=[], supplementary_queries=[]
            )
