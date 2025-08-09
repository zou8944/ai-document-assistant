"""
Simple web crawler implementation using requests and BeautifulSoup.
Lightweight solution for basic document crawling with domain restrictions.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from markdownify import markdownify

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

    def __init__(self, max_depth: int = 3, delay: float = 1.0, max_pages: int = 50):
        """Initialize crawler with basic settings"""
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
        main_content = (
            soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup
        )

        # Convert to markdown
        markdown_content = markdownify(str(main_content), heading_style="ATX")

        # Extract links with improved relative path handling
        links = []
        a_tags = soup.find_all("a")

        for link in a_tags:
            if hasattr(link, "get"):
                href = link.get("href")
                if not href or not isinstance(href, str):
                    continue

                href = href.strip()
                if not href:
                    continue

                # Skip anchor links, javascript, mailto, etc.
                if any(
                    href.startswith(prefix)
                    for prefix in ["#", "javascript:", "mailto:", "tel:", "ftp:"]
                ):
                    continue

                try:
                    # Convert relative URLs to absolute URLs
                    absolute_url = urljoin(url, href)

                    # Validate URL and check if it's from the same domain
                    if self._is_valid_url(absolute_url) and self._is_same_domain(url, absolute_url):
                        clean_url = self._clean_url(absolute_url)
                        if (
                            clean_url
                            and clean_url not in links
                            and clean_url != self._clean_url(url)
                        ):
                            links.append(clean_url)

                except Exception as e:
                    logger.debug(f"Failed to process link {href}: {e}")
                    continue

        return title, markdown_content, links

    def _fetch_page(self, url: str) -> SimpleCrawlResult:
        """Fetch and process a single page"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            title, content, links = self._extract_content(response.text, url)

            return SimpleCrawlResult(
                url=url, title=title, content=content, links=links, success=True
            )

        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
            return SimpleCrawlResult(
                url=url, title="", content="", links=[], success=False, error=str(e)
            )

    def crawl_single_url(self, url: str) -> SimpleCrawlResult:
        """Crawl a single URL"""
        return self._fetch_page(url)

    def crawl_domain(
        self, start_url: str, progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[SimpleCrawlResult]:
        """Crawl multiple pages within the same domain with improved queue management"""
        results = []
        crawled_urls = set()
        to_crawl = [(start_url, 0)]  # (url, depth)
        failed_urls = set()  # Track failed URLs to avoid retrying

        # Normalize start URL
        start_url = self._clean_url(start_url)

        while to_crawl and len(results) < self.max_pages:
            url, depth = to_crawl.pop(0)

            # Skip if already processed or too deep
            if url in crawled_urls or depth > self.max_depth or url in failed_urls:
                continue

            # Skip if not from the same domain
            if not self._is_same_domain(start_url, url):
                continue

            crawled_urls.add(url)

            # Progress callback
            if progress_callback:
                progress_callback(url, len(results), len(results) + len(to_crawl))

            # Fetch page
            result = self._fetch_page(url)
            results.append(result)

            # Handle failed requests
            if not result.success:
                failed_urls.add(url)
                logger.debug(f"Failed to crawl {url}: {result.error}")
                time.sleep(self.delay)
                continue

            # Add new links to crawl queue if not at max depth
            if depth < self.max_depth:
                new_links_added = 0
                for link in result.links:
                    # Skip if already processed or queued
                    if (
                        link not in crawled_urls
                        and link not in failed_urls
                        and not any(existing_url == link for existing_url, _ in to_crawl)
                        and self._is_same_domain(start_url, link)
                    ):
                        to_crawl.append((link, depth + 1))
                        new_links_added += 1

                        # Limit new links per page to avoid queue explosion
                        if new_links_added >= 10:
                            break

            # Rate limiting
            time.sleep(self.delay)

        logger.info(
            f"Crawled {len(results)} pages successfully ({len([r for r in results if r.success])} successful)"
        )
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


def create_simple_web_crawler(config: Any = None) -> SimpleWebCrawler:
    """Create and return a SimpleWebCrawler instance with specified configuration"""
    if config:
        return SimpleWebCrawler(
            max_depth=getattr(config, "crawler_max_depth", 3),
            delay=getattr(config, "crawler_delay", 1.0),
            max_pages=getattr(config, "crawler_max_pages", 50),
        )
    else:
        return SimpleWebCrawler(max_depth=3, delay=1.0, max_pages=50)


if __name__ == "__main__":

    def main():
        crawler = create_simple_web_crawler()
        results = crawler.crawl_domain("https://docs.crawl4ai.com/core/page-interaction/")
        for result in results:
            print(result.title)
            print(result.content)

    main()
