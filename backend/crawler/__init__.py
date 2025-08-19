"""
Web crawler package with multiple implementation options.
"""

# Import factory functions and types
from crawler.scrapy_web_crawler import (
    ScrapyCrawlResult,
    ScrapyWebCrawler,
    create_scrapy_web_crawler,
)

# Import specific crawler implementations
from crawler.simple_web_crawler import (
    SimpleCrawlResult,
    SimpleWebCrawler,
    create_simple_web_crawler,
)

__all__ = [
    # Simple crawler
    "SimpleWebCrawler",
    "SimpleCrawlResult",
    "create_simple_web_crawler",
    # Scrapy crawler
    "ScrapyWebCrawler",
    "ScrapyCrawlResult",
    "create_scrapy_web_crawler",
]
