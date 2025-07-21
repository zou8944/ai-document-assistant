# Pydantic AI Context Engineering Template

A comprehensive template for building production-grade AI agents using Pydantic AI with context engineering best practices, tools integration, structured outputs, and comprehensive testing patterns.

## 🚀 Quick Start - Copy Template

**Get started in 2 minutes:**

```bash
# Clone the context engineering repository
git clone https://github.com/coleam00/Context-Engineering-Intro.git
cd Context-Engineering-Intro/use-cases/pydantic-ai

# 1. Copy this template to your new project
python copy_template.py /path/to/my-agent-project

# 2. Navigate to your project
cd /path/to/my-agent-project

# 3. Fill out PRPs/INITIAL.md with the agent you want to create

# 4. Start building with the PRP workflow
# Edit PRPs/INITIAL.md with your requirements, then:
/generate-pydantic-ai-prp PRPs/INITIAL.md
/execute-pydantic-ai-prp PRPs/generated_prp.md
```

If you are not using Claude Code, you can simply tell your AI coding assistant to use the generate-pydantic-ai-prp and execute-pydantic-ai-prp slash commands in .claude/commands as prompts.

## 📖 What is This Template?

This template provides everything you need to build sophisticated Pydantic AI agents using proven context engineering workflows. It combines:

- **Pydantic AI Best Practices**: Type-safe agents with tools, structured outputs, and dependency injection
- **Context Engineering Workflows**: Proven PRP (Problem Requirements Planning) methodology
- **Production Patterns**: Security, testing, monitoring, and deployment-ready code
- **Working Examples**: Complete agent implementations you can learn from and extend

## 🎯 PRP Framework Workflow

This template uses a 3-step context engineering workflow for building AI agents:

### 1. **Define Requirements** (`PRPs/INITIAL.md`)
Start by clearly defining what your agent needs to do:
```markdown
# Customer Support Agent - Initial Requirements

## Overview
Build an intelligent customer support agent that can handle inquiries, 
access customer data, and escalate issues appropriately.

## Core Requirements
- Multi-turn conversations with context and memory
- Customer authentication and account access
- Account balance and transaction queries
- Payment processing and refund handling
...
```

### 2. **Generate Implementation Plan** 
```bash
/generate-pydantic-ai-prp PRPs/INITIAL.md
```
This creates a comprehensive Problem Requirements Planning document that includes:
- Pydantic AI technology research and best practices
- Agent architecture design with tools and dependencies
- Implementation roadmap with validation loops
- Security patterns and production considerations

### 3. **Execute Implementation**
```bash
/execute-pydantic-ai-prp PRPs/your_agent.md
```
This implements the complete agent based on the PRP, including:
- Agent creation with proper model provider configuration
- Tool integration with error handling and validation
- Structured output models with Pydantic validation
- Comprehensive testing with TestModel and FunctionModel
- Security patterns and production deployment setup

## 📂 Template Structure

```
pydantic-ai/
├── CLAUDE.md                           # Pydantic AI global development rules
├── copy_template.py                    # Template deployment script
├── .claude/commands/
│   ├── generate-pydantic-ai-prp.md     # PRP generation for agents
│   └── execute-pydantic-ai-prp.md      # PRP execution for agents
├── PRPs/
│   ├── templates/
│   │   └── prp_pydantic_ai_base.md     # Base PRP template for agents
│   └── INITIAL.md                      # Example agent requirements
├── examples/
│   ├── basic_chat_agent/               # Simple conversational agent
│   │   ├── agent.py                    # Agent with memory and context
│   │   └── README.md                   # Usage guide
│   ├── tool_enabled_agent/             # Agent with external tools
│   │   ├── agent.py                    # Web search + calculator tools
│   │   └── requirements.txt            # Dependencies
│   └── testing_examples/               # Comprehensive testing patterns
│       ├── test_agent_patterns.py      # TestModel, FunctionModel examples
│       └── pytest.ini                  # Test configuration
└── README.md                           # This file
```

## 🤖 Agent Examples Included

### 1. Main Agent Reference (`examples/main_agent_reference/`)
**The canonical reference implementation** showing proper Pydantic AI patterns:
- Environment-based configuration with `settings.py` and `providers.py`
- Clean separation of concerns between email and research agents
- Tool integration with external APIs (Gmail, Brave Search)
- Production-ready error handling and logging

**Key Files:**
- `settings.py`: Environment configuration with pydantic-settings
- `providers.py`: Model provider abstraction with `get_llm_model()`
- `research_agent.py`: Multi-tool agent with web search and email integration
- `email_agent.py`: Specialized agent for Gmail draft creation

### 2. Basic Chat Agent (`examples/basic_chat_agent/`)
A simple conversational agent demonstrating core patterns:
- **Environment-based model configuration** (follows main_agent_reference)
- **String output by default** (no `result_type` unless needed)
- System prompts (static and dynamic)
- Conversation memory with dependency injection

**Key Features:**
- Simple string responses (not structured output)
- Settings-based configuration pattern
- Conversation context tracking
- Clean, minimal implementation

### 3. Tool-Enabled Agent (`examples/tool_enabled_agent/`)
An agent with tool integration capabilities:
- **Environment-based configuration** (follows main_agent_reference)
- **String output by default** (no unnecessary structure)
- Web search and calculation tools
- Error handling and retry mechanisms

**Key Features:**
- `@agent.tool` decorator patterns
- RunContext for dependency injection
- Tool error handling and recovery
- Simple string responses from tools

### 4. Structured Output Agent (`examples/structured_output_agent/`)
**NEW**: Shows when to use `result_type` for data validation:
- **Environment-based configuration** (follows main_agent_reference)
- **Structured output with Pydantic validation** (when specifically needed)
- Data analysis with statistical tools
- Professional report generation

**Key Features:**
- Demonstrates proper use of `result_type`
- Pydantic validation for business reports
- Data analysis tools with numerical statistics
- Clear documentation on when to use structured vs string output

### 5. Testing Examples (`examples/testing_examples/`)
Comprehensive testing patterns for Pydantic AI agents:
- TestModel for rapid development validation
- FunctionModel for custom behavior testing
- Agent.override() for test isolation
- Pytest fixtures and async testing

**Key Features:**
- Unit testing without API costs
- Mock dependency injection
- Tool validation and error scenario testing
- Integration testing patterns

## 🛠️ Core Pydantic AI Patterns

### Environment-Based Configuration (from main_agent_reference)
```python
# settings.py - Environment configuration
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    llm_provider: str = Field(default="openai")
    llm_api_key: str = Field(...)
    llm_model: str = Field(default="gpt-4")
    llm_base_url: str = Field(default="https://api.openai.com/v1")
    
    class Config:
        env_file = ".env"

# providers.py - Model provider abstraction
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.models.openai import OpenAIModel

def get_llm_model() -> OpenAIModel:
    settings = Settings()
    provider = OpenAIProvider(
        base_url=settings.llm_base_url,
        api_key=settings.llm_api_key
    )
    return OpenAIModel(settings.llm_model, provider=provider)
```

### Simple Agent (String Output - Default)
```python
from pydantic_ai import Agent, RunContext
from dataclasses import dataclass

@dataclass
class AgentDependencies:
    """Dependencies for agent execution"""
    api_key: str
    session_id: str = None

# Simple agent - no result_type, defaults to string
agent = Agent(
    get_llm_model(),  # Environment-based configuration
    deps_type=AgentDependencies,
    system_prompt="You are a helpful assistant..."
)
```

### Structured Output Agent (When Validation Needed)
```python
from pydantic import BaseModel, Field

class AnalysisReport(BaseModel):
    """Use result_type ONLY when you need validation"""
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    insights: list[str] = Field(min_items=1)

# Structured agent - result_type specified for validation
structured_agent = Agent(
    get_llm_model(),
    deps_type=AgentDependencies,
    result_type=AnalysisReport,  # Only when structure is required
    system_prompt="You are a data analyst..."
)
```

### Tool Integration
```python
@agent.tool
async def example_tool(
    ctx: RunContext[AgentDependencies], 
    query: str
) -> str:
    """Tool with proper error handling - returns string."""
    try:
        result = await external_api_call(ctx.deps.api_key, query)
        return f"API result: {result}"
    except Exception as e:
        logger.error(f"Tool error: {e}")
        return f"Tool temporarily unavailable: {str(e)}"
```

### Testing with TestModel
```python
from pydantic_ai.models.test import TestModel

def test_simple_agent():
    """Test simple agent with string output."""
    test_model = TestModel()
    with agent.override(model=test_model):
        result = agent.run_sync("Test message")
        assert isinstance(result.data, str)  # String output

def test_structured_agent():
    """Test structured agent with validation."""
    test_model = TestModel(
        custom_output_text='{"summary": "Test", "confidence": 0.8, "insights": ["insight1"]}'
    )
    with structured_agent.override(model=test_model):
        result = structured_agent.run_sync("Analyze this data")
        assert isinstance(result.data, AnalysisReport)  # Validated object
        assert 0.0 <= result.data.confidence <= 1.0
```

## 🎯 When to Use String vs Structured Output

### Use String Output (Default) ✅
**Most agents should use string output** - don't specify `result_type`:

```python
# ✅ Simple chat agent
chat_agent = Agent(get_llm_model(), system_prompt="You are helpful...")

# ✅ Tool-enabled agent  
tool_agent = Agent(get_llm_model(), tools=[search_tool], system_prompt="...")

# Result: agent.run() returns string
result = agent.run_sync("Hello")
print(result.data)  # "Hello! How can I help you today?"
```

**When to use string output:**
- Conversational agents
- Creative writing
- Flexible responses
- Human-readable output
- Simple tool responses

### Use Structured Output (Specific Cases) 🎯
**Only use `result_type` when you need validation:**

```python
# ✅ Data analysis requiring validation
analysis_agent = Agent(
    get_llm_model(), 
    result_type=AnalysisReport,  # Pydantic model with validation
    system_prompt="You are a data analyst..."
)

# Result: agent.run() returns validated Pydantic object
result = analysis_agent.run_sync("Analyze sales data")
print(result.data.confidence)  # 0.85 (validated 0.0-1.0)
```

**When to use structured output:**
- Data validation required
- API integrations needing specific schemas
- Business reports with consistent formatting
- Downstream processing requiring type safety
- Database insertion with validated fields

### Key Rule 📏
**Start with string output. Only add `result_type` when you specifically need validation or structure.**

## 🔒 Security Best Practices

This template includes production-ready security patterns:

### API Key Management
```bash
# Environment variables (never commit to code)
export LLM_API_KEY="your-api-key-here"
export LLM_MODEL="gpt-4"
export LLM_BASE_URL="https://api.openai.com/v1"

# Or use .env file (git-ignored)
echo "LLM_API_KEY=your-api-key-here" > .env
echo "LLM_MODEL=gpt-4" >> .env
```

### Input Validation
```python
from pydantic import BaseModel, Field

class ToolInput(BaseModel):
    query: str = Field(max_length=1000, description="Search query")
    max_results: int = Field(ge=1, le=10, default=5)
```

### Error Handling
```python
@agent.tool
async def secure_tool(ctx: RunContext[Deps], input_data: str) -> str:
    try:
        # Validate and sanitize input
        cleaned_input = sanitize_input(input_data)
        result = await process_safely(cleaned_input)
        return result
    except Exception as e:
        # Log error without exposing sensitive data
        logger.error(f"Tool error: {type(e).__name__}")
        return "An error occurred. Please try again."
```

## 🧪 Testing Your Agents

### Development Testing (Fast, No API Costs)
```python
from pydantic_ai.models.test import TestModel

# Test with TestModel for rapid iteration
test_model = TestModel()
with agent.override(model=test_model):
    result = agent.run_sync("Test input")
    print(result.data)
```

### Custom Behavior Testing
```python
from pydantic_ai.models.test import FunctionModel

def custom_response(messages, tools):
    """Custom function to control agent responses."""
    return '{"response": "Custom test response", "confidence": 0.9}'

function_model = FunctionModel(function=custom_response)
with agent.override(model=function_model):
    result = agent.run_sync("Test input")
```

### Integration Testing
```python
# Test with real models (use sparingly due to costs)
@pytest.mark.integration
async def test_agent_integration():
    result = await agent.run("Real test message")
    assert result.data.confidence > 0.5
```

## 🚀 Deployment Patterns

### Environment Configuration
```python
# settings.py - Production configuration
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # LLM Configuration
    llm_api_key: str
    llm_model: str = "gpt-4"
    llm_base_url: str = "https://api.openai.com/v1"
    
    # Production settings
    app_env: str = "production"
    log_level: str = "INFO"
    retries: int = 3
    
    class Config:
        env_file = ".env"

# agent.py - Use environment settings
agent = Agent(
    get_llm_model(),  # From providers.py
    retries=settings.retries,
    system_prompt="Production agent..."
)
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

## 🎓 Learning Path

### 1. Start with Examples
- Run `examples/basic_chat_agent/agent.py` to see a simple agent
- Explore `examples/tool_enabled_agent/` for tool integration
- Study `examples/testing_examples/` for testing patterns

### 2. Use the PRP Workflow
- Edit `PRPs/INITIAL.md` with your agent requirements
- Generate a PRP: `/generate-pydantic-ai-prp PRPs/INITIAL.md`
- Execute the PRP: `/execute-pydantic-ai-prp PRPs/generated_file.md`

### 3. Build Your Own Agent
- Start with the basic chat agent pattern
- Add tools for external capabilities
- Implement structured outputs for your use case
- Add comprehensive testing and error handling

### 4. Production Deployment
- Implement security patterns from `CLAUDE.md`
- Add monitoring and logging
- Set up CI/CD with automated testing
- Deploy with proper scaling and availability

## 🤝 Common Gotchas & Solutions

Based on extensive Pydantic AI research, here are common issues and solutions:

### Async/Sync Patterns
```python
# ❌ Don't mix sync and async inconsistently
def bad_tool(ctx):
    return asyncio.run(some_async_function())  # Anti-pattern

# ✅ Be consistent with async patterns
@agent.tool
async def good_tool(ctx: RunContext[Deps]) -> str:
    result = await some_async_function()
    return result
```

### Model Token Limits
```python
# ✅ Handle different model capabilities
from pydantic_ai.models import FallbackModel

model = FallbackModel([
    "openai:gpt-4o",        # High capability, higher cost
    "openai:gpt-4o-mini",   # Fallback option
])
```

### Tool Error Handling
```python
# ✅ Implement proper retry and fallback
@agent.tool
async def resilient_tool(ctx: RunContext[Deps], query: str) -> str:
    for attempt in range(3):
        try:
            return await external_api_call(query)
        except TemporaryError:
            if attempt == 2:
                return "Service temporarily unavailable"
            await asyncio.sleep(2 ** attempt)
```

## 📚 Additional Resources

- **Official Pydantic AI Documentation**: https://ai.pydantic.dev/
- **Model Provider Guides**: https://ai.pydantic.dev/models/
- **Tool Integration Patterns**: https://ai.pydantic.dev/tools/
- **Testing Strategies**: https://ai.pydantic.dev/testing/
- **Context Engineering Methodology**: See main repository README

## 🆘 Support & Contributing

- **Issues**: Report problems with the template or examples
- **Improvements**: Contribute additional examples or patterns
- **Questions**: Ask about Pydantic AI integration or context engineering

This template is part of the larger Context Engineering framework. See the main repository for more context engineering templates and methodologies.

---

**Ready to build production-grade AI agents?** Start with `python copy_template.py my-agent-project` and follow the PRP workflow! 🚀