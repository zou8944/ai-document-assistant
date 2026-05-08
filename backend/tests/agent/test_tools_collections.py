"""Tests for chat.agent.tools.collections."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from chat.agent.cancellation import CancellationToken
from chat.agent.tools.base import AgentDeps, ToolContext
from chat.agent.tools.collections import GetCollectionOverviewTool, ListCollectionsTool


def _make_ctx(collection_ids=None, collection_repo=None, document_repo=None):
    return ToolContext(
        chat_id="test",
        collection_ids=collection_ids if collection_ids is not None else ["c1"],
        cancellation=CancellationToken(),
        emit=AsyncMock(),
        deps=AgentDeps(
            collection_repo=collection_repo or MagicMock(),
            document_repo=document_repo or MagicMock(),
        ),
    )


class TestListCollectionsTool:
    async def test_success_returns_markdown(self):
        mock_col = MagicMock()
        mock_col.id = "c1"
        mock_col.name = "Docs"
        mock_col.document_count = 5
        mock_col.summary = "Main documentation"

        repo = MagicMock()
        repo.get_by_id.return_value = mock_col

        ctx = _make_ctx(collection_ids=["c1"], collection_repo=repo)
        tool = ListCollectionsTool()
        result = await tool.run(ctx)

        assert not result.is_error
        assert "Available collections (1):" in result.content
        assert "id=c1" in result.content
        assert "name=\"Docs\"" in result.content
        assert "docs=5" in result.content
        repo.get_by_id.assert_called_once_with("c1")

    async def test_empty_collection_ids(self):
        ctx = _make_ctx(collection_ids=[])
        tool = ListCollectionsTool()
        result = await tool.run(ctx)

        assert not result.is_error
        assert "No collections bound" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.get_by_id.side_effect = RuntimeError("db down")

        ctx = _make_ctx(collection_ids=["c1"], collection_repo=repo)
        tool = ListCollectionsTool()
        result = await tool.run(ctx)

        assert result.is_error
        assert "db down" in result.content


class TestGetCollectionOverviewTool:
    async def test_success_returns_markdown(self):
        mock_col = MagicMock()
        mock_col.id = "c1"
        mock_col.name = "Docs"
        mock_col.readme_content = "Welcome"
        mock_col.categories_json = '["api", "guide"]'
        mock_col.document_count = 10
        mock_col.vector_count = 100

        repo = MagicMock()
        repo.get_by_id.return_value = mock_col

        mock_doc = MagicMock()
        mock_doc.id = "d1"
        mock_doc.name = "Intro"
        mock_doc.summary = "Intro doc"

        doc_repo = MagicMock()
        doc_repo.get_by_collection.return_value = [mock_doc]

        ctx = _make_ctx(collection_ids=["c1"], collection_repo=repo, document_repo=doc_repo)
        tool = GetCollectionOverviewTool()
        result = await tool.run(ctx, collection_id="c1")

        assert not result.is_error
        assert "# Collection: Docs" in result.content
        assert "Welcome" in result.content
        assert "api" in result.content
        assert "documents: 10" in result.content
        assert "vectors: 100" in result.content
        assert "Intro" in result.content

    async def test_collection_not_found(self):
        repo = MagicMock()
        repo.get_by_id.return_value = None

        ctx = _make_ctx(collection_repo=repo)
        tool = GetCollectionOverviewTool()
        result = await tool.run(ctx, collection_id="missing")

        assert result.is_error
        assert "not found" in result.content

    async def test_repo_exception_returns_error(self):
        repo = MagicMock()
        repo.get_by_id.side_effect = RuntimeError("db down")

        ctx = _make_ctx(collection_repo=repo)
        tool = GetCollectionOverviewTool()
        result = await tool.run(ctx, collection_id="c1")

        assert result.is_error
        assert "db down" in result.content

    async def test_no_collection_id(self):
        ctx = _make_ctx()
        tool = GetCollectionOverviewTool()
        result = await tool.run(ctx)

        assert result.is_error
        assert "collection_id is required" in result.content

    async def test_empty_sample_docs(self):
        mock_col = MagicMock()
        mock_col.id = "c1"
        mock_col.name = "Docs"
        mock_col.readme_content = ""
        mock_col.categories_json = None
        mock_col.document_count = 0
        mock_col.vector_count = 0

        repo = MagicMock()
        repo.get_by_id.return_value = mock_col

        doc_repo = MagicMock()
        doc_repo.get_by_collection.return_value = []

        ctx = _make_ctx(collection_repo=repo, document_repo=doc_repo)
        tool = GetCollectionOverviewTool()
        result = await tool.run(ctx, collection_id="c1")

        assert not result.is_error
        assert "No documents found" in result.content
