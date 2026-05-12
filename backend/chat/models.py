from dataclasses import dataclass
from enum import Enum
class QueryIntent(Enum):
    CHITCHAT = "chitchat"
    META = "meta"
    OFF_TOPIC = "off_topic"
    DIRECT_ANSWER = "direct_answer"
    LOCATE = "locate"
    RECOMMEND = "recommend"
    SUMMARIZE = "summarize"
    COMPARE = "compare"
    PROCEDURE = "procedure"
    SYNTHESIZE = "synthesize"
    ANALYZE = "analyze"


class ProcessingMode(Enum):
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"


@dataclass
class RouterResult:
    intent: QueryIntent
    confidence: float
    reason: str
    suggested_mode: ProcessingMode
    complexity_score: int
    rewritten_queries: list[str]
    requires_retrieval: bool = True
    core_keywords: list[str] | None = None
    semantic_expansions: list[str] | None = None
    implicit_aspects: list[str] | None = None


@dataclass
class RetrievedDocument:
    document_id: str
    document_name: str
    document_uri: str
    content: str
    relevance_score: float
    source_type: str
    chunk_index: int | None = None


@dataclass
class SearchResult:
    documents: list[RetrievedDocument]
    search_type: str
    total_found: int


@dataclass
class CollectionInfo:
    collection_id: str
    name: str
    description: str
    readme_content: str
    categories: list[dict]
    document_count: int
    total_tokens: int


@dataclass
class EvaluationResult:
    confidence_score: float
    missing_aspects: list[str]
    supplementary_queries: list[str]
    context_completeness: float = 0.0
    source_sufficiency: float = 0.0
    supplementary_strategy: str = "vector"


@dataclass
class AssembledContext:
    system_prompt: str
    messages: list[dict]
    context_documents: list[RetrievedDocument]
    collection_info: list[CollectionInfo]
    estimated_tokens: int
    mode: ProcessingMode


class SSEEventType(Enum):
    STATUS = "status"
    PROGRESS = "progress"
    INTENT = "intent"
    SEARCHING = "searching"
    SOURCES = "sources"
    THINKING = "thinking"
    CONTENT = "content"
    DONE = "done"
    ERROR = "error"
    # Agent protocol events
    AGENT_START = "agent_start"
    ITERATION_START = "iteration_start"
    AGENT_THINKING = "agent_thinking"
    THINKING_DONE = "thinking_done"
    TOOL_CALL = "tool_call"
    TOOL_PROGRESS = "tool_progress"
    TOOL_RESULT = "tool_result"
    COMPACT_TRIGGERED = "compact_triggered"
    FINAL_TEXT_PROMOTE = "final_text_promote"
    AGENT_HALTED = "agent_halted"


@dataclass
class SSEEvent:
    type: SSEEventType
    data: dict
