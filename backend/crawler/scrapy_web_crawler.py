"""
Advanced Scrapy-based web crawler with sophisticated features.
Provides better handling of JavaScript, anti-bot measures, and complex sites.
"""

import json
import logging
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CrawlerConfig:
    """Configuration class for Scrapy web crawler"""

    max_depth: int = 3
    delay: float = 1.0
    max_pages: int = 50
    timeout: int = 300
    concurrent_requests: int = 1
    obey_robots_txt: bool = True
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __post_init__(self):
        """Validate configuration after initialization"""
        if self.max_depth < 0:
            raise ValueError("max_depth must be non-negative")
        if self.delay < 0:
            raise ValueError("delay must be non-negative")
        if self.max_pages <= 0:
            raise ValueError("max_pages must be positive")
        if self.timeout <= 0:
            raise ValueError("timeout must be positive")


@dataclass
class ScrapyCrawlResult:
    """Scrapy crawl result structure"""

    url: str
    title: str
    content: str
    links: list[str]
    success: bool
    error: Optional[str] = None
    depth: int = 0
    status_code: int = 200
    content_length: int = 0
    crawl_time: float = 0.0


class ScrapyWebCrawler:
    """
    Advanced web crawler using Scrapy in subprocess to avoid reactor conflicts.
    Better for complex sites with JavaScript and anti-bot measures.
    """

    def __init__(
        self, config: Optional[CrawlerConfig] = None, max_depth: int = 3, delay: float = 1.0, max_pages: int = 50
    ):
        """Initialize Scrapy crawler runner"""
        # Use config if provided, otherwise use individual parameters
        if config:
            self.config = config
        else:
            self.config = CrawlerConfig(max_depth=max_depth, delay=delay, max_pages=max_pages)

        # Quick access properties
        self.max_depth = self.config.max_depth
        self.delay = self.config.delay
        self.max_pages = self.config.max_pages

        # Advanced headers for better compatibility
        self.headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

        logger.info(f"Initialized ScrapyWebCrawler with config: {self.config}")

    def _create_spider_script(self) -> str:
        """Get path to standalone spider script"""
        return str(Path(__file__).parent / "scrapy_document_spider.py")

    def run_spider(
        self, start_url: str, progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[ScrapyCrawlResult]:
        """
        Run Scrapy spider in subprocess and return results.

        Args:
            start_url: URL to start crawling from
            progress_callback: Optional progress callback

        Returns:
            List of crawl results
        """
        # Create temporary file for results
        with tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False) as f:
            result_file = f.name

        process = None
        script_file = None

        try:
            # Get spider script path
            script_file = self._create_spider_script()

            # Run spider in subprocess
            cmd = [
                "python",
                script_file,
                "--start-url",
                start_url,
                "--max-depth",
                str(self.max_depth),
                "--max-pages",
                str(self.max_pages),
                "--delay",
                str(self.delay),
                "--output",
                result_file,
            ]

            logger.info(f"Running Scrapy spider: {' '.join(cmd)}")

            # Run with timeout
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            # Monitor progress if callback provided
            if progress_callback:
                self._monitor_progress(process, progress_callback)

            stdout, stderr = process.communicate(timeout=300)  # 5 minute timeout

            if process.returncode != 0:
                logger.error(f"Scrapy spider failed: {stderr}")
                return []

            # Read and convert results
            raw_results = self._read_results(result_file)
            return [self._convert_result(r) for r in raw_results]

        except subprocess.TimeoutExpired:
            logger.error("Scrapy spider timed out")
            if process:
                process.kill()
                process.wait()
            return []
        except Exception as e:
            logger.error(f"Error running Scrapy spider: {e}")
            return []
        finally:
            # Cleanup
            try:
                Path(result_file).unlink(missing_ok=True)
            except Exception:
                pass

    def crawl_single_url(self, url: str) -> ScrapyCrawlResult:
        """Crawl a single URL using Scrapy"""
        results = self.run_spider(url)
        return (
            results[0]
            if results
            else ScrapyCrawlResult(url=url, title="", content="", links=[], success=False, error="No results")
        )

    def crawl_domain(
        self, start_url: str, progress_callback: Optional[Callable[[str, int, int], None]] = None
    ) -> list[ScrapyCrawlResult]:
        """Crawl multiple pages within the same domain using Scrapy"""
        return self.run_spider(start_url, progress_callback)

    def _monitor_progress(self, process: subprocess.Popen, callback: Callable):
        """Monitor spider progress"""
        start_time = time.time()
        while process.poll() is None:
            elapsed = time.time() - start_time
            callback(f"Scrapy crawling... ({elapsed:.1f}s)", 1, 1)
            time.sleep(2.0)

    def _read_results(self, result_file: str) -> list[dict]:
        """Read results from file"""
        try:
            with open(result_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error reading results: {e}")
            return []

    def _convert_result(self, raw_result: dict) -> ScrapyCrawlResult:
        """Convert raw result dict to ScrapyCrawlResult"""
        return ScrapyCrawlResult(
            url=raw_result.get("url", ""),
            title=raw_result.get("title", ""),
            content=raw_result.get("content", ""),
            links=raw_result.get("links", []),
            success=raw_result.get("success", False),
            error=raw_result.get("error"),
            depth=raw_result.get("depth", 0),
            status_code=raw_result.get("status_code", 200),
            content_length=raw_result.get("content_length", 0),
            crawl_time=raw_result.get("crawl_time", 0.0),
        )

    def get_crawl_stats(self, results: list[ScrapyCrawlResult]) -> dict[str, Any]:
        """Get statistics about crawl results"""
        if not results:
            return {
                "total_pages": 0,
                "successful_pages": 0,
                "failed_pages": 0,
                "success_rate": 0.0,
                "total_content_chars": 0,
                "average_content_length": 0,
                "max_depth_reached": 0,
                "total_crawl_time": 0.0,
                "average_crawl_time": 0.0,
            }

        successful = [r for r in results if r.success]
        total_content_chars = sum(r.content_length for r in successful)
        total_crawl_time = max(r.crawl_time for r in results) if results else 0.0

        return {
            "total_pages": len(results),
            "successful_pages": len(successful),
            "failed_pages": len(results) - len(successful),
            "success_rate": round(len(successful) / len(results) * 100, 1),
            "total_content_chars": total_content_chars,
            "average_content_length": round(total_content_chars / len(successful), 1) if successful else 0,
            "max_depth_reached": max(r.depth for r in results) if results else 0,
            "total_crawl_time": round(total_crawl_time, 2),
            "average_crawl_time": round(total_crawl_time / len(results), 2) if results else 0.0,
            "unique_domains": len({r.url.split("/")[2] for r in successful if "/" in r.url}),
        }


def create_scrapy_web_crawler(config: Any = None) -> ScrapyWebCrawler:
    """Create and return a ScrapyWebCrawler instance with specified configuration"""
    if config is None:
        return ScrapyWebCrawler()

    # Handle different config types
    if isinstance(config, CrawlerConfig):
        return ScrapyWebCrawler(config=config)

    # Handle dict-like config
    if hasattr(config, "__getitem__") or hasattr(config, "__dict__"):
        crawler_config = CrawlerConfig(
            max_depth=getattr(config, "crawler_max_depth", None) or config.get("max_depth", 3),
            delay=getattr(config, "crawler_delay", None) or config.get("delay", 1.0),
            max_pages=getattr(config, "crawler_max_pages", None) or config.get("max_pages", 50),
            timeout=getattr(config, "crawler_timeout", None) or config.get("timeout", 300),
            user_agent=getattr(config, "user_agent", None) or config.get("user_agent", CrawlerConfig.user_agent),
        )
        return ScrapyWebCrawler(config=crawler_config)

    # Fallback for attribute-based config
    crawler_config = CrawlerConfig(
        max_depth=getattr(config, "crawler_max_depth", 3),
        delay=getattr(config, "crawler_delay", 1.0),
        max_pages=getattr(config, "crawler_max_pages", 50),
        timeout=getattr(config, "crawler_timeout", 300),
    )
    return ScrapyWebCrawler(config=crawler_config)


if __name__ == "__main__":

    def main():
        crawler = create_scrapy_web_crawler()
        result = crawler.crawl_single_url("https://httpbin.org/get")
        print(result)

    main()
