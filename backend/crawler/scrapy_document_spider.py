"""
Standalone Scrapy spider for document crawling.
Extracted from scrapy_web_crawler.py to improve code organization.
"""

import sys
import time
from collections.abc import Generator
from typing import Any
from urllib.parse import urldefrag, urljoin, urlparse

try:
    import scrapy
    from bs4 import BeautifulSoup
    from markdownify import markdownify
    from scrapy import signals
    from scrapy.crawler import CrawlerProcess
    from scrapy.http import Response
except ImportError as e:
    print(f"Missing required packages: {e}")
    sys.exit(1)


class DocumentSpider(scrapy.Spider):
    """Advanced document spider with content extraction"""

    name = "document_spider"

    def __init__(self, start_url: str, max_depth: int = 3, max_pages: int = 50, delay: float = 1.0, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = [start_url]
        self.allowed_domains = [urlparse(start_url).netloc]
        self.max_depth = int(max_depth)
        self.max_pages = int(max_pages)
        self.delay = float(delay)
        self.results = []
        self.pages_crawled = 0
        self.start_time = time.time()

        # Custom settings
        self.custom_settings = {
            "DOWNLOAD_DELAY": self.delay,
            "RANDOMIZE_DOWNLOAD_DELAY": True,
            "ROBOTSTXT_OBEY": True,
            "CONCURRENT_REQUESTS": 1,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 1,
            "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_START_DELAY": self.delay,
            "AUTOTHROTTLE_MAX_DELAY": self.delay * 3,
            "AUTOTHROTTLE_TARGET_CONCURRENCY": 1.0,
            "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        crawler.signals.connect(spider.spider_closed, signal=signals.spider_closed)
        return spider

    def spider_closed(self, spider):
        spider.logger.info(f"Spider closed. Crawled {len(self.results)} pages")

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

    def _extract_content(self, response: Response) -> tuple[str, str, list[str]]:
        """Extract title, content and links from response"""
        try:
            soup = BeautifulSoup(response.text, "lxml")

            # Extract title
            title_tag = soup.find("title")
            title = title_tag.get_text(strip=True) if title_tag else ""

            # Remove unwanted elements
            for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
                tag.decompose()

            # Find main content area
            main_content = soup.find("main") or soup.find("article") or soup.find("div", class_="content") or soup

            # Convert to markdown
            markdown_content = markdownify(str(main_content), heading_style="ATX")

            # Extract links
            links = []
            for link in response.css("a::attr(href)").getall():
                if link and not link.startswith("#"):
                    absolute_url = urljoin(response.url, link)
                    if self._is_same_domain(response.url, absolute_url):
                        clean_url = self._clean_url(absolute_url)
                        if clean_url not in links:
                            links.append(clean_url)

            return title, markdown_content, links

        except Exception as e:
            self.logger.error(f"Content extraction failed for {response.url}: {e}")
            return "", "", []

    def parse(self, response: Response) -> Generator[Any, None, None]:
        """Parse response and extract content"""
        if self.pages_crawled >= self.max_pages:
            return

        self.pages_crawled += 1
        current_depth = response.meta.get("depth", 0)
        crawl_time = time.time() - self.start_time

        try:
            title, content, links = self._extract_content(response)

            # Store result
            result = {
                "url": response.url,
                "title": title,
                "content": content,
                "links": links,
                "success": True,
                "error": None,
                "depth": current_depth,
                "status_code": response.status,
                "content_length": len(content),
                "crawl_time": crawl_time,
            }
            self.results.append(result)

            # Follow links if not at max depth
            if current_depth < self.max_depth and self.pages_crawled < self.max_pages:
                for link in links[:10]:  # Limit links per page
                    yield response.follow(link, callback=self.parse, meta={"depth": current_depth + 1})

        except Exception as e:
            self.logger.error(f"Parse error for {response.url}: {e}")
            result = {
                "url": response.url,
                "title": "",
                "content": "",
                "links": [],
                "success": False,
                "error": str(e),
                "depth": current_depth,
                "status_code": response.status,
                "content_length": 0,
                "crawl_time": crawl_time,
            }
            self.results.append(result)

    def errback(self, failure):
        """Handle request failures"""
        self.logger.error(f"Request failed: {failure}")
        crawl_time = time.time() - self.start_time
        result = {
            "url": failure.request.url,
            "title": "",
            "content": "",
            "links": [],
            "success": False,
            "error": str(failure.value),
            "depth": failure.request.meta.get("depth", 0),
            "status_code": 0,
            "content_length": 0,
            "crawl_time": crawl_time,
        }
        self.results.append(result)


def main():

    try:
        # Configure process
        process = CrawlerProcess(
            {
                "USER_AGENT": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "DOWNLOAD_DELAY": 1.0,
                "ROBOTSTXT_OBEY": True,
                "CONCURRENT_REQUESTS": 1,
                "LOG_LEVEL": "INFO",
                "FEEDS": {"output.json": {"format": "json"}},
            }
        )

        # Create and run spider
        process.crawl(
            DocumentSpider,
            start_url="https://docs.crawl4ai.com/core/page-interaction/",
            max_depth=3,
            max_pages=50,
            delay=1.0,
        )

        process.start()  # This blocks until finished

        # Results are automatically saved via FEEDS setting
        # The output file should contain the crawled data

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
