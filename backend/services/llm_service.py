"""
LLM service for centralized AI model management and operations.
"""

import asyncio
import json
import logging
import re
import time

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from models.rag import CollectionSummary, DocChunk, HistoryItem
from rag.document_summarizer import DocumentSummarizer
from rag.intent_analyzer import IntentAnalyzer
from rag.prompt_templates import build_rag_prompt

logger = logging.getLogger(__name__)

# Overall timeout (seconds) for any single LLM call; prevents Ctrl+C from hanging
LLM_TIMEOUT = 300


class LLMService:
    """Centralized service for all LLM-related operations"""

    def __init__(self, config):
        self.config = config

        # Initialize OpenAI components
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        # Initialize crawl-specific LLM (falls back to chat_model if not configured)
        crawl_kwargs = self.config.get_openai_crawl_kwargs()
        self.crawl_llm = ChatOpenAI(**crawl_kwargs)
        if self.config.llm.crawl_model:
            logger.info("Using separate crawl model: %s", self.config.llm.crawl_model)

        # Initialize specialized components
        self.intent_analyzer = IntentAnalyzer(llm=self.llm)
        self.document_summarizer = DocumentSummarizer(self.llm)

        # Initialize output parser for text generation
        self.text_parser = StrOutputParser()

        logger.info("LLMService initialized successfully")

    # ==================== Embedding Operations ====================

    async def embed_query(self, query: str) -> list[float]:
        logger.info("[LLM] embed_query start, model=%s, query_len=%d", self.embeddings.model, len(query))
        t0 = time.monotonic()
        result = await asyncio.wait_for(self.embeddings.aembed_query(query), timeout=LLM_TIMEOUT)
        logger.info("[LLM] embed_query done, %.2fs", time.monotonic() - t0)
        return result

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.info("[LLM] embed_documents start, model=%s, count=%d", self.embeddings.model, len(texts))
        t0 = time.monotonic()
        result = await asyncio.wait_for(self.embeddings.aembed_documents(texts), timeout=LLM_TIMEOUT)
        logger.info("[LLM] embed_documents done, %.2fs", time.monotonic() - t0)
        return result

    # ==================== Intent Analysis ====================

    async def analyze_intent(self, user_message: str):
        return await self.intent_analyzer.analyze(user_message)

    # ==================== Document Summarization ====================

    async def summarize_document(self, content: str) -> str:
        return await self.document_summarizer.summarize_document_async(content, llm=self.crawl_llm)

    async def summarize_collection(self, document_summaries: list[str]) -> str:
        return await self.document_summarizer.summarize_collection_async(document_summaries, llm=self.crawl_llm)

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
        logger.info("[LLM] generate_chat_response start, model=%s, prompt_len=%d", self.llm.model_name, len(prompt))
        t0 = time.monotonic()
        chain = self.llm | self.text_parser
        result = await asyncio.wait_for(chain.ainvoke(prompt), timeout=LLM_TIMEOUT)
        logger.info("[LLM] generate_chat_response done, %.2fs, output_len=%d", time.monotonic() - t0, len(result))
        return result

    async def stream_chat_response(self, prompt: str):
        logger.info("[LLM] stream_chat_response start, model=%s, prompt_len=%d", self.llm.model_name, len(prompt))
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
        logger.info("[LLM] filter_by_summaries start, model=%s, query_len=%d, summaries_len=%d", self.crawl_llm.model_name, len(user_query), len(summaries_block))
        t0 = time.monotonic()
        from rag.prompt_templates import SUMMARY_FILTER_PROMPT
        chain = SUMMARY_FILTER_PROMPT | self.crawl_llm | self.text_parser
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

    # ==================== README Generation (Split into independent calls) ====================

    @staticmethod
    def _build_groups_text(groups: list[dict]) -> str:
        """Build compact group summary for prompts."""
        group_lines = []
        for g in groups:
            cat = g["category"]
            group_pages = g["pages"]
            sample = group_pages[:5]
            page_lines = "\n".join(f"    - {p['path']}: {p['title']}" for p in sample)
            more = f"    ... and {len(group_pages) - 5} more pages" if len(group_pages) > 5 else ""
            group_lines.append(f"- {cat} ({len(group_pages)} pages)\n{page_lines}{more}")
        return "\n".join(group_lines)

    async def generate_readme_content(self, groups: list[dict], language: str = "en") -> str:
        """Generate README markdown. For 'zh' generates Chinese, otherwise English."""
        groups_text = self._build_groups_text(groups)

        if language == "zh":
            prompt = f"""You are analyzing a documentation website. Given the grouped page data below,
generate a navigation guide README in Chinese. Respond with ONLY the Markdown content, no JSON wrapper.

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## 文档目录" section (at the TOP): list all groups as anchor links: [分类名](#分类名)
  - Use the exact group name as the anchor (no slug conversion)
- "## 整体介绍" section (second): write 2-4 natural paragraphs describing:
  - What topics this documentation site covers
  - Guidance for different users on where to find information
  - Use doc:///path links to point to specific pages
  - Brief overview of each group's content
- Then list each group as a ## heading with page links underneath
- Under each group, list up to 5 representative pages as Markdown links: [页面标题](doc:///path)
- Include a brief description after each link (em dash separator)
- Use Markdown formatting (headings, lists, bold)
- Do NOT list every single page if a group has many pages; pick the most representative ones

Groups:
{groups_text}"""
        else:
            prompt = f"""You are analyzing a documentation website. Given the grouped page data below,
generate a navigation guide README in English. Respond with ONLY the Markdown content, no JSON wrapper.

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## Table of Contents" section (at the TOP): list all groups as anchor links: [Group Name](#Group Name)
  - Use the exact group name as the anchor (no slug conversion)
- "## Overview" section (second): write 2-4 natural paragraphs describing:
  - What topics this documentation site covers
  - Guidance for different users on where to find information
  - Use doc:///path links to point to specific pages
  - Brief overview of each group's content
- Then list each group as a ## heading with page links underneath
- Under each group, list up to 5 representative pages as Markdown links: [Page Title](doc:///path)
- Include a brief description after each link (em dash separator)
- Use Markdown formatting (headings, lists, bold)
- Do NOT list every single page if a group has many pages; pick the most representative ones

Groups:
{groups_text}"""
        logger.info(f"[generate_readme_content] lang={language}, prompt_len={len(prompt)}")
        return await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)

    async def translate_readme(self, readme_en: str) -> str:
        """Translate English README to Chinese."""
        prompt = f"""Translate the following English documentation README into natural, fluent Chinese.
Preserve all Markdown formatting. Do NOT translate the paths inside doc:/// links, only the link text.
Respond with ONLY the translated Markdown content.

{readme_en}"""
        logger.info(f"[translate_readme] prompt_len={len(prompt)}")
        return await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)

    async def translate_category_names(self, group_names: list[str]) -> dict[str, str]:
        """Translate group names to Chinese. Returns {{en_name: zh_name}} mapping."""
        names_text = "\n".join(f"- {n}" for n in group_names)
        prompt = f"""Translate the following group names into concise natural Chinese (2-6 characters each).
Respond with ONLY a JSON object mapping each English name to Chinese.

Group names:
{names_text}

Format:
{{"GroupName": "分组中文名", ...}}"""
        logger.info(f"[translate_category_names] names={len(group_names)}")
        raw = await self._invoke_crawl_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse category name translation result: {raw}")
            return {}

    async def translate_page_titles(self, pages: list[dict]) -> dict[str, str]:
        """Translate page titles to Chinese. Returns {{path: zh_title}} mapping."""
        pages_text = "\n".join(f"- {p['path']}: {p['title']}" for p in pages)
        prompt = f"""Translate the following page titles into natural Chinese.
Respond with ONLY a JSON object mapping each path to its Chinese title.

Pages:
{pages_text}

Format:
{{"/path": "中文标题", ...}}"""
        logger.info(f"[translate_page_titles] pages={len(pages)}")
        raw = await self._invoke_crawl_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse page title translation result: {raw}")
            return {}

    # ==================== Direct LLM Access ====================

    async def invoke_llm(self, prompt: str, **kwargs) -> str:
        logger.info("[LLM] invoke_llm start, model=%s, prompt_len=%d", self.llm.model_name, len(prompt))
        t0 = time.monotonic()
        result = await asyncio.wait_for(
            self.llm.ainvoke(prompt, **kwargs), timeout=LLM_TIMEOUT
        )
        output = str(result.content) if hasattr(result, 'content') and result is not None else str(result)
        logger.info("[LLM] invoke_llm done, %.2fs, output_len=%d", time.monotonic() - t0, len(output))
        return output

    async def _invoke_crawl_llm(self, prompt: str, **kwargs) -> str:
        logger.info("[LLM] _invoke_crawl_llm start, model=%s, prompt_len=%d", self.crawl_llm.model_name, len(prompt))
        t0 = time.monotonic()
        result = await asyncio.wait_for(
            self.crawl_llm.ainvoke(prompt, **kwargs), timeout=LLM_TIMEOUT
        )
        output = str(result.content) if hasattr(result, 'content') and result is not None else str(result)
        logger.info("[LLM] _invoke_crawl_llm done, %.2fs, output_len=%d", time.monotonic() - t0, len(output))
        return output

    async def stream_llm(self, prompt: str, **kwargs):
        async for chunk in self.llm.astream(prompt, **kwargs):
            yield chunk

    def close(self):
        logger.info("LLMService resources closed")
