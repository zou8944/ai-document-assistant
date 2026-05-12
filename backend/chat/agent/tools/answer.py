"""Start answer tool — signals that the next output is the final answer."""

from chat.agent.tools.base import Tool, ToolContext, ToolResult


class StartAnswerTool(Tool):
    name = "start_answer"
    description = (
        "在调用完所有检索工具和 cite_sources 后，调用此工具表示你即将输出最终答案。"
        "调用后，你的下一次输出将作为最终答案展示给用户。"
    )
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="OK, please provide your answer.")
