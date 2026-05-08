"""Tool registry for the agent."""

from chat.agent.tools.base import Tool


class ToolRegistry:
    """Holds registered tools and exposes schemas/handlers."""

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def schemas(self) -> list[dict]:
        """Return JSON schemas for Anthropic tools= parameter."""
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": t.input_schema,
            }
            for t in self._tools.values()
        ]

    def handler(self, name: str) -> Tool:
        return self._tools[name]

    def get_preserve_set(self) -> set[str]:
        """Return names of tools whose results should never be compacted."""
        return {name for name, t in self._tools.items() if t.preserve_in_compact}
