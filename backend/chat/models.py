from dataclasses import dataclass
from enum import Enum


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
    START_ANSWER = "start_answer"


@dataclass
class SSEEvent:
    type: SSEEventType
    data: dict
