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
    def _build_groups_text(groups: list[dict], max_per_group: int = 5) -> str:
        """Build compact group summary for prompts."""
        group_lines = []
        for g in groups:
            cat = g["category"]
            group_pages = g["pages"]
            sample = group_pages[:max_per_group]
            page_lines = "\n".join(f"    - {p['path']}: {p['title']}" for p in sample)
            more = f"    ... and {len(group_pages) - max_per_group} more pages" if len(group_pages) > max_per_group else ""
            group_lines.append(f"- {cat} ({len(group_pages)} pages)\n{page_lines}{more}")
        return "\n".join(group_lines)

    async def generate_readme_content(self, groups: list[dict], language: str = "en", total_pages: int = 0) -> str:
        """Generate README markdown. For 'zh' generates Chinese, otherwise English.

        The number of representative pages per group scales with total document count:
        - < 30 pages: list all pages per group
        - 30-100 pages: up to 40 per group
        - > 100 pages: up to 45 per group
        """
        if total_pages < 30:
            max_per_group = total_pages  # effectively unlimited
        elif total_pages <= 100:
            max_per_group = 40
        else:
            max_per_group = 45

        groups_text = self._build_groups_text(groups, max_per_group=max_per_group)

        if language == "zh":
            prompt = f"""You are analyzing a documentation website. Given the grouped page data below,
generate a navigation guide README in Chinese. Respond with ONLY the Markdown content, no JSON wrapper.

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## 文档目录" section (at the TOP): list all groups as anchor links: [分类名](#分类名)
  - Use the exact group name as the anchor (no slug conversion)
- "## 整体介绍" section (second): write 3-5 natural paragraphs describing:
  - What topics this documentation site covers overall
  - The intended audience and what they can learn
  - Guidance for different users (beginners, advanced users, developers) on where to start
  - A brief overview of each group's content and how groups relate to each other
  - Use doc:///path links to point to specific key pages
- The groups below are already ordered from beginner-friendly to advanced; preserve this order in the table of contents and section headings
- Then list each group as a ## heading with page links underneath
- Under each group, start with a 1-2 sentence description of the group's theme
- Then list the representative pages as Markdown links: [页面标题](doc:///path)
- Include a brief description after each link (em dash separator)
- If a group has many pages beyond what's listed, add a note like "... 以及另外 X 个页面"
- Use Markdown formatting (headings, lists, bold)
- Do NOT list every single page if a group has many pages; focus on the most important and representative ones

Groups:
{groups_text}"""
        else:
            prompt = f"""You are analyzing a documentation website. Given the grouped page data below,
generate a navigation guide README in English. Respond with ONLY the Markdown content, no JSON wrapper.

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## Table of Contents" section (at the TOP): list all groups as anchor links: [Group Name](#Group Name)
  - Use the exact group name as the anchor (no slug conversion)
- "## Overview" section (second): write 3-5 natural paragraphs describing:
  - What topics this documentation site covers overall
  - The intended audience and what they can learn
  - Guidance for different users (beginners, advanced users, developers) on where to start
  - A brief overview of each group's content and how groups relate to each other
  - Use doc:///path links to point to specific key pages
- The groups below are already ordered from beginner-friendly to advanced; preserve this order in the table of contents and section headings
- Then list each group as a ## heading with page links underneath
- Under each group, start with a 1-2 sentence description of the group's theme
- Then list the representative pages as Markdown links: [Page Title](doc:///path)
- Include a brief description after each link (em dash separator)
- If a group has many pages beyond what's listed, add a note like "... and X more pages"
- Use Markdown formatting (headings, lists, bold)
- Do NOT list every single page if a group has many pages; focus on the most important and representative ones

Groups:
{groups_text}"""
        logger.info(f"[generate_readme_content] lang={language}, total_pages={total_pages}, max_per_group={max_per_group}, prompt_len={len(prompt)}")
        return await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)

    async def categorize_pages(self, pages: list[dict]) -> list[dict]:
        """Use AI to group pages by semantic topic.

        Returns groups in the format: [{"category": str, "pages": [{"path": str, "title": str}, ...]}]
        Guarantees 100% coverage - all pages are assigned to a group.
        Raises exception on failure (no fallback).
        """
        pages_text = "\n".join(f"- {p['path']}: {p['title']}" for p in pages)

        prompt = f"""You are organizing documentation pages into logical topic groups.
Analyze the page paths and titles below, and group them by content/theme similarity.

Each page must belong to exactly one group. Create meaningful, concise group names (2-4 words).
The number of groups should be natural based on content diversity (typically 4-10 groups).
Pages that don't clearly fit any theme should go into a group named "Other".

Pages:
{pages_text}

Return ONLY a JSON object in this exact format:
{{
  "groups": [
    {{
      "name": "Group Name",
      "description": "Brief description of what this group covers",
      "pages": ["/path1", "/path2"]
    }}
  ]
}}"""
        logger.info(f"[categorize_pages] pages={len(pages)}, prompt_len={len(prompt)}")
        raw = await self._invoke_crawl_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            data = json.loads(cleaned)
            groups_data = data.get("groups", [])
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse categorize_pages result: {e}, raw={raw[:500]}")
            raise

        # Build result and validate coverage
        all_paths = {p["path"] for p in pages}
        covered_paths: set[str] = set()
        result: list[dict] = []

        for g in groups_data:
            group_pages = []
            for path in g.get("pages", []):
                if path in all_paths and path not in covered_paths:
                    group_pages.append(next(p for p in pages if p["path"] == path))
                    covered_paths.add(path)

            if group_pages:
                result.append({
                    "category": g.get("name", "Unknown"),
                    "pages": group_pages,
                })

        # Add missing pages to "Other" group
        missing_paths = all_paths - covered_paths
        if missing_paths:
            other_pages = [p for p in pages if p["path"] in missing_paths]
            other_group = next((g for g in result if g["category"] == "Other"), None)
            if other_group:
                other_group["pages"].extend(other_pages)
            else:
                result.append({
                    "category": "Other",
                    "pages": other_pages,
                })

        # Keep "Other" at the end, otherwise preserve LLM-returned order
        other = [g for g in result if g["category"] == "Other"]
        non_other = [g for g in result if g["category"] != "Other"]
        result = non_other + other
        logger.info(f"[categorize_pages] produced {len(result)} groups, covering {len(covered_paths | missing_paths)} pages")
        return result

    def _ensure_other_last(self, groups: list[dict]) -> list[dict]:
        """Move 'Other' group to the end if present. Otherwise return as-is."""
        other = [g for g in groups if g["category"] == "Other"]
        non_other = [g for g in groups if g["category"] != "Other"]
        return non_other + other

    async def order_categories_by_complexity(self, groups: list[dict]) -> list[dict]:
        """Reorder categories from beginner-friendly to advanced.

        Both the order of categories AND the order of pages within each category
        are reordered by topic complexity. The "Other" category stays at the end.
        Falls back to the original order on parse/LLM failure.
        """
        if len(groups) <= 1:
            return groups

        groups_text = json.dumps(
            {
                "groups": [
                    {
                        "name": g["category"],
                        "pages": [
                            {"path": p["path"], "title": p["title"]}
                            for p in g["pages"]
                        ],
                    }
                    for g in groups
                ]
            },
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""You are a documentation expert. Reorder the groups below from beginner-friendly to advanced.

Input JSON:
{groups_text}

Return ONLY a JSON object in this exact format:
{{
  "category_order": ["Group Name 1", "Group Name 2", ...],
  "page_orders": {{
    "Group Name 1": ["/path1", "/path2"],
    ...
  }}
}}

Rules:
- "category_order" must include ALL group names, with beginner-friendly topics first and advanced topics last.
- "page_orders" must include ALL page paths for each group, ordered from simple to complex within that group.
- The "Other" group, if present, must always be LAST in "category_order".
- Do NOT rename groups or pages; only change the order.
- Use the exact group names and paths from the input."""

        try:
            logger.info(f"[order_categories_by_complexity] groups={len(groups)}")
            raw = await self._invoke_crawl_llm(prompt)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

            data = json.loads(cleaned)
            category_order = data.get("category_order", [])
            page_orders = data.get("page_orders", {})

            # Validation
            original_names = {g["category"] for g in groups}
            if set(category_order) != original_names:
                logger.warning(
                    f"Category order mismatch: expected {original_names}, got {set(category_order)}. Falling back."
                )
                return self._ensure_other_last(groups)

            # Validate page orders
            for g in groups:
                cat_name = g["category"]
                ordered_paths = set(page_orders.get(cat_name, []))
                original_paths = {p["path"] for p in g["pages"]}
                if ordered_paths != original_paths:
                    logger.warning(
                        f"Page order mismatch for '{cat_name}': expected {original_paths}, got {ordered_paths}. Falling back."
                    )
                    return self._ensure_other_last(groups)

            # Rebuild result in requested order
            name_to_pages = {g["category"]: g["pages"] for g in groups}

            result = []
            for cat_name in category_order:
                ordered_paths = list(page_orders.get(cat_name, []))
                # Reorder pages within group
                path_to_page = {p["path"]: p for p in name_to_pages[cat_name]}
                ordered_pages = [path_to_page[p] for p in ordered_paths]
                result.append({
                    "category": cat_name,
                    "pages": ordered_pages,
                })

            logger.info(
                f"[order_categories_by_complexity] reordered {len(result)} groups"
            )
            return result

        except Exception as e:
            logger.warning(f"order_categories_by_complexity failed: {e}. Falling back.")
            return self._ensure_other_last(groups)

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

    async def translate_all_page_titles(self, pages: list[dict]) -> dict[str, str]:
        """Translate all page titles to Chinese in batches.

        Returns {{path: zh_title}} mapping. Failures in individual batches
        are logged but do not block other batches.
        """
        batch_size = 35
        results: dict[str, str] = {}
        total_batches = (len(pages) + batch_size - 1) // batch_size

        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]
            batch_num = i // batch_size + 1
            try:
                batch_result = await self.translate_page_titles(batch)
                results.update(batch_result)
                logger.info(f"[translate_all_page_titles] batch {batch_num}/{total_batches} done, translated {len(batch_result)} titles")
            except Exception as e:
                logger.warning(f"[translate_all_page_titles] batch {batch_num}/{total_batches} failed: {e}")

        logger.info(f"[translate_all_page_titles] total translated {len(results)}/{len(pages)} titles")
        return results

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
