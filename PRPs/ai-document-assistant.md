name: "AI Document Reading Assistant - Desktop Application"
description: |

## Purpose
Build a complete AI document reading assistant desktop application that allows users to upload local files/folders or provide website URLs as data sources, then ask questions about the content using RAG (Retrieval Augmented Generation).

## Core Principles
1. **Context is King**: Follow all patterns from CLAUDE.md and UI design guide
2. **Validation Loops**: Test each component before integrating
3. **Information Dense**: Use proven 2024 patterns for Electron+React+Python
4. **Progressive Success**: Start with basic functionality, then enhance
5. **Global rules**: Be sure to follow all rules in CLAUDE.md

---

## Goal
Build a complete desktop application that processes documents (local files/folders or websites) and provides intelligent question-answering capabilities through a modern, native-feeling macOS interface using Apple Liquid Glass design principles.

## Why
- **Business value**: Solve efficiency problems when reading large volumes of documentation
- **User impact**: Reduce time spent manually searching through documents, prevent missing critical information
- **Integration**: Self-contained desktop application requiring no external services
- **Problems solved**: Document information overload, manual search inefficiency, knowledge extraction from multiple sources

## What
A desktop application with the following user-visible behavior:
- Upload local files or entire folders for processing
- Enter website URLs for recursive scraping (same-domain only)
- Ask natural language questions about processed content
- Receive contextual answers with source attribution
- Modern macOS-native interface with glass morphism effects

### Success Criteria
- [ ] Successfully process local files (PDF, text, markdown, etc.)
- [ ] Successfully scrape websites with domain restrictions
- [ ] Provide accurate RAG-based answers with source citations
- [ ] Handle large document sets without memory issues
- [ ] Native-feeling macOS interface matching design guidelines
- [ ] Stable subprocess communication between frontend and backend

## All Needed Context

### Documentation & References
```yaml
# MUST READ - Include these in your context window
- url: https://python.langchain.com/docs/tutorials/rag/
  why: Official RAG tutorial with RecursiveCharacterTextSplitter patterns
  
- url: https://python.langchain.com/docs/integrations/vectorstores/qdrant/
  why: LangChain Qdrant integration documentation and patterns
  
- url: https://docs.crawl4ai.com/
  why: Official Crawl4AI documentation for web scraping implementation
  
- url: https://medium.com/geekculture/building-a-desktop-app-with-electron-create-react-app-and-python-e02bb1c47227
  why: Electron + React + Python architecture tutorial
  
- url: https://www.electronjs.org/docs/latest/tutorial/ipc
  why: Electron IPC documentation for process communication
  
- url: https://www.npmjs.com/package/python-shell
  why: Python-shell package for subprocess communication via JSON/stdio
  
- docfile: /Users/zouguodong/Code/Personal/context-engineering-intro/UI 设计指南.md
  why: Apple Liquid Glass UI design specifications for native macOS feel
  
- docfile: /Users/zouguodong/Code/Personal/context-engineering-intro/CLAUDE.md
  why: Project requirements, architecture decisions, and constraints
```

### Current Codebase tree
```bash
/Users/zouguodong/Code/Personal/context-engineering-intro/
├── CLAUDE.md                    # Project instructions and architecture
├── INITIAL.md                   # Feature requirements
├── UI 设计指南.md                # Design specifications
├── PRPs/
│   └── templates/
│       └── prp_base.md          # PRP template structure
├── examples/                    # Empty - will create examples here
└── use-cases/                   # Other project examples for reference
```

### Desired Codebase tree with files to be added and responsibility of file
```bash
/Users/zouguodong/Code/Personal/context-engineering-intro/
├── frontend/                    # Electron + React application
│   ├── package.json            # Frontend dependencies (electron, react, tailwind)
│   ├── src/
│   │   ├── main.ts             # Electron main process
│   │   ├── App.tsx             # Main React application
│   │   ├── components/         # React components following UI guide
│   │   │   ├── FileUpload.tsx  # File selection component
│   │   │   ├── URLInput.tsx    # Website URL input
│   │   │   ├── ChatInterface.tsx # Q&A interface
│   │   │   └── StatusIndicator.tsx # Processing status display
│   │   ├── services/
│   │   │   └── pythonBridge.ts # Python subprocess communication
│   │   └── styles/
│   │       └── globals.css     # Tailwind with custom glass morphism
│   └── public/
│       └── index.html          # Electron renderer entry point
├── backend/                    # Python service
│   ├── requirements.txt        # Python dependencies
│   ├── main.py                 # Entry point for frontend communication
│   ├── crawler/
│   │   ├── __init__.py
│   │   └── web_crawler.py      # Crawl4AI implementation
│   ├── data_processing/
│   │   ├── __init__.py
│   │   ├── file_processor.py   # Local file handling
│   │   └── text_splitter.py    # LangChain text splitting
│   ├── vector_store/
│   │   ├── __init__.py
│   │   └── qdrant_client.py    # Qdrant vector operations
│   ├── rag/
│   │   ├── __init__.py
│   │   ├── retrieval_chain.py  # RAG implementation
│   │   └── prompt_templates.py # LLM prompts
│   └── tests/                  # Python unit tests
├── docker-compose.yml          # Qdrant container configuration
└── examples/                   # Implementation examples
    ├── crawl_demo.py          # Crawl4AI usage example
    ├── rag_demo.py            # RAG chain example
    └── ipc_demo/              # Frontend-backend communication demo
        ├── electron_demo.js   # Electron IPC example
        └── python_demo.py     # Python stdio example
```

### Known Gotchas of our codebase & Library Quirks
```python
# CRITICAL: Crawl4AI requires proper user agent and rate limiting
# Example: Default requests get blocked, need stealth headers
crawler_config = {
    'headers': {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)'},
    'delay': 1.0  # Minimum 1 second between requests
}

# CRITICAL: LangChain RecursiveCharacterTextSplitter standard config
text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,      # Standard 2024 recommendation
    chunk_overlap=200,    # Standard overlap
    add_start_index=True  # Track source location
)

# CRITICAL: Qdrant requires both REST (6333) and gRPC (6334) ports
# Python client prefers gRPC when prefer_grpc=True
qdrant_client = QdrantClient(host="localhost", port=6334, prefer_grpc=True)

# CRITICAL: python-shell expects JSON communication via stdout/stdin
# Each message must be complete JSON on single line
import json
import sys
sys.stdout.write(json.dumps(response) + '\n')
sys.stdout.flush()

# CRITICAL: Electron vibrancy requires specific window options
const win = new BrowserWindow({
  vibrancy: 'under-window',  # macOS only
  transparent: true,
  titleBarStyle: 'hiddenInset'
})

# CRITICAL: Domain restriction for web crawling
# Only crawl same domain as initial URL
from urllib.parse import urlparse
base_domain = urlparse(initial_url).netloc
# Skip any URL not matching base_domain
```

## Implementation Blueprint

### Data models and structure

Create core data models ensuring type safety and consistency.
```python
# Pydantic models for data validation
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Union
from enum import Enum

class DataSource(BaseModel):
    type: Literal['file', 'folder', 'url']
    path: str
    processed: bool = False
    created_at: datetime = Field(default_factory=datetime.now)

class DocumentChunk(BaseModel):
    id: str
    content: str
    source: str
    start_index: int
    metadata: dict

class QueryRequest(BaseModel):
    question: str
    collection_name: str
    max_results: int = 5

class QueryResponse(BaseModel):
    answer: str
    sources: List[DocumentChunk]
    confidence: float
```

### List of tasks to be completed to fulfill the PRP in the order they should be completed

```yaml
Task 1:
CREATE docker-compose.yml:
  - SET UP Qdrant container with persistent storage
  - EXPOSE ports 6333 (REST) and 6334 (gRPC)
  - CONFIGURE volume mapping for data persistence

Task 2:
CREATE backend/requirements.txt:
  - ADD langchain, qdrant-client, crawl4ai, pydantic
  - SPECIFY exact versions for reproducibility
  - INCLUDE fastapi for potential HTTP endpoint alternative

Task 3:
CREATE backend/vector_store/qdrant_client.py:
  - IMPLEMENT QdrantClient wrapper with connection management
  - ADD collection creation and management methods
  - INCLUDE error handling for connection failures

Task 4:
CREATE backend/data_processing/text_splitter.py:
  - IMPLEMENT RecursiveCharacterTextSplitter with standard config
  - ADD document preprocessing and chunk creation
  - INCLUDE metadata preservation for source tracking

Task 5:
CREATE backend/crawler/web_crawler.py:
  - IMPLEMENT Crawl4AI with anti-detection measures
  - ADD domain restriction logic
  - INCLUDE progress reporting and error handling

Task 6:
CREATE backend/data_processing/file_processor.py:
  - IMPLEMENT local file reading (PDF, txt, md, docx)
  - ADD folder traversal with file type filtering
  - INCLUDE encoding detection and error handling

Task 7:
CREATE backend/rag/retrieval_chain.py:
  - IMPLEMENT LangChain RAG chain with Qdrant retriever
  - ADD custom prompt templates with source citation
  - INCLUDE response formatting and confidence scoring

Task 8:
CREATE backend/main.py:
  - IMPLEMENT JSON stdio communication protocol
  - ADD command routing (process_files, crawl_url, query)
  - INCLUDE logging and error reporting to frontend

Task 9:
CREATE frontend/package.json:
  - ADD electron, react, typescript, tailwindcss
  - INCLUDE python-shell for subprocess communication
  - CONFIGURE build scripts and development server

Task 10:
CREATE frontend/src/main.ts:
  - IMPLEMENT Electron main process with vibrancy support
  - ADD window management with proper macOS integration
  - INCLUDE python subprocess lifecycle management

Task 11:
CREATE frontend/src/services/pythonBridge.ts:
  - IMPLEMENT python-shell integration with JSON protocol
  - ADD async request/response handling
  - INCLUDE error handling and process monitoring

Task 12:
CREATE frontend/src/components following UI guidelines:
  - IMPLEMENT FileUpload.tsx with drag-and-drop
  - ADD URLInput.tsx with validation
  - CREATE ChatInterface.tsx with glass morphism styling
  - ADD StatusIndicator.tsx for processing feedback

Task 13:
CREATE frontend/src/App.tsx:
  - IMPLEMENT main application layout
  - ADD state management for data sources and queries
  - INCLUDE navigation between upload and chat interfaces

Task 14:
CREATE frontend/src/styles/globals.css:
  - IMPLEMENT Tailwind configuration with custom glass effects
  - ADD backdrop-blur and transparency utilities
  - INCLUDE macOS-native color schemes and typography

Task 15:
CREATE comprehensive test suite:
  - ADD backend unit tests for each module
  - IMPLEMENT integration tests for RAG pipeline
  - CREATE frontend component tests and E2E scenarios
```

### Per task pseudocode as needed added to each task

```python
# Task 3: Qdrant Client Implementation
class QdrantManager:
    def __init__(self, host="localhost", port=6334):
        # PATTERN: Use prefer_grpc for better performance
        self.client = QdrantClient(host=host, port=port, prefer_grpc=True)
    
    async def ensure_collection(self, name: str, vector_size: int):
        # GOTCHA: Check if collection exists before creating
        collections = await self.client.get_collections()
        if name not in [c.name for c in collections.collections]:
            # PATTERN: Use COSINE distance for text embeddings
            await self.client.create_collection(name, vectors_config=VectorParams(
                size=vector_size, distance=Distance.COSINE
            ))

# Task 5: Web Crawler Implementation  
class WebCrawler:
    def __init__(self):
        # CRITICAL: Anti-detection headers
        self.crawler = AsyncWebCrawler(
            headers={'User-Agent': 'Mozilla/5.0 (compatible; AI-DocAssistant/1.0)'},
            delay=1.0,  # Rate limiting
            max_depth=3  # Prevent infinite crawling
        )
    
    async def crawl_domain(self, start_url: str) -> List[str]:
        # PATTERN: Domain restriction
        base_domain = urlparse(start_url).netloc
        visited = set()
        to_crawl = [start_url]
        results = []
        
        while to_crawl:
            url = to_crawl.pop(0)
            if url in visited:
                continue
                
            # GOTCHA: Only same domain
            if urlparse(url).netloc != base_domain:
                continue
                
            result = await self.crawler.arun(url=url)
            results.append(result.markdown)
            visited.add(url)
            
            # Extract same-domain links for recursive crawling
            # ... link extraction logic

# Task 8: Main Python Communication
def main():
    while True:
        try:
            # PATTERN: Read JSON from stdin
            line = sys.stdin.readline().strip()
            if not line:
                break
                
            request = json.loads(line)
            command = request.get('command')
            
            if command == 'process_files':
                response = await process_files(request['paths'])
            elif command == 'crawl_url':
                response = await crawl_website(request['url'])
            elif command == 'query':
                response = await answer_question(request['question'])
            
            # CRITICAL: Flush stdout immediately
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()
            
        except Exception as e:
            # PATTERN: Error responses
            error_response = {'status': 'error', 'message': str(e)}
            sys.stdout.write(json.dumps(error_response) + '\n')
            sys.stdout.flush()

# Task 11: Frontend Python Bridge
class PythonBridge {
    private pythonProcess: PythonShell;
    
    constructor() {
        // PATTERN: Use python-shell with stdio mode
        this.pythonProcess = new PythonShell('backend/main.py', {
            mode: 'json',  // Automatic JSON parsing
            pythonPath: 'python3',
            pythonOptions: ['-u']  // Unbuffered output
        });
    }
    
    async sendCommand(command: string, data: any): Promise<any> {
        return new Promise((resolve, reject) => {
            // GOTCHA: Set up response handler before sending
            this.pythonProcess.once('message', (response) => {
                if (response.status === 'error') {
                    reject(new Error(response.message));
                } else {
                    resolve(response);
                }
            });
            
            // Send JSON command
            this.pythonProcess.send({ command, ...data });
        });
    }
}
```

### Integration Points
```yaml
DOCKER:
  - service: "qdrant container with persistent volumes"
  - ports: "6333:6333, 6334:6334"
  - command: "docker-compose up -d"
  
ELECTRON:
  - main_process: "src/main.ts manages python subprocess lifecycle"
  - renderer: "src/App.tsx communicates via pythonBridge service"
  - vibrancy: "Enable transparent window with backdrop blur effects"
  
PYTHON_SUBPROCESS:
  - protocol: "JSON messages via stdin/stdout"
  - commands: "process_files, crawl_url, query"
  - error_handling: "Structured error responses with status codes"
  
STYLING:
  - framework: "Tailwind CSS with custom glass morphism utilities"
  - theme: "macOS system colors and SF Pro font family"
  - effects: "backdrop-blur-xl, bg-white/80, shadow-2xl patterns"
```

## Validation Loop

### Level 1: Syntax & Style
```bash
# Backend validation
cd backend
uv run black . --check
uv run mypy .
uv run ruff check .

# Frontend validation  
cd frontend
npm run lint
npm run type-check
npm run build

# Expected: No errors. If errors, READ and fix before proceeding.
```

### Level 2: Unit Tests each new feature/file/function use existing test patterns
```python
# Backend tests - CREATE backend/tests/test_rag_chain.py
def test_document_processing():
    """Test document chunking and embedding"""
    processor = FileProcessor()
    chunks = processor.process_file("test.pdf")
    assert len(chunks) > 0
    assert all(chunk.content for chunk in chunks)

def test_qdrant_integration():
    """Test vector store operations"""
    manager = QdrantManager(":memory:")  # In-memory for testing
    await manager.ensure_collection("test", 384)
    
    # Test document indexing
    result = await manager.index_documents("test", test_chunks)
    assert result.status == "success"

def test_rag_retrieval():
    """Test question answering pipeline"""
    chain = RetrievalChain("test_collection")
    response = await chain.query("What is the main topic?")
    assert response.answer
    assert len(response.sources) > 0

# Frontend tests - CREATE frontend/src/tests/
def test_python_bridge():
    """Test subprocess communication"""
    bridge = new PythonBridge()
    response = await bridge.sendCommand('query', {
        question: 'test question'
    })
    expect(response.status).toBe('success')
```

```bash
# Run and iterate until passing:
cd backend && uv run pytest tests/ -v
cd frontend && npm test

# If failing: Read error, understand root cause, fix code, re-run
```

### Level 3: Integration Test
```bash
# Start Qdrant container
docker-compose up -d

# Start the Electron app in development mode
cd frontend
npm run dev

# Test workflow:
# 1. Upload a test document
# 2. Verify processing completes without errors  
# 3. Ask a question about the document
# 4. Verify response includes relevant answer and sources

# Expected: Complete document processing → successful question answering
# If error: Check Electron DevTools console and Python subprocess logs
```

## Final validation Checklist
- [ ] All backend tests pass: `cd backend && uv run pytest tests/ -v`
- [ ] All frontend tests pass: `cd frontend && npm test`
- [ ] No linting errors: `uv run ruff check .` and `npm run lint`
- [ ] No type errors: `uv run mypy .` and `npm run type-check`
- [ ] Manual test successful: Upload document → ask question → get answer with sources
- [ ] UI matches Apple Liquid Glass design specifications
- [ ] Web crawling respects domain restrictions
- [ ] Error cases display user-friendly messages
- [ ] Processing progress is clearly communicated to user
- [ ] Large files don't cause memory issues or crashes

---

## Anti-Patterns to Avoid
- ❌ Don't skip domain restriction in web crawler - security risk
- ❌ Don't block the UI thread during document processing - use async
- ❌ Don't ignore subprocess communication errors - handle gracefully  
- ❌ Don't hardcode file paths or URLs - make configurable
- ❌ Don't skip chunking for large documents - will exceed token limits
- ❌ Don't forget to flush stdout in Python - messages won't reach frontend
- ❌ Don't use sync functions in async context - will cause deadlocks
- ❌ Don't skip UI loading states - user experience suffers

## Quality Score: 9/10
This PRP provides comprehensive context including:
- Complete 2024 documentation URLs for all technologies
- Proven architecture patterns from recent tutorials  
- Detailed implementation blueprints with gotchas highlighted
- Executable validation commands for each development phase
- Anti-patterns section to avoid common pitfalls
- Progressive task breakdown for manageable implementation

The high confidence score reflects the extensive research into current best practices and the inclusion of all necessary context for one-pass implementation success.