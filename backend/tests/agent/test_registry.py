"""Tests for chat.agent.registry.ToolRegistry."""

import pytest

from chat.agent.registry import ToolRegistry
from chat.agent.tools.base import Tool, ToolContext, ToolResult


class DummyTool(Tool):
    name = "dummy"
    description = "A dummy tool."
    input_schema = {"type": "object", "properties": {}}
    preserve_in_compact = True

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="ok")


class AnotherTool(Tool):
    name = "another"
    description = "Another tool."
    input_schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    preserve_in_compact = False

    async def run(self, ctx: ToolContext, **kwargs) -> ToolResult:
        return ToolResult(content="ok")


class TestToolRegistry:
    def test_register_and_handler(self):
        registry = ToolRegistry()
        tool = DummyTool()
        registry.register(tool)
        assert registry.handler("dummy") is tool

    def test_handler_missing_tool(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.handler("missing")

    def test_schemas(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        registry.register(AnotherTool())
        schemas = registry.schemas()
        assert len(schemas) == 2
        names = {s["name"] for s in schemas}
        assert names == {"dummy", "another"}
        for s in schemas:
            assert "description" in s
            assert "input_schema" in s

    def test_schemas_empty(self):
        registry = ToolRegistry()
        assert registry.schemas() == []

    def test_get_preserve_set(self):
        registry = ToolRegistry()
        registry.register(DummyTool())
        registry.register(AnotherTool())
        preserve = registry.get_preserve_set()
        assert preserve == {"dummy"}
