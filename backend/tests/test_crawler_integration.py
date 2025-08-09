import pytest

from config import Config
from crawler.web_crawler import create_web_crawler, CrawlResult


class TestCrawlerIntegration:

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_website_crawl(self):
        """Test real website crawling with httpbin.org"""
        print("Starting crawl...")

        # Use reliable test website with limited pages
        config = Config(crawler_max_pages=3)
        instance = create_web_crawler(config)

        # 使用可靠的测试网站
        results = await instance.crawl_domain("https://httpbin.org")

        print(f"Crawl results: {len(results)} pages")
        for result in results:
            print(f"- {result.url}: {'✓' if result.success else '✗'} ({len(result.content)} chars)")

        # Validate results
        assert isinstance(results, list), "Results should be a list"
        assert len(results) > 0, "Should crawl at least one page"
        
        # Check that we got the main page
        main_page = next((r for r in results if r.url.startswith("https://httpbin.org")), None)
        assert main_page is not None, "Should crawl the main httpbin.org page"
        assert isinstance(main_page, CrawlResult), "Results should be CrawlResult objects"
        
        # Validate CrawlResult structure
        for result in results:
            assert hasattr(result, 'url'), "Result should have url attribute"
            assert hasattr(result, 'title'), "Result should have title attribute"
            assert hasattr(result, 'content'), "Result should have content attribute"
            assert hasattr(result, 'links'), "Result should have links attribute"
            assert hasattr(result, 'success'), "Result should have success attribute"
            assert isinstance(result.success, bool), "Success should be boolean"
            
            if result.success:
                assert isinstance(result.content, str), "Content should be string when successful"
                assert isinstance(result.links, list), "Links should be list"
                # Content should be in markdown format (our new feature)
                assert len(result.content) > 0, "Successful crawls should have content"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_single_url_crawl(self):
        """Test crawling a single URL without following links"""
        config = Config(crawler_max_pages=1)
        instance = create_web_crawler(config)
        
        # Test single URL crawl
        result = await instance.crawl_single_url("https://httpbin.org/html")
        
        print(f"Single URL crawl: {result.url}: {'✓' if result.success else '✗'}")
        
        # Validate single result
        assert isinstance(result, CrawlResult), "Should return CrawlResult object"
        assert result.url == "https://httpbin.org/html", "URL should match"
        
        if result.success:
            assert len(result.content) > 0, "Should have extracted content"
            assert isinstance(result.links, list), "Should have links list"
            print(f"Content preview: {result.content[:100]}...")

    @pytest.mark.integration
    @pytest.mark.asyncio  
    async def test_progress_callback_integration(self):
        """Test that progress callbacks work correctly"""
        config = Config(crawler_max_pages=2)
        instance = create_web_crawler(config)
        
        progress_calls = []
        
        def progress_callback(url, current, total):
            progress_calls.append((url, current, total))
            print(f"Progress: {current}/{total} - {url}")
        
        # Crawl with progress callback
        results = await instance.crawl_domain("https://httpbin.org", progress_callback)
        
        # Validate progress was reported
        assert len(progress_calls) > 0, "Progress callback should be called"
        
        # Check progress call structure
        for call in progress_calls:
            url, current, total = call
            assert isinstance(url, str), "URL should be string"
            assert isinstance(current, int), "Current should be integer"
            assert isinstance(total, int), "Total should be integer"
            assert url.startswith("https://"), "URL should be valid"

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_domain_restriction_enforcement(self):
        """Test that domain restrictions are properly enforced"""
        config = Config(crawler_max_pages=5)
        instance = create_web_crawler(config)
        
        # Crawl a site that likely has external links
        results = await instance.crawl_domain("https://httpbin.org")
        
        # All results should be from the same domain
        for result in results:
            if result.success:
                assert "httpbin.org" in result.url, f"URL {result.url} should be from httpbin.org domain"

    @pytest.mark.integration
    def test_get_crawl_stats(self):
        """Test crawl statistics functionality"""
        config = Config()
        instance = create_web_crawler(config)
        
        # Create mock results for testing stats
        from crawler.web_crawler import CrawlResult
        mock_results = [
            CrawlResult("https://test.com/page1", "Page 1", "Content 1", [], True),
            CrawlResult("https://test.com/page2", "Page 2", "Content 2", [], True),
            CrawlResult("https://test.com/page3", "", "", [], False, "Error message")
        ]
        
        stats = instance.get_crawl_stats(mock_results)
        
        # Validate stats structure
        assert stats['total_pages'] == 3, "Should count all pages"
        assert stats['successful_pages'] == 2, "Should count successful pages"
        assert stats['failed_pages'] == 1, "Should count failed pages"
        assert stats['success_rate'] == 66.7, "Should calculate success rate"
        assert isinstance(stats['failed_urls'], list), "Should list failed URLs"

    def test_crawler_factory_function(self):
        """Test the create_web_crawler factory function"""
        # Test with config
        config = Config(crawler_max_depth=5, crawler_delay=2.0, crawler_max_pages=100)
        instance1 = create_web_crawler(config)
        
        assert instance1.max_depth == 5
        assert instance1.delay == 2.0 
        assert instance1.max_pages == 100
        
        # Test without config (defaults)
        instance2 = create_web_crawler()
        
        assert instance2.max_depth == 3
        assert instance2.delay == 1.0
        assert instance2.max_pages == 50
