"""
Chat service for managing conversations and AI responses.
"""

import json
import logging
from typing import Any, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from database.connection import get_db_session_context
from models.database.chat import Chat, ChatMessage
from models.responses import ChatMessageResponse, ChatResponse, SourceReference
from repository.chat import ChatMessageRepository, ChatRepository
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing conversations and AI responses"""

    def __init__(self, config=None):
        """Initialize chat service"""
        from config import get_config

        self.config = config or get_config()

        # Initialize components that will be reused
        self.chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings and LLM
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        logger.info("ChatService initialized successfully")

    def _to_chat_response(self, chat: Chat) -> ChatResponse:
        """Convert Chat model to response model"""
        try:
            collection_ids = json.loads(chat.collection_ids) if chat.collection_ids else []
        except json.JSONDecodeError:
            collection_ids = []

        return ChatResponse(
            chat_id=chat.id,
            name=chat.name,
            collection_ids=collection_ids,
            message_count=chat.message_count,
            created_at=chat.created_at.isoformat(),
            last_message_at=chat.last_message_at.isoformat() if chat.last_message_at else None
        )

    def _to_message_response(self, message: ChatMessage) -> ChatMessageResponse:
        """Convert ChatMessage model to response model"""
        try:
            sources = json.loads(message.sources) if message.sources else []
            metadata = json.loads(message.metadata) if message.metadata else {}
        except json.JSONDecodeError:
            sources = []
            metadata = {}

        return ChatMessageResponse(
            message_id=message.id,
            chat_id=message.chat_id,
            role=message.role,
            content=message.content,
            sources=sources,
            metadata=metadata,
            created_at=message.created_at.isoformat()
        )

    async def create_chat(self, name: str, collection_ids: list[str]) -> Optional[ChatResponse]:
        """Create a new chat"""
        with get_db_session_context() as session:
            repo = ChatRepository(session)

            chat = Chat(
                name=name,
                collection_ids=json.dumps(collection_ids),
                message_count=0
            )

            created_chat = repo.create_by_model(chat)
            logger.info(f"Created chat {created_chat.id} with name '{name}'")

            return self._to_chat_response(created_chat)

    async def get_chat(self, chat_id: str) -> Optional[ChatResponse]:
        """Get chat by ID"""
        with get_db_session_context() as session:
            repo = ChatRepository(session)
            chat = repo.get_by_id(chat_id)

            if not chat:
                return None

            return self._to_chat_response(chat)

    async def list_chats(self, offset: int = 0, limit: int = 50) -> list[ChatResponse]:
        """List chats with pagination"""
        with get_db_session_context() as session:
            repo = ChatRepository(session)
            chats = repo.get_all_ordered(offset=offset, limit=limit)

            return [self._to_chat_response(chat) for chat in chats]

    async def update_chat(
        self,
        chat_id: str,
        name: Optional[str] = None,
        collection_ids: Optional[list[str]] = None
    ) -> Optional[ChatResponse]:
        """Update chat information"""
        with get_db_session_context() as session:
            repo = ChatRepository(session)
            chat = repo.get_by_id(chat_id)

            if not chat:
                return None

            if name is not None:
                chat.name = name
            if collection_ids is not None:
                chat.collection_ids = json.dumps(collection_ids)

            session.commit()
            logger.info(f"Updated chat {chat_id}")

            return self._to_chat_response(chat)

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete chat and all its messages"""
        with get_db_session_context() as session:
            chat_repo = ChatRepository(session)
            message_repo = ChatMessageRepository(session)

            # Delete all messages first
            message_repo.delete_by_chat(chat_id)

            # Delete chat
            success = chat_repo.delete(chat_id)

            if success:
                logger.info(f"Deleted chat {chat_id}")

            return success

    async def get_chat_messages(
        self,
        chat_id: str,
        offset: int = 0,
        limit: int = 50
    ) -> list[ChatMessageResponse]:
        """Get messages for a chat"""
        with get_db_session_context() as session:
            repo = ChatMessageRepository(session)
            messages = repo.get_by_chat(chat_id, offset=offset, limit=limit)

            return [self._to_message_response(message) for message in messages]

    async def _retrieve_from_multiple_collections(
        self,
        query: str,
        collection_ids: list[str],
        top_k_per_collection: int = 3
    ) -> list[dict[str, Any]]:
        """Retrieve documents from multiple collections"""
        all_results = []

        # Generate query embedding once
        query_embedding = await self.embeddings.aembed_query(query)

        for collection_id in collection_ids:
            try:
                # Search in this collection
                results = await self.chroma_manager.search_similar(
                    collection_name=collection_id,
                    query_embedding=query_embedding,
                    limit=top_k_per_collection,
                    score_threshold=0.3
                )

                # Add collection info to results
                for result in results:
                    result['collection_id'] = collection_id

                all_results.extend(results)

            except Exception as e:
                logger.warning(f"Failed to search collection '{collection_id}': {e}")
                continue

        # Sort by relevance score and take top results
        all_results.sort(key=lambda x: x.get('score', 0), reverse=True)
        return all_results[:top_k_per_collection * 2]  # Return top results across all collections

    def _format_sources(self, documents: list[dict[str, Any]]) -> list[SourceReference]:
        """Format retrieved documents as source references"""
        sources = []

        for doc in documents:
            source_ref = SourceReference(
                document_name=doc.get('source', 'Unknown Document'),
                document_id=doc.get('document_id', ''),
                chunk_index=doc.get('chunk_index', 0),
                content_preview=doc.get('content', '')[:200] + "..." if len(doc.get('content', '')) > 200 else doc.get('content', ''),
                relevance_score=doc.get('score', 0.0)
            )
            sources.append(source_ref)

        return sources

    def _format_context(self, documents: list[dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
        if not documents:
            return "未找到相关文档。"

        context_parts = []
        for i, doc in enumerate(documents, 1):
            source = doc.get('source', 'Unknown')
            content = doc.get('content', '')
            collection_id = doc.get('collection_id', 'unknown')

            context_part = f"[文档 {i}] 来源: {source} (知识库: {collection_id})\n内容: {content}"
            context_parts.append(context_part)

        return "\n\n".join(context_parts)

    async def send_message(
        self,
        chat_id: str,
        user_message: str
    ) -> Optional[ChatMessageResponse]:
        """Send a message and get AI response"""
        # Get chat information
        chat = await self.get_chat(chat_id)
        if not chat:
            raise ValueError(f"Chat '{chat_id}' not found")

        # Save user message
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)

            message_repo.add_message(
                chat_id=chat_id,
                role="user",
                content=user_message
            )

        # Retrieve relevant documents from multiple collections
        relevant_docs = await self._retrieve_from_multiple_collections(
            user_message,
            chat.collection_ids,
            top_k_per_collection=3
        )

        # Format context and sources
        context = self._format_context(relevant_docs)
        sources = self._format_sources(relevant_docs)

        # Get conversation history for context
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)
            history = message_repo.get_conversation_history(chat_id, max_messages=10)

        # Format conversation history
        conversation_context = ""
        if len(history) > 1:  # More than just the current message
            conversation_context = "\n对话历史:\n"
            for msg in history[:-1]:  # Exclude the current message
                conversation_context += f"{msg.role}: {msg.content}\n"

        # Generate AI response using RAG
        from rag.prompt_templates import get_rag_prompt

        prompt = get_rag_prompt()

        # Prepare the full context
        full_context = context
        if conversation_context:
            full_context = conversation_context + "\n\n当前文档上下文:\n" + context

        # Generate response
        from langchain_core.output_parsers import StrOutputParser
        chain = prompt | self.llm | StrOutputParser()

        ai_response = await chain.ainvoke({
            "context": full_context,
            "question": user_message
        })

        # Save AI response with sources
        with get_db_session_context() as session:
            message_repo = ChatMessageRepository(session)

            ai_msg = message_repo.add_message(
                chat_id=chat_id,
                role="assistant",
                content=ai_response,
                sources=json.dumps([source.dict() for source in sources]),
                metadata=json.dumps({
                    "model": self.config.openai_chat_model,
                    "sources_count": len(sources),
                    "collections_searched": chat.collection_ids
                })
            )

        logger.info(f"Generated AI response for chat {chat_id} with {len(sources)} sources")

        return self._to_message_response(ai_msg)

    def close(self):
        self.chroma_manager.close()
        logger.info("ChatService resources closed")
