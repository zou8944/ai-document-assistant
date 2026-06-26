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

from rag.document_summarizer import DocumentSummarizer

logger = logging.getLogger(__name__)

# Overall timeout (seconds) for any single LLM call; prevents Ctrl+C from hanging
LLM_TIMEOUT = 300

# Max consecutive failures before aborting task
MAX_CONSECUTIVE_FAILURES = 3


class LLMConsecutiveFailureError(Exception):
    """Raised when LLM API calls fail consecutively."""
    pass


class LLMService:
    """Centralized service for all LLM-related operations"""

    def __init__(self, config):
        self.config = config

        # Defer initialization if API key is not configured (first launch)
        if not config.llm.crawl.api_key:
            logger.warning("Crawl API key not configured, LLMService will be unavailable until configured via settings UI")
            self.embeddings = None
            self.crawl_llm = None
            self.document_summarizer = None
            self.text_parser = StrOutputParser()
            self._consecutive_failures = 0
            return

        # Validate crawl provider (currently only openai is supported)
        self.config.llm.crawl.validate(supported_providers=["openai"])

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Initialize crawl-specific LLM
        crawl = self.config.llm.crawl
        self.crawl_llm = ChatOpenAI(
            model=crawl.model,
            temperature=0.1,
            api_key=crawl.api_key,
            base_url=crawl.base_url or None,
            max_tokens=self.config.llm.max_tokens,
        )
        logger.info("Using crawl model: %s", crawl.model)

        # Initialize specialized components
        self.document_summarizer = DocumentSummarizer(self.crawl_llm)

        # Initialize output parser for text generation
        self.text_parser = StrOutputParser()

        # Consecutive failure tracking for task abort
        self._consecutive_failures = 0

        logger.info("LLMService initialized successfully")

    def reset_failure_counter(self):
        """Reset consecutive failure counter. Call at task start."""
        self._consecutive_failures = 0

    def _on_success(self):
        """Reset failure counter on success."""
        self._consecutive_failures = 0

    def _on_failure(self, error: Exception):
        """Increment failure counter and raise if exceeded."""
        self._consecutive_failures += 1
        if self._consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            raise LLMConsecutiveFailureError(
                f"AI API 连续 {self._consecutive_failures} 次调用失败，中止任务"
            ) from error

    # ==================== Embedding Operations ====================

    async def embed_query(self, query: str) -> list[float]:
        logger.info("[LLM] embed_query start, model=%s, query_len=%d", self.embeddings.model, len(query))
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(self.embeddings.aembed_query(query), timeout=LLM_TIMEOUT)
            self._on_success()
            logger.info("[LLM] embed_query done, %.2fs", time.monotonic() - t0)
            return result
        except LLMConsecutiveFailureError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        logger.info("[LLM] embed_documents start, model=%s, count=%d", self.embeddings.model, len(texts))
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(self.embeddings.aembed_documents(texts), timeout=LLM_TIMEOUT)
            self._on_success()
            logger.info("[LLM] embed_documents done, %.2fs", time.monotonic() - t0)
            return result
        except LLMConsecutiveFailureError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    # ==================== Document Summarization ====================

    async def summarize_document(self, content: str) -> str:
        try:
            result = await self.document_summarizer.summarize_document_async(content, llm=self.crawl_llm)
            self._on_success()
            return result
        except LLMConsecutiveFailureError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    async def summarize_collection(self, document_summaries: list[str]) -> str:
        try:
            result = await self.document_summarizer.summarize_collection_async(document_summaries, llm=self.crawl_llm)
            self._on_success()
            return result
        except LLMConsecutiveFailureError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

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
    def _build_groups_text(groups: list[dict], max_per_group: int = 5, indent: int = 0) -> str:
        """Build compact group summary for prompts. Handles nested structures."""
        group_lines: list[str] = []
        prefix = "  " * indent
        for g in groups:
            cat = g["category"]
            group_pages = g.get("pages", [])
            children = g.get("children", [])
            sample = group_pages[:max_per_group]
            page_lines = "\n".join(f"{prefix}    - {p['path']}: {p['title']}" for p in sample)
            more = f"\n{prefix}    ... and {len(group_pages) - max_per_group} more pages" if len(group_pages) > max_per_group else ""
            child_text = ""
            if children:
                child_text = "\n" + LLMService._build_groups_text(children, max_per_group, indent + 1)
            group_lines.append(f"{prefix}- {cat} ({len(group_pages)} pages)\n{page_lines}{more}{child_text}")
        return "\n".join(group_lines)

    @staticmethod
    def _count_all_groups(groups: list[dict]) -> int:
        """Count total number of groups in nested structure."""
        count = 0
        for g in groups:
            count += 1
            count += LLMService._count_all_groups(g.get("children", []))
        return count

    async def generate_readme_content(self, groups: list[dict], language: str = "en", total_pages: int = 0) -> str:
        """Generate README markdown. For 'zh' generates Chinese, otherwise English.

        The number of representative pages per group scales with total document count and group count:
        - < 30 pages: list all pages per group
        - 30-100 pages: up to 20 per group
        - > 100 pages: up to 15 per group (further reduced if many groups)
        """
        num_groups = self._count_all_groups(groups)
        if total_pages < 30:
            max_per_group = total_pages  # effectively unlimited
        elif total_pages <= 100:
            max_per_group = 20
        else:
            # For large page counts, reduce per-group limit based on group count
            if num_groups > 20:
                max_per_group = 8
            elif num_groups > 10:
                max_per_group = 12
            else:
                max_per_group = 15

        groups_text = self._build_groups_text(groups, max_per_group=max_per_group)

        if language == "zh":
            prompt = f"""You are analyzing a documentation website. Given the grouped page data below,
generate a navigation guide README in Chinese. Respond with ONLY the Markdown content, no JSON wrapper.

The data is hierarchical — groups may have sub-groups. Use different heading levels to reflect the hierarchy:
- Top-level groups use ## headings
- Sub-groups use ### headings
- Sub-sub-groups use #### headings

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## 文档目录" section (at the TOP): list all groups as anchor links: [分类名](#分类名)
  - Use indentation to show hierarchy in the table of contents
  - Use the exact group name as the anchor (no slug conversion)
- "## 整体介绍" section (second): write 3-5 natural paragraphs describing:
  - What topics this documentation site covers overall
  - The intended audience and what they can learn
  - Guidance for different users (beginners, advanced users, developers) on where to start
  - A brief overview of each group's content and how groups relate to each other
  - Use doc:///path links to point to specific key pages
- Then list each group using the appropriate heading level based on its nesting depth
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

The data is hierarchical — groups may have sub-groups. Use different heading levels to reflect the hierarchy:
- Top-level groups use ## headings
- Sub-groups use ### headings
- Sub-sub-groups use #### headings

Rules:
- Start with an h1 title and a short overview paragraph in blockquote (>)
- "## Table of Contents" section (at the TOP): list all groups as anchor links: [Group Name](#Group Name)
  - Use indentation to show hierarchy in the table of contents
  - Use the exact group name as the anchor (no slug conversion)
- "## Overview" section (second): write 3-5 natural paragraphs describing:
  - What topics this documentation site covers overall
  - The intended audience and what they can learn
  - Guidance for different users (beginners, advanced users, developers) on where to start
  - A brief overview of each group's content and how groups relate to each other
  - Use doc:///path links to point to specific key pages
- Then list each group using the appropriate heading level based on its nesting depth
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

        Input pages must contain 'id', 'path', and 'title'.
        Returns groups in the format:
            [{"category": str, "pages": [{"id": str, "path": str, "title": str}, ...]}]
        Guarantees 100% coverage - all pages are assigned to a group.
        Raises exception on failure (no fallback).

        For large page counts (>80), uses batch processing with AI-assisted merging.
        """
        if len(pages) <= 80:
            return await self._categorize_pages_batch(pages)

        # Batch processing for large page counts
        batch_size = 80
        all_groups: list[dict] = []
        existing_categories: list[str] = []

        logger.info(f"[categorize_pages] Using batch processing for {len(pages)} pages (batch_size={batch_size})")

        for i in range(0, len(pages), batch_size):
            batch = pages[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (len(pages) + batch_size - 1) // batch_size
            logger.info(f"[categorize_pages] Processing batch {batch_num}/{total_batches} ({len(batch)} pages)")

            try:
                batch_groups = await self._categorize_pages_batch(batch, existing_categories)
                all_groups.extend(batch_groups)
                # Update existing categories for next batch
                existing_categories = list({g["category"] for g in all_groups})
            except Exception as e:
                logger.error(f"[categorize_pages] Batch {batch_num} failed: {e}")
                all_groups.append({
                    "category": "Other",
                    "pages": batch,
                })

        # Final AI merge: consolidate similar category names
        if len(all_groups) > 10:
            logger.info(f"[categorize_pages] Running final AI merge for {len(all_groups)} groups")
            result = await self._merge_categories_with_ai(all_groups)
        else:
            # Simple code merge for small group counts
            result = self._merge_categories_by_name(all_groups)

        logger.info(f"[categorize_pages] Batch processing complete: {len(result)} groups from {len(pages)} pages")
        return result

    def _merge_categories_by_name(self, all_groups: list[dict]) -> list[dict]:
        """Merge groups with same category name using code logic."""
        merged: dict[str, list[dict]] = {}
        for g in all_groups:
            cat = g["category"]
            if cat not in merged:
                merged[cat] = []
            merged[cat].extend(g["pages"])

        result = [{"category": cat, "pages": pgs} for cat, pgs in merged.items()]

        # Keep "Other" at the end
        other = [g for g in result if g["category"] == "Other"]
        non_other = [g for g in result if g["category"] != "Other"]
        return non_other + other

    async def _merge_categories_with_ai(self, all_groups: list[dict]) -> list[dict]:
        """Use AI to merge similar category names."""
        # Build summary of current groups
        groups_summary = []
        for i, g in enumerate(all_groups):
            groups_summary.append({
                "index": i,
                "name": g["category"],
                "count": len(g["pages"])
            })

        summary_text = json.dumps(groups_summary, ensure_ascii=False, indent=2)

        prompt = f"""You are consolidating documentation categories. The following groups were created by different batches and may have similar names that should be merged.

Current groups:
{summary_text}

Instructions:
1. Identify groups with similar or duplicate names (e.g., "API Reference" and "API Docs", "Getting Started" and "Introduction")
2. Create a mapping from old names to new merged names
3. Keep meaningful distinct categories separate
4. If a group named "Other" exists, keep it as-is

Return ONLY a JSON object mapping old category names to new merged names:
{{"Old Name 1": "New Name", "Old Name 2": "New Name", ...}}"""

        try:
            logger.info(f"[_merge_categories_with_ai] Merging {len(all_groups)} categories")
            raw = await self._invoke_crawl_llm(prompt, max_tokens=2000)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
                cleaned = cleaned.strip()

            name_mapping = json.loads(cleaned)
            logger.info(f"[_merge_categories_with_ai] Mapping: {name_mapping}")

            # Apply mapping
            merged: dict[str, list[dict]] = {}
            for g in all_groups:
                old_name = g["category"]
                new_name = name_mapping.get(old_name, old_name)
                if new_name not in merged:
                    merged[new_name] = []
                merged[new_name].extend(g["pages"])

        except Exception as e:
            logger.warning(f"[_merge_categories_with_ai] AI merge failed: {e}, falling back to code merge")
            return self._merge_categories_by_name(all_groups)

        result = [{"category": cat, "pages": pgs} for cat, pgs in merged.items()]
        # Keep "Other" at the end
        other = [g for g in result if g["category"] == "Other"]
        non_other = [g for g in result if g["category"] != "Other"]
        return non_other + other

    async def _categorize_pages_batch(self, pages: list[dict], existing_categories: list[str] | None = None) -> list[dict]:
        """Categorize a single batch of pages (max 80).

        Args:
            pages: List of page dicts with 'id', 'path', 'title'.
            existing_categories: If provided, AI should prefer these category names for consistency.
        """
        pages_text = "\n".join(f"- {p['id']}: {p['path']}: {p['title']}" for p in pages)

        existing_hint = ""
        if existing_categories:
            existing_hint = f"""
IMPORTANT: Previous batches have already created these categories. When a page fits one of these categories, use the EXACT same name:
{', '.join(existing_categories)}

You may also create new categories if needed, but prefer existing ones when appropriate."""

        prompt = f"""You are organizing documentation pages into logical topic groups.
Analyze the page paths and titles below, and group them by content/theme similarity.
{existing_hint}

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
      "page_ids": ["page_id_1", "page_id_2"]
    }}
  ]
}}"""
        logger.info(f"[_categorize_pages_batch] pages={len(pages)}, prompt_len={len(prompt)}")
        raw = await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)
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
        all_ids = {p["id"] for p in pages}
        covered_ids: set[str] = set()
        id_to_page = {p["id"]: p for p in pages}
        result: list[dict] = []

        for g in groups_data:
            group_pages = []
            for page_id in g.get("page_ids", []):
                if page_id in all_ids and page_id not in covered_ids:
                    group_pages.append(id_to_page[page_id])
                    covered_ids.add(page_id)

            if group_pages:
                result.append({
                    "category": g.get("name", "Unknown"),
                    "pages": group_pages,
                })

        # Add missing pages to "Other" group
        missing_ids = all_ids - covered_ids
        if missing_ids:
            other_pages = [p for p in pages if p["id"] in missing_ids]
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
        logger.info(f"[_categorize_pages_batch] produced {len(result)} groups, covering {len(covered_ids | missing_ids)} pages")
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
                        "page_ids": [p["id"] for p in g["pages"]],
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
    "Group Name 1": ["page_id_1", "page_id_2"],
    ...
  }}
}}

Rules:
- "category_order" must include ALL group names, with beginner-friendly topics first and advanced topics last.
- "page_orders" must include ALL page IDs for each group, ordered from simple to complex within that group.
- The "Other" group, if present, must always be LAST in "category_order".
- Do NOT rename groups or pages; only change the order.
- Use the exact group names and page IDs from the input."""

        try:
            logger.info(f"[order_categories_by_complexity] groups={len(groups)}")
            raw = await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)
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
                ordered_ids = set(page_orders.get(cat_name, []))
                original_ids = {p["id"] for p in g["pages"]}
                if ordered_ids != original_ids:
                    logger.warning(
                        f"Page order mismatch for '{cat_name}': expected {original_ids}, got {ordered_ids}. Falling back."
                    )
                    return self._ensure_other_last(groups)

            # Rebuild result in requested order
            name_to_pages = {g["category"]: g["pages"] for g in groups}

            result = []
            for cat_name in category_order:
                ordered_ids = list(page_orders.get(cat_name, []))
                # Reorder pages within group
                id_to_page = {p["id"]: p for p in name_to_pages[cat_name]}
                ordered_pages = [id_to_page[pid] for pid in ordered_ids]
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
        # Preprocess: replace hyphens with spaces so the LLM can translate URL segments
        preprocessed = [n.replace("-", " ") for n in group_names]
        names_text = "\n".join(f"- {n}" for n in preprocessed)
        prompt = f"""Translate the following group names into concise natural Chinese (2-6 characters each).
Respond with ONLY a JSON object mapping each name to Chinese.

Group names:
{names_text}

Format:
{{"group name": "分组中文名", ...}}"""
        logger.info(f"[translate_category_names] names={len(group_names)}")
        raw = await self._invoke_crawl_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            result = json.loads(cleaned)
            # Map preprocessed keys back to original names
            pre_to_orig = dict(zip(preprocessed, group_names))
            return {pre_to_orig.get(k, k): v for k, v in result.items()}
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse category name translation result: {raw}")
            return {}

    async def _translate_titles_batch(self, titles: list[str]) -> list[str]:
        """Translate a batch of titles. Returns translated array in same order."""
        titles_text = "\n".join(f"- {t}" for t in titles)
        prompt = f"""Translate the following page titles into natural Chinese.
Respond with ONLY a JSON array of Chinese translations in the same order.

Titles:
{titles_text}

Format:
["中文标题1", "中文标题2", ...]"""
        raw = await self._invoke_crawl_llm(prompt)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()
        try:
            result: list[str] = json.loads(cleaned)
            if not isinstance(result, list):
                raise ValueError("Expected array")
            return result
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Failed to parse title translation result: {raw}")
            return []

    async def translate_all_page_titles(self, pages: list[dict]) -> dict[str, str]:
        """Translate all page titles to Chinese.

        Deduplicates titles globally, translates in batches of 80,
        then maps back to paths. Returns {path: zh_title} mapping.
        """
        # Build title -> [paths] mapping for dedup
        title_to_paths: dict[str, list[str]] = {}
        for p in pages:
            title = p.get("title", "").strip()
            path = p["path"]
            if not title:
                continue
            title_to_paths.setdefault(title, []).append(path)

        unique_titles = list(title_to_paths.keys())
        batch_size = 80
        translated: dict[str, str] = {}
        total_batches = (len(unique_titles) + batch_size - 1) // batch_size

        for i in range(0, len(unique_titles), batch_size):
            batch = unique_titles[i:i + batch_size]
            batch_num = i // batch_size + 1
            try:
                batch_result = await self._translate_titles_batch(batch)
                if len(batch_result) == len(batch):
                    for en, zh in zip(batch, batch_result):
                        translated[en] = zh
                else:
                    logger.warning(f"[translate_all_page_titles] batch {batch_num} length mismatch: got {len(batch_result)}, expected {len(batch)}")
            except Exception as e:
                logger.warning(f"[translate_all_page_titles] batch {batch_num}/{total_batches} failed: {e}")

        # Map translated titles back to all paths
        result: dict[str, str] = {}
        for title, paths in title_to_paths.items():
            zh_title = translated.get(title)
            if zh_title:
                for path in paths:
                    result[path] = zh_title

        logger.info(f"[translate_all_page_titles] pages={len(pages)}, unique={len(unique_titles)}, translated={len(result)}")
        return result

    # ==================== Incremental Category Merge ====================

    async def merge_categories(
        self,
        existing_categories: list[dict],
        new_pages: list[dict],
    ) -> list[dict]:
        """Merge new pages into existing categories.

        existing_categories: [{"category": str, "pages": [{"path": str, "title": str}, ...]}]
        new_pages: [{"id": str, "path": str, "title": str}]
        Returns the same format as existing_categories.
        """
        existing_text = json.dumps(existing_categories, ensure_ascii=False, indent=2)
        new_text = json.dumps(
            [{"path": p["path"], "title": p["title"]} for p in new_pages],
            ensure_ascii=False, indent=2,
        )

        prompt = f"""You are a documentation categorization expert.

Existing categories:
{existing_text}

New documents to merge:
{new_text}

Instructions:
- If a new document fits an existing category, add it to that category
- If a new document doesn't fit any existing category, create a new category for it
- You may create multiple new categories if the new documents cover distinct topics
- Maintain the overall order from beginner-friendly to advanced
- Do NOT remove or rename existing categories unless necessary for clarity

Return ONLY a JSON array in this exact format (same as input categories format):
[
  {{"category": "Category Name", "pages": [{{"path": "/path", "title": "Title"}}, ...]}},
  ...
]"""

        logger.info(f"[merge_categories] existing={len(existing_categories)} cats, new={len(new_pages)} pages")
        raw = await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return self._ensure_other_last(result)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[merge_categories] parse failed: {e}, raw={raw[:300]}")

        # Fallback: just append new pages to a "New" category
        return existing_categories + [{"category": "New", "pages": [
            {"path": p["path"], "title": p["title"]} for p in new_pages
        ]}]

    async def optimize_categories(
        self,
        categories: list[dict],
        all_pages: list[dict],
    ) -> list[dict]:
        """Check category balance and optimize: merge small groups, split large ones."""
        categories_text = json.dumps(categories, ensure_ascii=False, indent=2)
        all_pages_text = json.dumps(
            [{"path": p["path"], "title": p["title"]} for p in all_pages],
            ensure_ascii=False, indent=2,
        )

        prompt = f"""You are a documentation categorization expert. Review the current category structure and optimize it.

Current categories:
{categories_text}

All documents (for reference):
{all_pages_text}

Optimization rules:
- Merge categories with fewer than 2 pages into the most related category
- Split categories with more than 20 pages into sub-topics
- Ensure every document appears in exactly one category
- Ensure category names are clear and descriptive
- Keep "Other" category last if it exists
- Maintain order from beginner-friendly to advanced

If no changes are needed, return the input unchanged.

Return ONLY a JSON array in this exact format:
[
  {{"category": "Category Name", "pages": [{{"path": "/path", "title": "Title"}}, ...]}},
  ...
]"""

        logger.info(f"[optimize_categories] input={len(categories)} categories, {len(all_pages)} pages")
        raw = await self._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            result = json.loads(cleaned)
            if isinstance(result, list):
                return self._ensure_other_last(result)
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"[optimize_categories] parse failed: {e}, raw={raw[:300]}")

        # Fallback: return original unchanged
        return categories

    # ==================== Direct LLM Access ====================

    async def _invoke_crawl_llm(self, prompt: str, **kwargs) -> str:
        logger.info("[LLM] _invoke_crawl_llm start, model=%s, prompt_len=%d", self.crawl_llm.model_name, len(prompt))
        t0 = time.monotonic()
        try:
            result = await asyncio.wait_for(
                self.crawl_llm.ainvoke(prompt, **kwargs), timeout=LLM_TIMEOUT
            )
            output = str(result.content) if hasattr(result, 'content') and result is not None else str(result)
            self._on_success()
            logger.info("[LLM] _invoke_crawl_llm done, %.2fs, output_len=%d", time.monotonic() - t0, len(output))
            return output
        except LLMConsecutiveFailureError:
            raise
        except Exception as e:
            self._on_failure(e)
            raise

    def close(self):
        logger.info("LLMService resources closed")
