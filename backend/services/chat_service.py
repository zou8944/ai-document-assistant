"""
Chat service for managing conversations and AI responses.
"""

import json
import logging
from typing import Any, Optional

from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from exception import HTTPNotFoundException
from models.dto import ChatDTO, ChatMessageDTO
from models.responses import ChatMessageResponse, ChatResponse, SourceReference
from repository.chat import ChatMessageRepository, ChatRepository
from repository.collection import CollectionRepository
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing conversations and AI responses"""

    def __init__(self, config=None):
        """Initialize chat service"""
        from config import get_config

        self.config = config or get_config()

        # Initialize repository instance
        self.chat_repo = ChatRepository()
        self.chat_message_repo = ChatMessageRepository()
        self.collection_repo = CollectionRepository()

        # Initialize components that will be reused
        self.chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings and LLM
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        chat_kwargs = self.config.get_openai_chat_kwargs()
        self.llm = ChatOpenAI(**chat_kwargs)

        logger.info("ChatService initialized successfully")

    def _to_chat_response(self, chat: ChatDTO) -> ChatResponse:
        """Convert Chat model to response model"""
        assert chat.id
        assert chat.name
        return ChatResponse(
            chat_id=chat.id,
            name=chat.name,
            collection_ids=json.loads(chat.collection_ids) if chat.collection_ids else [],
            message_count=chat.message_count or 0,
            created_at=chat.created_at.isoformat() if chat.created_at else "",
            last_message_at=chat.last_message_at.isoformat() if chat.last_message_at else None
        )

    def _to_message_response(self, message: ChatMessageDTO) -> ChatMessageResponse:
        """Convert ChatMessage model to response model"""
        try:
            sources = json.loads(message.sources) if message.sources else []
        except json.JSONDecodeError:
            sources = []

        return ChatMessageResponse(
            message_id=message.id or "" ,
            chat_id=message.chat_id or "",
            role=message.role or "",
            content=message.content or "",
            sources=sources,
            created_at=message.created_at.isoformat() if message.created_at else ""
        )

    async def create_chat(self, name: str, collection_ids: list[str]) -> ChatResponse:
        """Create a new chat"""
        created_chat = self.chat_repo.create_by_model(ChatDTO(
            name=name,
            collection_ids=json.dumps(collection_ids),
            message_count=0
        ))
        logger.info(f"Created chat {created_chat.id} with name '{name}'")

        return self._to_chat_response(created_chat)

    async def get_chat(self, chat_id: str) -> Optional[ChatResponse]:
        """Get chat by ID"""
        chat = self.chat_repo.get_by_id(chat_id)

        if not chat:
            return None

        return self._to_chat_response(chat)

    async def list_chats(self, offset: int = 0, limit: int = 50) -> list[ChatResponse]:
        """List chats with pagination"""
        chats = self.chat_repo.get_all_ordered(offset=offset, limit=limit)

        return [self._to_chat_response(chat) for chat in chats]

    async def update_chat(
        self,
        chat_id: str,
        name: Optional[str] = None,
        collection_ids: Optional[list[str]] = None
    ) -> Optional[ChatResponse]:
        """Update chat information"""
        updated_model = self.chat_repo.update_by_model(ChatDTO(
            id=chat_id,
            name=name,
            collection_ids=json.dumps(collection_ids) if collection_ids else None
        ))
        if not updated_model:
            return None

        return self._to_chat_response(updated_model)

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete chat and all its messages"""
        self.chat_message_repo.delete_by_chat(chat_id)
        return self.chat_repo.delete(chat_id)

    async def get_chat_messages(
        self,
        chat_id: str,
        offset: int = 0,
        limit: int = 50
    ) -> list[ChatMessageResponse]:
        """Get messages for a chat"""
        messages = self.chat_message_repo.get_by_chat(chat_id, offset=offset, limit=limit)
        return [self._to_message_response(message) for message in messages]

    async def count_chat_messages(self, chat_id: str) -> int:
        """Count total chat messages"""
        return self.chat_message_repo.count_by_chat(chat_id)

    async def _retrieve_from_multiple_collections(
        self,
        query: str,
        collection_ids: list[str],
        top_k_per_collection: int = 5
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
        return all_results[:top_k_per_collection * 2]

    def _format_sources(self, documents: list[dict[str, Any]]) -> list[SourceReference]:
        """Format retrieved documents as source references"""
        sources = []

        for doc in documents:
            source_ref = SourceReference(
                document_id=doc.get('document_id', ''),
                document_name=doc.get('document_name', 'Unknown Document'),
                document_uri=doc.get('document_uri', ''),
                chunk_index=doc.get('chunk_index', 0),
                content_preview=doc.get('content', '')[:100] + "..." if len(doc.get('content', '')) > 100 else doc.get('content', ''),
                relevance_score=doc.get('score', 0.0)
            )
            sources.append(source_ref)

        return sources

    def _format_context(self, documents: list[dict[str, Any]]) -> str:
        """Format retrieved documents as context"""
        if not documents:
            return "未找到相关文档。"

        # Cache collection names to avoid repeated queries
        collection_names = {}

        context_parts = []
        for i, doc in enumerate(documents, 1):
            doc_name = doc.get('document_name', 'Unknown')
            content = doc.get('content', '')
            collection_id = doc.get('collection_id', 'unknown')

            # Get collection name
            collection_name = collection_names.get(collection_id)
            if collection_name is None:
                collection = self.collection_repo.get_by_id(collection_id)
                collection_name = collection.name if collection else collection_id
                collection_names[collection_id] = collection_name

            context_part = f"[文档 {i}] 来源: '{doc_name}' (来自知识库: {collection_name})\n内容: {content}"
            context_parts.append(context_part)

        return "\n\n".join(context_parts)

    async def chat(self, chat_id: str, user_message: str) -> Optional[ChatMessageResponse]:
        """Send a message and get AI response"""
        # Get chat information
        chat = await self.get_chat(chat_id)
        if not chat:
            raise HTTPNotFoundException(detail=f"Chat '{chat_id}' not found")

        # Save user message
        self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=user_message
        )

        # Retrieve relevant documents from multiple collections
        relevant_docs = await self._retrieve_from_multiple_collections(
            user_message,
            chat.collection_ids
        )

        # Format context and sources
        context = self._format_context(relevant_docs)
        sources = self._format_sources(relevant_docs)

        # Get conversation history for context
        history = self.chat_message_repo.get_conversation_history(chat_id, max_messages=10)

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
        ai_msg = self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="assistant",
            content=ai_response,
            sources=json.dumps([source.model_dump() for source in sources]),
            metadata=json.dumps({
                "model": self.config.openai_chat_model,
                "sources_count": len(sources),
                "collections_searched": chat.collection_ids
            })
        )

        logger.info(f"Generated AI response for chat {chat_id} with {len(sources)} sources")

        return self._to_message_response(ai_msg)

    async def chat_stream_generator(self, chat_id: str, user_message: str):
        # Get chat information
        chat = await self.get_chat(chat_id)
        if not chat:
            raise HTTPNotFoundException(detail=f"Chat '{chat_id}' not found")

        # Save user message
        self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=user_message
        )

        # Retrieve relevant documents
        yield {
            "event": "status",
            "data": json.dumps({"status": "retrieving_documents"})
        }
        relevant_docs = await self._retrieve_from_multiple_collections(
            user_message,
            chat.collection_ids
        )

        # Send sources found
        sources = self._format_sources(relevant_docs)
        yield {
            "event": "sources",
            "data": json.dumps({
                "sources": [source.model_dump() for source in sources],
                "count": len(sources)
            })
        }

        # Generate AI response
        yield {
            "event": "status",
            "data": json.dumps({"status": "generating_response"})
        }

        # Format context and get conversation history
        context = self._format_context(relevant_docs)
        history = self.chat_message_repo.get_conversation_history(chat_id, max_messages=10)

        # Format conversation history
        conversation_context = ""
        if len(history) > 1:  # More than just the current message
            conversation_context = "\n对话历史:\n"
            for msg in history[:-1]:  # Exclude the current message
                conversation_context += f"{msg.role}: {msg.content}\n"

        # Prepare the full context
        full_context = context
        if conversation_context:
            full_context = conversation_context + "\n\n当前文档上下文:\n" + context

        # Generate AI response using RAG
        from rag.prompt_templates import get_rag_prompt

        prompt = get_rag_prompt()

        # Create streaming chain
        chain = prompt | self.llm

        # Stream response chunks
        full_response = ""
        async for chunk in chain.astream({
            "context": full_context,
            "question": user_message
        }):
            content = chunk.content if hasattr(chunk, 'content') else str(chunk)
            if content:
                full_response += str(content)
                yield {
                    "event": "content",
                    "data": json.dumps({"content": content}, ensure_ascii=False)
                }

        # Save complete AI response
        ai_msg = self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="assistant",
            content=full_response,
            sources=json.dumps([source.model_dump() for source in sources]),
            metadata=json.dumps({
                "model": self.config.openai_chat_model,
                "sources_count": len(sources),
                "collections_searched": chat.collection_ids
            })
        )

        # Send completion event
        yield {
            "event": "done",
            "data": json.dumps({
                "message_id": ai_msg.id,
                "sources_count": len(sources),
                "total_content_length": len(full_response)
            })
        }

        logger.info(f"Generated AI response for chat {chat_id} with {len(sources)} sources")

    def close(self):
        self.chroma_manager.close()
        logger.info("ChatService resources closed")
