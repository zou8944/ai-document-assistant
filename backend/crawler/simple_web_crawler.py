"""
Simple web crawler implementation using requests and BeautifulSoup.
Lightweight solution for basic document crawling with domain restrictions.
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from markdownify import markdownify

from config import Config

logger = logging.getLogger(__name__)


@dataclass
class SimpleCrawlResult:
    """Simple crawl result structure"""

    url: str
    title: str
    content: str
    links: list[str]
    success: bool
    error: Optional[str] = None


class SimpleWebCrawler:
    """
    Simple web crawler using requests + BeautifulSoup.
    Fast and lightweight for basic document crawling needs.
    """

    def __init__(self, cache_dir: str, max_depth: int = 0, delay: float = 1.0, max_pages: int = 1000):
        """Initialize crawler with basic settings"""
        self.cache_dir = cache_dir
        self.max_depth = max_depth
        self.delay = max(delay, 1.0)
        self.max_pages = max_pages

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

        logger.info(
            f"Initialized SimpleWebCrawler with max_depth={max_depth}, delay={delay}s, max_pages={max_pages}"
        )

    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if URLs are from the same domain"""
        try:
            domain1 = urlparse(url1).netloc.lower().replace("www.", "")
            domain2 = urlparse(url2).netloc.lower().replace("www.", "")
            return domain1 == domain2
        except Exception:
            return False

    def _clean_url(self, url: str) -> str:
        """Clean URL by removing fragments"""
        url, _ = urldefrag(url)
        return url.rstrip("/")

    def _is_valid_url(self, url: str) -> bool:
        """Check if URL is valid"""
        try:
            parsed = urlparse(url)
            return bool(parsed.netloc and parsed.scheme in ("http", "https"))
        except Exception:
            return False

    def _extract_content(self, html: str, url: str) -> tuple[str, str, list[str]]:
        """Extract title, content and links from HTML"""
        soup = BeautifulSoup(html, "lxml")

        # Extract title
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else ""

        # Remove meta elements
        for tag in soup(["script", "style", "header", "footer"]):
            tag.decompose()

        # Find main content area
        main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup

        # Convert main content to markdown
        markdown_content = markdownify(str(main_content), heading_style="ATX")

        # Extract links with improved relative path handling
        links = []
        a_tags = soup.find_all("a")

        for link in a_tags:
            # type assertion
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
                if (clean_url and clean_url not in links and clean_url != self._clean_url(url)):
                    links.append(clean_url)

        return title, markdown_content, links

    def _fetch_page_with_cache(self, url: str, force_crawl: bool) -> SimpleCrawlResult:
        cache_file = self._parse_url_to_cache_file(url)

        html_content = ""
        if os.path.exists(cache_file) and not force_crawl:
            logger.info(f"Loading from cache: {cache_file}")
            with open(cache_file, encoding="utf-8") as f:
                html_content = f.read()
        else:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            html_content = response.text

            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                f.write(html_content)

        title, content, links = self._extract_content(html_content, url)
        return SimpleCrawlResult(url=url, title=title, content=content, links=links, success=True)

    def _parse_url_to_cache_file(self, url: str) -> str:
        parsed_url = urlparse(self._clean_url(url))
        url_domain = parsed_url.netloc.replace("www.", "")
        path = parsed_url.path.strip("/")
        if not path:
            path = "index.html"
        else:
            path = f"{path}.html"
        splites = path.split("/")
        return os.path.join(self.cache_dir, url_domain, *splites)

    def crawl_single_url(self, url: str, force_crawl: bool = False) -> SimpleCrawlResult:
        """Crawl a single URL"""
        return self._fetch_page_with_cache(url, force_crawl)

    def crawl_recursive(
        self,
        urls: list[str], exclude_urls: list[str] = [],
        recursive_prefix: str = "",
        max_depth: int = 1,
        force_crawl: bool = False,
        progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[SimpleCrawlResult]:
        """Crawl multiple pages within the same domain with improved queue management"""
        results = []
        to_crawl = [(url, 0) for url in urls]  # (url, depth)
        crawled_urls = set()
        failed_urls = set()

        while to_crawl and len(results) < self.max_pages:
            url, depth = to_crawl.pop(0)

            # Skip if already processed
            if url in crawled_urls or url in failed_urls:
                continue

            # Skip if exceed max depth
            if depth > max_depth:
                continue

            crawled_urls.add(url)

            # Progress callback
            logger.info(f"Crawling {url}, depth {depth}, crawled: {len(results)}, remaining: {len(to_crawl)}")
            if progress_callback:
                progress_callback(url, len(results), len(results) + len(to_crawl))

            # Fetch page
            result = self._fetch_page_with_cache(url, force_crawl)
            results.append(result)

            # Handle failed requests
            if not result.success:
                failed_urls.add(url)
                logger.warning(f"Failed to crawl {url}: {result.error}")
                time.sleep(self.delay)
                continue

            # Handle success requests.
            for link in result.links:
                # If the link is already crawled or failed, skip it
                if link in crawled_urls or link in failed_urls:
                    continue
                # If the link is in the exclude list, skip it
                if link in exclude_urls:
                    continue
                # If the link does not start with the recursive prefix, skip it
                if not link.startswith(recursive_prefix):
                    continue
                # If the link is already in the crawl queue, skip it
                if any(existing_url == link for existing_url, _ in to_crawl):
                    continue
                # Queue it
                to_crawl.append((link, depth + 1))

            # Rate limiting
            time.sleep(self.delay)

        logger.info(f"Crawled {len(results)} pages successfully ({len([r for r in results if r.success])} successful)")
        return results

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


def create_simple_web_crawler(config: Config) -> SimpleWebCrawler:
    """Create and return a SimpleWebCrawler instance with specified configuration"""
    return SimpleWebCrawler(
        cache_dir=config.crawler_cache_dir,
        max_depth=config.crawler_max_depth,
        max_pages=config.crawler_max_pages,
        delay=config.crawler_delay,
    )


if __name__ == "__main__":

    def main():
        crawler = create_simple_web_crawler(Config(crawler_max_pages=10))
        results = crawler.crawl_recursive(
            urls=["https://docs.crawl4ai.com/core/page-interaction/"],
            recursive_prefix="https://docs.crawl4ai.com/core/",
            max_depth=2,
            force_crawl=True,
        )
        for result in results:
            print("-----")
            print(result.url)
            print(result.title)
            print("success:", result.success)
            print("error:", result.error)
            print("Links:")
            # for link in result.links:
            #     print(link)

    main()

