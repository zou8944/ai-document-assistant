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
6. context_completeness: 当前文档上下文是否完整覆盖了用户问题的答案？对于流程/步骤类问题，是否包含从开始到结束的全部步骤？是否有截断？
7. source_sufficiency: 来源数量和质量是否足够支撑完整回答？

如果回答不够充分，请列出：
- missing_aspects: 遗漏的方面
- supplementary_queries: 为了补充这些遗漏，应该搜索什么
- supplementary_strategy: 补充检索策略建议，可选值：
  - "vector": 需要通过向量检索找更多相关文档
  - "full_doc": 已有高相关文档，需要读取其完整内容
  - "none": 不需要补充

请以JSON格式输出：
{{
  "confidence_score": float (0-1),
  "context_completeness": float (0-1),
  "source_sufficiency": float (0-1),
  "missing_aspects": ["..."],
  "supplementary_queries": ["..."],
  "supplementary_strategy": "vector|full_doc|none"
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
                supplementary_queries=result.get("supplementary_queries", []),
                context_completeness=result.get("context_completeness", 0.5),
                source_sufficiency=result.get("source_sufficiency", 0.5),
                supplementary_strategy=result.get("supplementary_strategy", "vector")
            )
        except Exception as e:
            logger.warning(f"Evaluation failed ({e}), defaulting to pass")
            return EvaluationResult(
                confidence_score=1.0,
                missing_aspects=[],
                supplementary_queries=[],
                context_completeness=1.0,
                source_sufficiency=1.0,
                supplementary_strategy="none"
            )
