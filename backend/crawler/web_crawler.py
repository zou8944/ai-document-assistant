"""
Web crawler implementation using Crawl4AI with anti-detection measures.
Following 2024 best practices for domain-restricted crawling and progress reporting.
"""

import asyncio
import logging
from typing import List, Dict, Any, Set, Optional, Callable
from urllib.parse import urlparse, urljoin, urldefrag
import re
from dataclasses import dataclass

try:
    from crawl4ai import AsyncWebCrawler
    from crawl4ai.extraction_strategy import LLMExtractionStrategy
except ImportError:
    logging.error("crawl4ai not installed. Install with: pip install crawl4ai")
    raise

logger = logging.getLogger(__name__)


@dataclass
class CrawlResult:
    """Structure for crawl results"""
    url: str
    title: str
    content: str
    links: List[str]
    success: bool
    error: Optional[str] = None


class WebCrawler:
    """
    Advanced web crawler with domain restrictions and anti-detection measures.
    Optimized for document collection with progress reporting.
    """
    
    def __init__(self, max_depth: int = 3, delay: float = 1.0, max_pages: int = 50):
        """
        Initialize web crawler with anti-detection configuration.
        
        Args:
            max_depth: Maximum crawling depth (default 3)
            delay: Delay between requests in seconds (minimum 1.0)
            max_pages: Maximum number of pages to crawl
        """
        self.max_depth = max_depth
        self.delay = max(delay, 1.0)  # Minimum 1 second delay
        self.max_pages = max_pages
        
        # CRITICAL: Anti-detection headers
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        logger.info(f"Initialized WebCrawler with max_depth={max_depth}, delay={delay}s, max_pages={max_pages}")
    
    def _is_same_domain(self, url1: str, url2: str) -> bool:
        """Check if two URLs belong to the same domain"""
        try:
            domain1 = urlparse(url1).netloc.lower()
            domain2 = urlparse(url2).netloc.lower()
            
            # Handle subdomains - consider www.example.com and example.com as same
            domain1 = domain1.replace('www.', '')
            domain2 = domain2.replace('www.', '')
            
            return domain1 == domain2
        except Exception as e:
            logger.warning(f"Error comparing domains for {url1} and {url2}: {e}")
            return False
    
    def _clean_url(self, url: str) -> str:
        """Clean URL by removing fragments and normalizing"""
        # Remove fragment (hash)
        url, _ = urldefrag(url)
        
        # Remove trailing slash for consistency
        if url.endswith('/') and url.count('/') > 2:
            url = url.rstrip('/')
        
        return url
    
    def _extract_links(self, content: str, base_url: str) -> List[str]:
        """Extract links from HTML content"""
        links = []
        
        # Simple regex for href attributes (more robust than BeautifulSoup dependency)
        href_pattern = r'href=["\']([^"\']+)["\']'
        matches = re.findall(href_pattern, content, re.IGNORECASE)
        
        for match in matches:
            try:
                # Convert relative URLs to absolute
                absolute_url = urljoin(base_url, match)
                cleaned_url = self._clean_url(absolute_url)
                
                # Basic filtering
                if (cleaned_url.startswith(('http://', 'https://')) and 
                    not any(ext in cleaned_url.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.css', '.js'])):
                    links.append(cleaned_url)
            except Exception:
                continue
        
        return list(set(links))  # Remove duplicates
    
    async def _crawl_single_page(self, url: str, crawler: AsyncWebCrawler) -> CrawlResult:
        """
        Crawl a single page and extract content.
        
        Args:
            url: URL to crawl
            crawler: AsyncWebCrawler instance
            
        Returns:
            CrawlResult with page content and extracted links
        """
        try:
            logger.info(f"Crawling: {url}")
            
            # Crawl the page
            result = await crawler.arun(url=url)
            
            if not result.success:
                return CrawlResult(
                    url=url,
                    title="",
                    content="",
                    links=[],
                    success=False,
                    error=f"Crawl failed: {result.error_message}"
                )
            
            # Extract links from the raw HTML
            links = self._extract_links(result.html, url)
            
            # Use markdown content if available, otherwise use cleaned HTML
            content = result.markdown if result.markdown else result.cleaned_html
            
            return CrawlResult(
                url=url,
                title=result.metadata.get('title', ''),
                content=content,
                links=links,
                success=True
            )
            
        except Exception as e:
            logger.error(f"Failed to crawl {url}: {e}")
            return CrawlResult(
                url=url,
                title="",
                content="",
                links=[],
                success=False,
                error=str(e)
            )
    
    async def crawl_domain(self, start_url: str, 
                          progress_callback: Optional[Callable[[str, int, int], None]] = None) -> List[CrawlResult]:
        """
        Crawl all pages within the same domain as start_url.
        
        Args:
            start_url: Starting URL
            progress_callback: Optional callback for progress updates (url, current, total)
            
        Returns:
            List of CrawlResult objects
        """
        # PATTERN: Domain restriction
        base_domain = urlparse(start_url).netloc
        logger.info(f"Starting domain crawl for: {base_domain}")
        
        visited: Set[str] = set()
        to_crawl: List[tuple] = [(start_url, 0)]  # (url, depth)
        results: List[CrawlResult] = []
        
        # Initialize crawler with anti-detection settings
        crawler = AsyncWebCrawler(
            headers=self.headers,
            delay=self.delay,
            max_depth=self.max_depth
        )
        
        try:
            while to_crawl and len(results) < self.max_pages:
                url, depth = to_crawl.pop(0)
                
                # Skip if already visited or too deep
                if url in visited or depth > self.max_depth:
                    continue
                
                # GOTCHA: Only same domain
                if not self._is_same_domain(start_url, url):
                    logger.debug(f"Skipping {url} - different domain")
                    continue
                
                visited.add(url)
                
                # Progress callback
                if progress_callback:
                    progress_callback(url, len(results), len(to_crawl) + len(results))
                
                # Crawl the page
                crawl_result = await self._crawl_single_page(url, crawler)
                results.append(crawl_result)
                
                # Add new links to crawl queue if successful and not at max depth
                if crawl_result.success and depth < self.max_depth:
                    for link in crawl_result.links:
                        if (link not in visited and 
                            self._is_same_domain(start_url, link) and
                            len(to_crawl) + len(visited) < self.max_pages * 2):  # Prevent queue explosion
                            to_crawl.append((link, depth + 1))
                
                # Rate limiting delay
                if self.delay > 0:
                    await asyncio.sleep(self.delay)
        
        finally:
            await crawler.close()
        
        successful_results = [r for r in results if r.success]
        logger.info(f"Crawling completed. Successfully crawled {len(successful_results)}/{len(results)} pages")
        
        return results
    
    async def crawl_single_url(self, url: str) -> CrawlResult:
        """
        Crawl a single URL without following links.
        
        Args:
            url: URL to crawl
            
        Returns:
            CrawlResult for the single page
        """
        logger.info(f"Crawling single URL: {url}")
        
        crawler = AsyncWebCrawler(
            headers=self.headers,
            delay=0  # No delay needed for single page
        )
        
        try:
            result = await self._crawl_single_page(url, crawler)
            return result
        finally:
            await crawler.close()
    
    def get_crawl_stats(self, results: List[CrawlResult]) -> Dict[str, Any]:
        """
        Get statistics about crawl results.
        
        Args:
            results: List of crawl results
            
        Returns:
            Dictionary with crawl statistics
        """
        if not results:
            return {"total_pages": 0, "successful_pages": 0, "failed_pages": 0}
        
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        total_content_length = sum(len(r.content) for r in successful)
        avg_content_length = total_content_length / len(successful) if successful else 0
        
        return {
            "total_pages": len(results),
            "successful_pages": len(successful),
            "failed_pages": len(failed),
            "total_content_chars": total_content_length,
            "average_content_length": round(avg_content_length, 2),
            "success_rate": round(len(successful) / len(results) * 100, 1) if results else 0,
            "failed_urls": [r.url for r in failed][:5]  # First 5 failed URLs
        }


# Convenience function for creating crawler instance
def create_web_crawler(max_depth: int = 3, delay: float = 1.0, max_pages: int = 50) -> WebCrawler:
    """Create and return a WebCrawler instance with specified configuration"""
    return WebCrawler(max_depth=max_depth, delay=delay, max_pages=max_pages)