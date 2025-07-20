## FEATURE:

Build a simple customer support chatbot using PydanticAI that can answer basic questions and escalate complex issues to human agents.

## EXAMPLES:

- Basic chat agent with conversation memory
- Tool-enabled agent with web search capabilities  
- Structured output agent for data validation
- Testing examples with TestModel and FunctionModel

## DOCUMENTATION:

- PydanticAI Official Documentation: https://ai.pydantic.dev/
- Agent Creation Guide: https://ai.pydantic.dev/agents/
- Tool Integration: https://ai.pydantic.dev/tools/
- Testing Patterns: https://ai.pydantic.dev/testing/
- Model Providers: https://ai.pydantic.dev/models/

## OTHER CONSIDERATIONS:

- Use environment variables for API key configuration instead of hardcoded model strings
- Keep agents simple - default to string output unless structured output is specifically needed
- Follow the main_agent_reference patterns for configuration and providers
- Always include comprehensive testing with TestModel for development