"""
Simple web crawler implementation using requests and BeautifulSoup.
Lightweight solution for basic document crawling with domain restrictions.
"""

import logging
import time
import xml.etree.ElementTree as ET
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

from models.config import AppConfig, KnowledgeBaseConfig

logger = logging.getLogger(__name__)

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


@dataclass
class SimpleCrawlResult:
    """Simple crawl result structure"""

    url: str
    title: str
    content: str
    html_content: str
    clean_html: str
    links: list[str]
    success: bool
    error: Optional[str] = None


class SimpleWebCrawler:
    """
    Simple web crawler using requests + BeautifulSoup.
    Fast and lightweight for basic document crawling needs.
    """

    def __init__(self):
        """Initialize crawler with basic settings"""
        self.delay = 1.0

        # Anti-detection headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
        }

        # Create session for connection reuse
        self.session = requests.Session()
        self.session.headers.update(self.headers)

        logger.info(f"Initialized SimpleWebCrawler with delay={self.delay}s")

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if URLs are from the same domain"""
        try:
            domain1 = urlparse(url1).netloc.lower().replace("www.", "")
            domain2 = urlparse(url2).netloc.lower().replace("www.", "")
            return domain1 == domain2
        except Exception:
            return False

    def _clean_url(self, url: str) -> str:
        """Normalize URL: remove fragment, query params and trailing slash."""
        url, _ = urldefrag(url)
        parsed = urlparse(url)
        # Strip query params for canonical form; preserve scheme/netloc/path only
        canonical = parsed._replace(query="", fragment="")
        return canonical.geturl().rstrip("/")

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ("http", "https"))
        except Exception:
            return False

    def _clean_html(self, html: str) -> str:
        """Remove navigation/layout elements from raw HTML for clean preview."""
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()
        return str(soup)

    def _extract_content(self, html: str, url: str) -> tuple[str, str, list[str]]:
        """Extract title, markdown content and links from HTML"""
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Remove navigation/layout elements (keep in sync with _clean_html)
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Find main content area
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup

        # Convert main content to markdown
        markdown_content = markdownify(str(main_content), heading_style="ATX")

        # Extract links with improved relative path handling
        links = []
        a_tags = soup.find_all("a")

        for link in a_tags:
            if not isinstance(link, Tag):
                continue

            href = link.get("href")
            if not href or not isinstance(href, str):
                continue

            href = href.strip()
            if not href:
                continue

            # Skip anchor links, javascript, mailto, etc.
            if any(href.startswith(prefix) for prefix in ["#", "javascript:", "mailto:", "tel:", "ftp:"]):
                continue

            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(url, href)

            # Validate URL and check if it's from the same domain
            if self._is_valid_url(absolute_url) and self._is_same_domain(url, absolute_url):
                clean_url = self._clean_url(absolute_url)
                if clean_url and clean_url not in links and clean_url != self._clean_url(url):
                    links.append(clean_url)

        return title, markdown_content, links

    def extract_links_from_html(self, html: str, base_url: str) -> list[str]:
        """Extract same-domain links from stored HTML (used for resuming interrupted crawls)."""
        _, _, links = self._extract_content(html, base_url)
        return links

    def _fetch_page(self, url: str) -> SimpleCrawlResult:
        """Fetch a page from the network and return its content."""
        response = self.session.get(url, timeout=30)
        response.raise_for_status()
        html_content = response.text
        clean_html = self._clean_html(html_content)
        title, content, links = self._extract_content(clean_html, url)
        return SimpleCrawlResult(
            url=url,
            title=title,
            content=content,
            html_content=html_content,
            clean_html=clean_html,
            links=links,
            success=True,
        )

    def _try_sitemap(self, base_url: str, recursive_prefix: str) -> list[str]:
        """Try to fetch sitemap.xml and return filtered URLs. Returns empty list on failure."""
        parsed = urlparse(base_url)
        sitemap_url = f"{parsed.scheme}://{parsed.netloc}/sitemap.xml"
        try:
            response = self.session.get(sitemap_url, timeout=10)
            response.raise_for_status()
            root = ET.fromstring(response.text)
            urls = []
            for loc in root.iter(f"{{{SITEMAP_NS}}}loc"):
                if not loc.text:
                    continue
                url = self._clean_url(loc.text.strip())
                if (
                    self._is_valid_url(url)
                    and (not recursive_prefix or url.startswith(recursive_prefix))
                ):
                    urls.append(url)
            logger.info(f"Found {len(urls)} URLs in sitemap.xml at {sitemap_url}")
            return urls
        except Exception as e:
            logger.info(f"sitemap.xml not available at {sitemap_url}: {e}")
            return []

    def crawl_single_url(self, url: str) -> SimpleCrawlResult:
        """Crawl a single URL"""
        return self._fetch_page(url)

    def crawl_recursive_stream(
        self,
        urls: list[str],
        recursive_prefix: str = "",
        skip_urls: Optional[set[str]] = None,
        progress_callback: Optional[Callable[[str, int, int], None]] = None,
    ) -> Iterator[SimpleCrawlResult]:
        """
        Crawl all pages within the same domain.
        First tries sitemap.xml for URL discovery; falls back to BFS via <a> tags.
        No depth limit — crawls every reachable page up to max_pages.

        Stream crawl results one-by-one so callers can persist progress immediately.
        skip_urls: URLs already stored in the database; skipped without fetching.
        """
        if skip_urls is None:
            skip_urls = set()

        crawled_urls: set[str] = set()
        failed_urls: set[str] = set()
        yielded = 0

        # URL discovery — prefer sitemap.xml, fall back to BFS seed
        sitemap_urls = self._try_sitemap(urls[0] if urls else recursive_prefix, recursive_prefix)
        if sitemap_urls:
            # Merge user-provided URLs (priority) with sitemap-discovered URLs
            merged = list(dict.fromkeys(list(urls) + sitemap_urls))
            to_crawl = [url for url in merged if url not in skip_urls]
            logger.info(f"Using sitemap.xml: {len(merged)} URLs found, {len(to_crawl)} after skip")
        else:
            to_crawl = list(urls)
            logger.info("No sitemap.xml found, starting BFS from provided URLs")

        while to_crawl:
            url = to_crawl.pop(0)

            if url in crawled_urls or url in failed_urls:
                continue

            crawled_urls.add(url)

            logger.info(f"Crawling {url} | done: {yielded} | queued: {len(to_crawl)}")
            if progress_callback:
                progress_callback(url, yielded, yielded + len(to_crawl))

            try:
                result = self._fetch_page(url)
            except Exception as e:
                failed_urls.add(url)
                result = SimpleCrawlResult(
                    url=url, title="", content="", html_content="", clean_html="",
                    links=[], success=False, error=str(e),
                )
                logger.warning(f"Failed to crawl {url}: {e}")
                yield result
                yielded += 1
                time.sleep(self.delay)
                continue

            yield result
            yielded += 1

            if not result.success:
                failed_urls.add(url)
                time.sleep(self.delay)
                continue

            # Discover new links for BFS
            for link in result.links:
                if link in crawled_urls or link in failed_urls or link in skip_urls:
                    continue
                if recursive_prefix and not link.startswith(recursive_prefix):
                    continue
                if any(queued == link for queued in to_crawl):
                    continue
                to_crawl.append(link)

            time.sleep(self.delay)

        logger.info(
            f"Crawl complete: {yielded} pages crawled in this run"
        )

    def get_crawl_stats(self, results: list[SimpleCrawlResult]) -> dict[str, Any]:
        """Get statistics about crawl results"""
        if not results:
            return {"total_pages": 0, "successful_pages": 0, "failed_pages": 0}

        successful = [r for r in results if r.success]

        return {
            "total_pages": len(results),
            "successful_pages": len(successful),
            "failed_pages": len(results) - len(successful),
            "success_rate": round(len(successful) / len(results) * 100, 1),
            "total_content_chars": sum(len(r.content) for r in successful),
        }


def create_simple_web_crawler(config: AppConfig) -> SimpleWebCrawler:
    return SimpleWebCrawler()


if __name__ == "__main__":

    def main():
        config = AppConfig(knowledge_base=KnowledgeBaseConfig())
        crawler = create_simple_web_crawler(config)
        results = crawler.crawl_recursive_stream(
            urls=["https://docs.crawl4ai.com/core/page-interaction/"],
            recursive_prefix="https://docs.crawl4ai.com/core/",
        )
        for result in results:
            print("-----")
            print(result.url)
            print(result.title)
            print("success:", result.success)
            print("error:", result.error)

    main()
