import pytest

from config import Config
from crawler.web_crawler import create_web_crawler


class TestCrawlerIntegration:

    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_real_website_crawl(self):
        print("Starting crawl...")

        """测试真实网站爬取"""
        config = Config(crawler_max_pages=3)
        instance = create_web_crawler(config)

        # 使用可靠的测试网站
        results = await instance.crawl_domain("https://httpbin.org")

        print(results)

    def test_tt(self):
        print("就纯粹测试")
