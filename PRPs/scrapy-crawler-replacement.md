name: "Scrapy Crawler Replacement PRP - Context-Rich Implementation Guide"
description: |
  Replace crawl4ai-based crawler with Scrapy + BeautifulSoup + html2markdown stack
  to solve macOS compatibility issues while maintaining all existing functionality.

---

## Goal
Replace the existing crawl4ai-based web crawler implementation with a cross-platform compatible solution using Scrapy + BeautifulSoup + html2markdown stack. The new implementation must maintain identical API compatibility, preserve all domain restrictions, anti-detection measures, and progress reporting functionality while solving the macOS compatibility issues.

## Why  
- **Cross-Platform Compatibility**: crawl4ai has compatibility issues on macOS, preventing the application from working on all target platforms
- **Stability**: Scrapy is a mature, battle-tested framework with excellent cross-platform support
- **Performance**: Scrapy provides superior concurrent processing capabilities and built-in rate limiting
- **Maintenance**: Well-established libraries with active communities and regular updates
- **Integration**: Better integration with existing Python ecosystem and project dependencies

## What
Create a new crawler implementation that:
- Uses Scrapy as the main crawling framework for robustness and concurrency
- Integrates BeautifulSoup for intelligent HTML parsing and content extraction
- Uses html-to-markdown library for clean HTML to Markdown conversion
- Maintains 100% API compatibility with existing WebCrawler class
- Preserves all existing features: domain restrictions, anti-detection, progress callbacks
- Follows existing code patterns and error handling approaches

### Success Criteria
- [ ] All existing WebCrawler API methods work identically
- [ ] Cross-platform compatibility (Windows, macOS, Linux)  
- [ ] Same or better crawling performance and reliability
- [ ] All existing tests pass without modification
- [ ] Proper domain restriction enforcement
- [ ] Anti-detection measures maintained
- [ ] Progress reporting functionality preserved

## All Needed Context

### Documentation & References
```yaml
- url: https://docs.scrapy.org/en/latest/
  why: Core Scrapy framework documentation for crawler setup and configuration
  
- url: https://docs.scrapy.org/en/latest/topics/settings.html
  why: Configuration settings for anti-detection headers and rate limiting
  
- url: https://www.crummy.com/software/BeautifulSoup/bs4/doc/
  why: BeautifulSoup HTML parsing for content extraction and cleaning
  
- url: https://github.com/Kludex/html-to-markdown
  why: Modern html-to-markdown library with full HTML5 support and type safety
  
- url: https://docs.scrapy.org/en/latest/topics/practices.html#avoiding-getting-banned
  why: Best practices for avoiding detection and implementing delays

- file: backend/crawler/web_crawler.py
  why: Current implementation patterns for API compatibility and domain restrictions
  
- file: backend/main.py:263
  why: Integration patterns for progress callbacks and error handling
  
- file: backend/tests/test_crawler_integration.py
  why: Test patterns that must be maintained
  
- file: backend/pyproject.toml
  why: Current dependency management and testing configuration
```

### Current Codebase Tree (crawler module)
```bash
backend/
├── crawler/
│   ├── __init__.py
│   └── web_crawler.py           # Current crawl4ai implementation (3KB)
├── tests/
│   └── test_crawler_integration.py  # Integration tests to maintain
└── pyproject.toml               # Dependencies to update
```

### Desired Codebase Tree with New Implementation
```bash  
backend/
├── crawler/
│   ├── __init__.py
│   ├── web_crawler.py           # New Scrapy-based implementation (4-5KB)
│   ├── scrapy_spider.py         # Custom Scrapy spider (2-3KB)
│   └── content_processor.py     # BeautifulSoup + html2markdown logic (2KB)
├── tests/
│   ├── test_crawler_integration.py  # Updated integration tests
│   ├── test_scrapy_spider.py        # New spider-specific tests
│   └── test_content_processor.py    # New content processing tests
└── pyproject.toml               # Updated with new dependencies
```

### Known Gotchas & Library Quirks
```python
# CRITICAL: Scrapy requires reactor management
# Only one reactor can run per process - must use CrawlerProcess or CrawlerRunner
from scrapy.crawler import CrawlerRunner
from twisted.internet import reactor

# GOTCHA: Scrapy is async by default, integration with asyncio requires special handling
# Use scrapy-playwright plugin or custom reactor integration

# CRITICAL: BeautifulSoup memory usage with large HTML documents
# Use lxml parser for better performance: BeautifulSoup(html, 'lxml')

# GOTCHA: html-to-markdown preserves structure but may need custom tag handling
# Configure markdownify options for clean output without excess whitespace

# CRITICAL: Domain checking must be implemented in Scrapy spider
# Use allowed_domains and custom URL filtering in spider middleware

# GOTCHA: Progress callbacks need thread-safe communication
# Use Scrapy signals system for progress reporting to main thread

# CRITICAL: Anti-detection headers must be set at Scrapy settings level
# Custom User-Agent rotation and header configuration in settings.py
```

## Implementation Blueprint

### Data Models and Structure  
```python
# Maintain exact compatibility with existing CrawlResult dataclass
@dataclass
class CrawlResult:
    """Structure for crawl results - MUST maintain exact compatibility"""
    url: str
    title: str  
    content: str    # Markdown format from html-to-markdown
    links: list[str]
    success: bool
    error: Optional[str] = None

# New internal models for Scrapy integration
@dataclass
class SpiderResult:
    """Internal result from Scrapy spider"""
    url: str
    html: str
    title: str
    status_code: int
    links: list[str]
```

### List of Tasks (Implementation Order)

```yaml
Task 1 - Update Dependencies:
  MODIFY pyproject.toml:
    - REMOVE crawl4ai==0.7.2 dependency
    - ADD scrapy>=2.11.0 for main framework
    - ADD beautifulsoup4>=4.12.0 for HTML parsing
    - ADD html-to-markdown>=1.0.0 for conversion
    - ADD lxml>=4.9.0 for fast XML/HTML parsing
    - UPDATE dev dependencies with scrapy testing tools

Task 2 - Create Content Processor:
  CREATE backend/crawler/content_processor.py:
    - IMPLEMENT clean_html_content() using BeautifulSoup
    - IMPLEMENT convert_to_markdown() using html-to-markdown
    - IMPLEMENT extract_links() with domain filtering
    - MIRROR error handling patterns from existing web_crawler.py
    - PRESERVE link extraction logic from lines 91-112

Task 3 - Create Scrapy Spider:
  CREATE backend/crawler/scrapy_spider.py:
    - IMPLEMENT DocumentSpider class extending scrapy.Spider
    - IMPLEMENT domain restriction logic (mirror _is_same_domain from line 65)
    - IMPLEMENT depth limiting and page count restrictions
    - ADD anti-detection headers and delays
    - IMPLEMENT progress reporting via Scrapy signals

Task 4 - Refactor Main WebCrawler Class:
  MODIFY backend/crawler/web_crawler.py:
    - PRESERVE exact method signatures and return types
    - REPLACE crawl4ai imports with new Scrapy integration
    - IMPLEMENT _run_scrapy_crawler() for reactor management
    - KEEP existing anti-detection headers (lines 54-61)
    - PRESERVE domain checking logic in _is_same_domain()
    - MAINTAIN progress callback integration
    - KEEP crawl_domain() and crawl_single_url() API identical

Task 5 - Create Unit Tests:
  CREATE backend/tests/test_content_processor.py:
    - TEST HTML cleaning removes scripts, ads, navigation
    - TEST markdown conversion preserves structure
    - TEST link extraction with domain filtering
    - MIRROR test patterns from existing test files

  CREATE backend/tests/test_scrapy_spider.py:
    - TEST spider configuration and settings
    - TEST domain restriction enforcement  
    - TEST depth and page count limits
    - TEST progress signal emission

Task 6 - Update Integration Tests:
  MODIFY backend/tests/test_crawler_integration.py:
    - ENSURE existing tests pass without modification
    - ADD platform-specific compatibility tests
    - PRESERVE test patterns and assertions
    - TEST against same httpbin.org endpoint

Task 7 - Update Main Integration:
  VERIFY backend/main.py integration:
    - CONFIRM create_web_crawler() factory function works
    - ENSURE progress_callback integration unchanged (line 259)
    - VERIFY crawl_website() method compatibility (line 238)
    - TEST error handling and response format consistency
```

### Per Task Pseudocode

```python
# Task 2: Content Processor Implementation
class ContentProcessor:
    def __init__(self, markdownify_options: Dict[str, Any]):
        # PATTERN: Configuration-driven initialization
        self.md_options = markdownify_options
        
    def clean_html_content(self, html: str) -> str:
        # PATTERN: Use lxml parser for performance (see existing patterns)
        soup = BeautifulSoup(html, 'lxml')
        
        # CRITICAL: Remove unwanted elements (ads, scripts, nav)
        for tag in soup(['script', 'style', 'nav', 'footer', 'aside']):
            tag.decompose()
            
        # GOTCHA: Preserve article/main content structure
        main_content = soup.find('main') or soup.find('article') or soup
        return str(main_content)
    
    def convert_to_markdown(self, cleaned_html: str) -> str:
        # CRITICAL: Use html-to-markdown with ATX heading style
        from markdownify import markdownify
        return markdownify(cleaned_html, 
                          heading_style="ATX",
                          **self.md_options)

# Task 3: Scrapy Spider Implementation  
class DocumentSpider(scrapy.Spider):
    name = 'document_spider'
    
    def __init__(self, start_urls, allowed_domains, max_depth=3, max_pages=50):
        # PATTERN: Mirror WebCrawler initialization parameters
        self.start_urls = start_urls
        self.allowed_domains = allowed_domains  
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.pages_crawled = 0
        
    def parse(self, response):
        # GOTCHA: Check depth and page limits before processing
        if self.pages_crawled >= self.max_pages:
            return
            
        # PATTERN: Extract content and links using content_processor
        processor = ContentProcessor({})
        cleaned_html = processor.clean_html_content(response.text)
        
        # CRITICAL: Emit progress signal for callback integration
        self.crawler.signals.send_catch_log(
            signal=signals.spider_progress,
            url=response.url,
            current=self.pages_crawled,
            total=self.pages_crawled + len(response.meta.get('pending_urls', []))
        )
        
        yield SpiderResult(
            url=response.url,
            html=cleaned_html,
            title=response.xpath('//title/text()').get(''),
            status_code=response.status,
            links=self._extract_valid_links(response)
        )

# Task 4: WebCrawler Integration
class WebCrawler:
    async def crawl_domain(self, start_url: str, progress_callback=None):
        # PATTERN: Preserve exact method signature and behavior
        base_domain = urlparse(start_url).netloc
        
        # CRITICAL: Use CrawlerRunner for async integration
        runner = CrawlerRunner(settings={
            'USER_AGENT': self.headers['User-Agent'],
            'DOWNLOAD_DELAY': self.delay,
            'RANDOMIZE_DOWNLOAD_DELAY': 0.5,
            'CONCURRENT_REQUESTS': 1,  # Conservative for anti-detection
        })
        
        # GOTCHA: Collect results from spider via item pipeline
        results = []
        def collect_result(item):
            results.append(item)
            
        runner.crawl(DocumentSpider, 
                    start_urls=[start_url],
                    allowed_domains=[base_domain],
                    result_callback=collect_result,
                    progress_callback=progress_callback)
        
        # PATTERN: Convert SpiderResult to CrawlResult for API compatibility
        return [self._convert_to_crawl_result(r) for r in results]
```

### Integration Points
```yaml
DEPENDENCIES:
  - remove: "crawl4ai==0.7.2"
  - add: "scrapy>=2.11.0" 
  - add: "beautifulsoup4>=4.12.0"
  - add: "html-to-markdown>=1.0.0"
  - add: "lxml>=4.9.0"

CONFIGURATION:
  - preserve: All existing WebCrawler configuration parameters
  - maintain: Anti-detection headers and delay settings
  - add: Scrapy-specific settings for user-agent rotation

API_COMPATIBILITY:
  - preserve: All public method signatures in WebCrawler class
  - maintain: CrawlResult dataclass structure
  - keep: Progress callback function signature and behavior
```

## Validation Loop

### Level 1: Syntax & Style  
```bash
# Run these FIRST - fix any errors before proceeding
ruff check backend/crawler/ --fix
mypy backend/crawler/
ruff check backend/tests/ --fix

# Expected: No errors. If errors, READ the error message and fix systematically.
```

### Level 2: Unit Tests
```bash
# Test individual components
uv run pytest backend/tests/test_content_processor.py -v
uv run pytest backend/tests/test_scrapy_spider.py -v

# Expected: All tests pass. If failing, debug step by step.
```

### Level 3: Integration Tests
```bash
# Test full crawler integration
uv run pytest backend/tests/test_crawler_integration.py -v

# Expected: Existing test_real_website_crawl passes with same behavior
# If failing: Check logs, verify API compatibility, fix incrementally
```

### Level 4: Full System Test
```bash
# Test with the main backend service
cd backend
PYTHONPATH=. uv run python main.py

# In another terminal:
echo '{"command": "crawl_url", "url": "https://httpbin.org", "collection_name": "test"}' | python -c "import sys, json; print(json.dumps(json.loads(sys.stdin.read())))"

# Expected: Successful crawl with same response format as before
```

## Final Validation Checklist
- [ ] All existing tests pass: `uv run pytest backend/tests/ -v`
- [ ] No linting errors: `ruff check backend/`
- [ ] No type errors: `mypy backend/`
- [ ] Integration test successful: `pytest test_crawler_integration.py -v`
- [ ] Cross-platform compatibility verified on macOS
- [ ] Memory usage acceptable for large site crawls
- [ ] Progress callbacks work correctly
- [ ] Domain restrictions enforced properly
- [ ] Anti-detection measures effective
- [ ] Markdown output quality preserved

---

## Anti-Patterns to Avoid
- ❌ Don't change existing API method signatures or return types
- ❌ Don't skip domain restriction validation - security critical
- ❌ Don't ignore Scrapy reactor management - will cause crashes
- ❌ Don't use synchronous operations in async contexts
- ❌ Don't overcomplicate BeautifulSoup selectors - keep it readable
- ❌ Don't skip progress callback testing - frontend depends on it
- ❌ Don't hardcode Scrapy settings - make them configurable
- ❌ Don't ignore memory cleanup - Scrapy can leak resources
- ❌ Don't change error message formats - maintain consistency

## Expected Challenges & Solutions
1. **Reactor Integration**: Use CrawlerRunner with proper async/await patterns
2. **Progress Reporting**: Leverage Scrapy signals for thread-safe callbacks  
3. **Memory Management**: Implement proper resource cleanup and limits
4. **Cross-Platform Testing**: Verify on multiple OS environments
5. **Performance Tuning**: Balance crawl speed with anti-detection measures

---

## PRP Quality Score: 8/10

**Confidence Level for One-Pass Implementation Success: 8/10**

**Strengths:**
- ✅ Comprehensive context with specific documentation URLs and code references
- ✅ Executable validation gates with clear bash commands and expected outcomes
- ✅ Maintains 100% API compatibility with existing WebCrawler implementation
- ✅ References existing patterns from multiple files with specific line numbers
- ✅ Clear 7-task implementation path with detailed pseudocode
- ✅ Addresses core macOS compatibility problem directly
- ✅ Includes external research on 2024 best practices
- ✅ Multiple validation levels from unit tests to full system integration

**Risk Factors:**
- ⚠️ Scrapy reactor management complexity (mitigated with detailed examples)
- ⚠️ Async/await integration between Scrapy and existing asyncio code
- ⚠️ Thread safety for progress callbacks (addressed with Scrapy signals)

**Mitigation:** All risk factors have been identified with specific solutions provided in the gotchas section and pseudocode examples. The implementation path follows established patterns from the existing codebase, ensuring consistency and reducing integration complexity.