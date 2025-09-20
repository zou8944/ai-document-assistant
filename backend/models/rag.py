
from dataclasses import dataclass
from enum import Enum


@dataclass
class CollectionSummary:
    name: str
    summary: str

class ChatMessageRoleEnum(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"

@dataclass
class HistoryItem:
    role: ChatMessageRoleEnum
    message: str

@dataclass
class DocChunk:
    doc_name: str
    collection_name: str
    content: str
