"""
LLM service for centralized AI model management and operations.
"""

import logging

from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from models.rag import CollectionSummary, DocChunk, HistoryItem
from rag.document_summarizer import DocumentSummarizer
from rag.intent_analyzer import IntentAnalyzer
from rag.prompt_templates import build_rag_prompt

logger = logging.getLogger(__name__)


class LLMService:
    """Centralized service for all LLM-related operations"""

    def __init__(self, config=None):
        from config import get_config

        self.config = config or get_config()

        # Initialize OpenAI components
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        # Initialize specialized components
        self.intent_analyzer = IntentAnalyzer(llm=self.llm)
        self.document_summarizer = DocumentSummarizer(self.llm)

        # Initialize output parser for text generation
        self.text_parser = StrOutputParser()

        logger.info("LLMService initialized successfully")

    # ==================== Embedding Operations ====================

    async def embed_query(self, query: str) -> list[float]:
        return await self.embeddings.aembed_query(query)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self.embeddings.aembed_documents(texts)

    # ==================== Intent Analysis ====================

    async def analyze_intent(self, user_message: str):
        return await self.intent_analyzer.analyze(user_message)

    # ==================== Document Summarization ====================

    def summarize_document(self, content: str) -> str:
        return self.document_summarizer.summarize_document(content)

    def summarize_collection(self, document_summaries: list[str]) -> str:
        return self.document_summarizer.summarize_collection(document_summaries)

    # ==================== RAG Chat Operations ====================

    def build_rag_prompt(
        self,
        collections: list[CollectionSummary],
        histories: list[HistoryItem],
        reference_chunks: list[DocChunk],
        user_query: str
    ) -> str:
        return build_rag_prompt(
            collections=collections,
            histories=histories,
            reference_chunks=reference_chunks,
            user_query=user_query
        )

    async def generate_chat_response(self, prompt: str) -> str:
        chain = self.llm | self.text_parser
        return await chain.ainvoke(prompt)

    async def stream_chat_response(self, prompt: str):
        async for chunk in self.llm.astream(prompt):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if content:
                yield content

    # ==================== Direct LLM Access ====================

    async def invoke_llm(self, prompt: str, **kwargs) -> str:
        result = await self.llm.ainvoke(prompt, **kwargs)
        if hasattr(result, 'content'):
            content = result.content
            return str(content) if content is not None else ""
        return str(result)

    async def stream_llm(self, prompt: str, **kwargs):
        async for chunk in self.llm.astream(prompt, **kwargs):
            yield chunk

    def close(self):
        logger.info("LLMService resources closed")
