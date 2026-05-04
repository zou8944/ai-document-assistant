"""
LLM service for centralized AI model management and operations.
"""

import asyncio
import json
import logging
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from models.rag import CollectionSummary, DocChunk, HistoryItem
from rag.document_summarizer import DocumentSummarizer
from rag.intent_analyzer import IntentAnalyzer
from rag.prompt_templates import build_rag_prompt

logger = logging.getLogger(__name__)

# Overall timeout (seconds) for any single LLM call; prevents Ctrl+C from hanging
LLM_TIMEOUT = 180


class LLMService:
    """Centralized service for all LLM-related operations"""

    def __init__(self, config):
        self.config = config

        # Initialize OpenAI components
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        # Initialize specialized components
        self.intent_analyzer = IntentAnalyzer(llm=self.llm)
        self.document_summarizer = DocumentSummarizer(self.llm)

        # Initialize output parser for text generation
        self.text_parser = StrOutputParser()

        logger.info("LLMService initialized successfully")

    # ==================== Embedding Operations ====================

    async def embed_query(self, query: str) -> list[float]:
        logger.info("[LLM] embed_query start, query_len=%d", len(query))
        t0 = time.monotonic()
        result = await asyncio.wait_for(self.embeddings.aembed_query(query), timeout=LLM_TIMEOUT)
        logger.info("[LLM] embed_query done, %.2fs", time.monotonic() - t0)
        return result

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.info("[LLM] embed_documents start, count=%d", len(texts))
        t0 = time.monotonic()
        result = await asyncio.wait_for(self.embeddings.aembed_documents(texts), timeout=LLM_TIMEOUT)
        logger.info("[LLM] embed_documents done, %.2fs", time.monotonic() - t0)
        return result

    # ==================== Intent Analysis ====================

    async def analyze_intent(self, user_message: str):
        return await self.intent_analyzer.analyze(user_message)

    # ==================== Document Summarization ====================

    async def summarize_document(self, content: str) -> str:
        return await self.document_summarizer.summarize_document_async(content)

    async def summarize_collection(self, document_summaries: list[str]) -> str:
        return await self.document_summarizer.summarize_collection_async(document_summaries)

    # ==================== RAG Chat Operations ====================

    def build_rag_prompt(
        self,
        collections: list[CollectionSummary],
        histories: list[HistoryItem],
        reference_chunks: list[DocChunk],
        user_query: str
    ) -> str:
        return build_rag_prompt(
            collections=collections,
            histories=histories,
            reference_chunks=reference_chunks,
            user_query=user_query
        )

    async def generate_chat_response(self, prompt: str) -> str:
        logger.info("[LLM] generate_chat_response start, prompt_len=%d", len(prompt))
        t0 = time.monotonic()
        chain = self.llm | self.text_parser
        result = await asyncio.wait_for(chain.ainvoke(prompt), timeout=LLM_TIMEOUT)
        logger.info("[LLM] generate_chat_response done, %.2fs, output_len=%d", time.monotonic() - t0, len(result))
        return result

    async def stream_chat_response(self, prompt: str):
        logger.info("[LLM] stream_chat_response start, prompt_len=%d", len(prompt))
        t0 = time.monotonic()
        stream = self.llm.astream(prompt)
        while True:
            try:
                chunk = await asyncio.wait_for(stream.__anext__(), timeout=LLM_TIMEOUT)
            except StopAsyncIteration:
                break
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if content:
                yield content
        logger.info("[LLM] stream_chat_response done, %.2fs", time.monotonic() - t0)

    # ==================== README Generation ====================

    async def filter_by_summaries(self, user_query: str, summaries_block: str) -> list[int]:
        """Returns list of 1-based document indices relevant to the query."""
        logger.info("[LLM] filter_by_summaries start, query_len=%d, summaries_len=%d", len(user_query), len(summaries_block))
        t0 = time.monotonic()
        from rag.prompt_templates import SUMMARY_FILTER_PROMPT
        chain = SUMMARY_FILTER_PROMPT | self.llm | self.text_parser
        result = await asyncio.wait_for(
            chain.ainvoke({"user_query": user_query, "summaries_block": summaries_block}),
            timeout=LLM_TIMEOUT,
        )
        logger.info("[LLM] filter_by_summaries done, %.2fs", time.monotonic() - t0)
        try:
            indices = json.loads(result.strip())
            return [int(i) for i in indices if isinstance(i, int) and i > 0]
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse summary filter result: {result}")
            return []

    async def generate_readme(self, pages: list[dict], source_language: str = "en") -> str:
        """
        Given a list of {path, title} dicts, generate a README navigation guide
        and structured categories data. Returns a JSON string.

        When source_language is 'zh', generates Chinese-only content.
        When source_language is 'en' or other, generates bilingual content
        with both English and Chinese versions.
        """
        pages_text = "\n".join(f"- {p['path']}: {p['title']}" for p in pages)
        logger.info(f"[generate_readme] pages count: {len(pages)}, total chars: {len(pages_text)}")
        logger.info(f"[generate_readme] pages_text:\n{pages_text}")

        if source_language == "zh":
            prompt = f"""You are analyzing a documentation website. Given the page paths and titles below,
generate a navigation guide README and structured category data in Chinese.

Respond with ONLY a JSON object in this exact format:
{{
  "readme": "# 欢迎\\n\\n> 简短介绍这个文档站的整体定位和内容范围...\\n\\n## 文档目录\\n\\n- [分类一名称](#分类一名称)\\n- [分类二名称](#分类二名称)\\n...\\n\\n## 整体介绍\\n\\n这个网站是关于...的文档站。\\n\\n根据你的需求，可以前往不同页面：\\n\\n- 如果你是新手，建议从 [快速开始](doc:///path) 开始\\n- 如果你想了解 API，请查看 [API 参考](doc:///path)\\n...\\n\\n## 分类一名称\\n\\n- [页面标题](doc:///path) — 简短描述\\n...",
  "categories": [
    {{
      "category": "分类名称",
      "pages": [
        {{"path": "/path", "title": "页面标题", "description": "1-2句话的描述"}},
        ...
      ]
    }},
    ...
  ]
}}

Rules for "readme":
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## 文档目录" section (at the TOP): list all categories as anchor links: [分类名](#分类名)
  - Use the exact category name as the anchor (no slug conversion)
  - Example: [快速开始](#快速开始), [API 文档](#API 文档)
- "## 整体介绍" section (second): write 2-4 natural paragraphs describing:
  - What topics this documentation site covers
  - Guidance for different users on where to find information
  - Use doc:///path links to point to specific pages
  - Brief overview of each category's content
- Then list each category as a ## heading with page links underneath
- Under each category, list pages as Markdown links: [页面标题](doc:///path)
- Include a brief description after each link (em dash separator)
- Use Markdown formatting (headings, lists, bold)

Rules for "categories":
- Group similar pages under meaningful category labels in Chinese
- Each page needs: path, title (Chinese), description (Chinese, 1-2 sentences)
- Categories should be concise (2-6 Chinese characters)

Pages:
{pages_text}"""
        else:
            prompt = f"""You are analyzing a documentation website. Given the page paths and titles below,
generate a navigation guide README and structured category data in BOTH English and Chinese.

Respond with ONLY a JSON object in this exact format:
{{
  "readme": "# Welcome\\n\\n> A short overview of this documentation site...\\n\\n## Table of Contents\\n\\n- [Category One](#Category One)\\n- [Category Two](#Category Two)\\n...\\n\\n## Overview\\n\\nThis site covers...\\n\\nDepending on your needs:\\n\\n- If you are new, start with [Quick Start](doc:///path)\\n- For API reference, see [API Docs](doc:///path)\\n...\\n\\n## Category One\\n\\n- [Page Title](doc:///path) — short description\\n...",
  "readme_zh": "# 欢迎\\n\\n> 简短介绍这个文档站的整体定位和内容范围...\\n\\n## 文档目录\\n\\n- [分类一名称](#分类一名称)\\n- [分类二名称](#分类二名称)\\n...\\n\\n## 整体介绍\\n\\n这个网站是关于...的文档站。\\n\\n根据你的需求，可以前往不同页面：\\n\\n- 如果你是新手，建议从 [快速开始](doc:///path) 开始\\n- 如果你想了解 API，请查看 [API 参考](doc:///path)\\n...\\n\\n## 分类一名称\\n\\n- [页面中文标题](doc:///path) — 简短中文描述\\n...",
  "categories": [
    {{
      "category": "Category Name",
      "category_zh": "分类中文名",
      "pages": [
        {{"path": "/path", "title": "Page Title", "title_zh": "页面中文标题", "description": "1-2 sentence description", "description_zh": "1-2句话的中文描述"}},
        ...
      ]
    }},
    ...
  ]
}}

Rules for "readme" (English):
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## Table of Contents" section (at the TOP): list all categories as anchor links: [Category Name](#Category Name)
  - Use the exact category name as the anchor (no slug conversion)
  - Example: [Getting Started](#Getting Started), [API Reference](#API Reference)
- "## Overview" section (second): write 2-4 natural paragraphs describing:
  - What topics this documentation site covers
  - Guidance for different users on where to find information
  - Use doc:///path links to point to specific pages
  - Brief overview of each category's content
- Then list each category as a ## heading with page links underneath
- Under each category, list pages as Markdown links: [Page Title](doc:///path)
- Include a brief description after each link (em dash separator)
- Use Markdown formatting (headings, lists, bold)

Rules for "readme_zh" (Chinese):
- Same structure as English version but all content in natural Chinese
- "## 文档目录" for table of contents, "## 整体介绍" for overview
- Use doc:///path links (same paths as English version)

Rules for English content:
- Write in natural, helpful language
- Categories should be concise (2-4 words)

Rules for Chinese content:
- Translate all content accurately into natural Chinese
- Category names should be concise (2-6 Chinese characters)
- Page titles should be meaningful Chinese translations
- Descriptions should be fluent Chinese

Pages:
{pages_text}"""
        logger.info(f"[generate_readme] full prompt length: {len(prompt)} chars (~{len(prompt) // 4} tokens)")
        return await self.invoke_llm(prompt, max_tokens=self.config.llm.max_tokens)

    # ==================== Direct LLM Access ====================

    async def invoke_llm(self, prompt: str, **kwargs) -> str:
        logger.info("[LLM] invoke_llm start, prompt_len=%d", len(prompt))
        t0 = time.monotonic()
        result = await asyncio.wait_for(
            self.llm.ainvoke(prompt, **kwargs), timeout=LLM_TIMEOUT
        )
        output = str(result.content) if hasattr(result, 'content') and result is not None else str(result)
        logger.info("[LLM] invoke_llm done, %.2fs, output_len=%d", time.monotonic() - t0, len(output))
        return output

    async def stream_llm(self, prompt: str, **kwargs):
        async for chunk in self.llm.astream(prompt, **kwargs):
            yield chunk

    def close(self):
        logger.info("LLMService resources closed")
