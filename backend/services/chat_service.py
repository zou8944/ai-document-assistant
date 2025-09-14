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
from rag.intent_analyzer import IntentAnalyzer, QueryIntent
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

        # Initialize intent analyzer
        self.intent_analyzer = IntentAnalyzer(llm=self.llm)

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
        intent: Optional[QueryIntent] = None,
        top_k_per_collection: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve documents from multiple collections with intent-based strategy"""
        all_results = []

        # Adjust retrieval parameters based on intent
        if intent == QueryIntent.OVERVIEW:
            top_k_per_collection = max(top_k_per_collection, 8)
            score_threshold = 0.2  # Lower threshold for broader coverage
        elif intent == QueryIntent.HOW_TO:
            top_k_per_collection = max(top_k_per_collection, 6)
            score_threshold = 0.3  # Standard threshold
        elif intent == QueryIntent.COMPARISON:
            top_k_per_collection = max(top_k_per_collection, 7)
            score_threshold = 0.25  # Moderate threshold
        else:
            score_threshold = 0.3

        logger.info(f"Intent-based retrieval: {intent.value if intent else 'None'}, "
                   f"top_k={top_k_per_collection}, threshold={score_threshold}")

        # Generate query embedding once
        query_embedding = await self.embeddings.aembed_query(query)

        for collection_id in collection_ids:
            try:
                # Search in this collection
                results = await self.chroma_manager.search_similar(
                    collection_name=collection_id,
                    query_embedding=query_embedding,
                    limit=top_k_per_collection,
                    score_threshold=score_threshold
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

        # Adjust final result count based on intent
        if intent == QueryIntent.OVERVIEW:
            max_results = top_k_per_collection * len(collection_ids)  # More results for overview
        else:
            max_results = top_k_per_collection * 2  # Standard limit

        return all_results[:max_results]

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

    def _generate_non_document_response(self, user_message: str, intent: QueryIntent) -> str:
        """
        Generate response for queries that don't need document retrieval

        Args:
            user_message: User's message
            intent: Detected intent

        Returns:
            Appropriate response for the intent
        """
        if intent == QueryIntent.GREETING:
            # Handle greetings
            greetings_map = {
                "你好": "您好！我是您的AI文档助手，可以帮您查找和分析文档内容。有什么问题需要我协助的吗？",
                "您好": "您好！我是您的AI文档助手，可以帮您查找和分析文档内容。有什么问题需要我协助的吗？",
                "hi": "Hello! I'm your AI document assistant. How can I help you today?",
                "hello": "Hello! I'm your AI document assistant. How can I help you today?",
                "谢谢": "不客气！很高兴能帮助您。如果还有其他问题，请随时告诉我。",
                "thank": "You're welcome! Feel free to ask if you have any other questions.",
                "再见": "再见！期待下次为您提供帮助。",
                "bye": "Goodbye! Looking forward to helping you again.",
            }

            message_lower = user_message.lower().strip()
            for key, response in greetings_map.items():
                if key in message_lower:
                    return response

            return "您好！我是您的AI文档助手。如果您有任何关于文档的问题，请随时告诉我！"

        elif intent == QueryIntent.GENERAL:
            # Handle general queries
            if any(keyword in user_message.lower() for keyword in ["你是谁", "你叫什么", "who are you", "your name"]):
                return "我是您的AI文档助手，专门帮助您查找、分析和理解文档内容。我可以回答关于已加载文档的各种问题，包括概述、操作指南、具体事实查询等。"

            elif any(keyword in user_message.lower() for keyword in ["能做什么", "功能", "capabilities", "what can you do"]):
                return """我可以为您提供以下服务：

📋 **文档分析功能：**
• 文档内容概述和总结
• 操作步骤指导
• 具体事实查询
• 不同选项的对比分析

🔍 **智能检索：**
• 根据您的问题类型调整搜索策略
• 提供相关来源引用
• 多文档综合分析

💡 **使用建议：**
• 询问"给我概述一下..."获取整体介绍
• 询问"如何..."获取操作指南
• 询问具体问题获取准确答案
• 询问"A和B的区别"进行对比分析

请告诉我您想了解什么内容！"""

            elif any(keyword in user_message.lower() for keyword in ["时间", "几点", "日期", "time", "date"]):
                return "抱歉，我是文档助手，无法提供实时时间信息。我主要专注于帮助您分析和查找文档内容。有什么关于文档的问题需要我协助吗？"

            else:
                return "我主要专注于帮助您分析文档内容。如果您有关于已加载文档的问题，请告诉我，我会尽力为您解答！"

        else:
            # Fallback for other non-document intents
            return "我是您的AI文档助手，主要帮助您查找和分析文档内容。请告诉我您想了解文档中的什么信息！"

    async def chat(self, chat_id: str, user_message: str) -> Optional[ChatMessageResponse]:
        """Send a message and get AI response with intent-based processing"""
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

        # Analyze user intent
        intent_info = self.intent_analyzer.analyze_with_confidence(user_message)
        intent = intent_info["intent"]
        intent_confidence = intent_info["confidence"]

        logger.info(f"Detected intent: {intent.value} (confidence: {intent_confidence}) - {intent_info['description']}")

        # Check if document retrieval is needed based on intent
        needs_documents = self.intent_analyzer.requires_document_retrieval(intent)

        if needs_documents:
            pass

        # Retrieve relevant documents from multiple collections with intent-based strategy
        logger.info(f"Intent {intent.value} requires document retrieval")
        relevant_docs = await self._retrieve_from_multiple_collections(
            user_message,
            chat.collection_ids,
            intent=intent
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

        # Generate AI response using intent-specific RAG
        from rag.prompt_templates import get_prompt_by_intent

        prompt = get_prompt_by_intent(intent)

        logger.debug(f"Using intent-specific prompt template for {intent.value}")

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

        # Save AI response with sources and intent info
        ai_msg = self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="assistant",
            content=ai_response,
            sources=json.dumps([source.model_dump() for source in sources]),
            metadata=json.dumps({
                "model": self.config.openai_chat_model,
                "sources_count": len(sources),
                "collections_searched": chat.collection_ids,
                "document_retrieval": True
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

        # Analyze user intent
        yield {
            "event": "status",
            "data": json.dumps({"status": "analyzing_intent"})
        }

        intent_info = self.intent_analyzer.analyze_with_confidence(user_message)
        intent = intent_info["intent"]
        intent_confidence = intent_info["confidence"]

        logger.info(f"Detected intent: {intent.value} (confidence: {intent_confidence})")

        # Check if document retrieval is needed based on intent
        needs_documents = self.intent_analyzer.requires_document_retrieval(intent)

        if not needs_documents:
            # Handle non-document queries directly
            logger.info(f"Intent {intent.value} does not require document retrieval")

            yield {
                "event": "status",
                "data": json.dumps({"status": "generating_direct_response"})
            }

            ai_response = self._generate_non_document_response(user_message, intent)

            # Send the direct response as streaming content
            yield {
                "event": "content",
                "data": json.dumps({"content": ai_response}, ensure_ascii=False)
            }

            # Save AI response without sources
            ai_msg = self.chat_message_repo.add_message(
                chat_id=chat_id,
                role="assistant",
                content=ai_response,
                sources=json.dumps([]),
                metadata=json.dumps({
                    "model": self.config.openai_chat_model,
                    "sources_count": 0,
                    "collections_searched": [],
                    "document_retrieval": False
                })
            )

            # Send completion event
            yield {
                "event": "done",
                "data": json.dumps({
                    "message_id": ai_msg.id,
                    "sources_count": 0,
                    "total_content_length": len(ai_response),
                    "document_retrieval": False
                })
            }

            logger.info(f"Generated non-document streaming response for chat {chat_id}")
            return

        # Retrieve relevant documents with intent-based strategy
        logger.info(f"Intent {intent.value} requires document retrieval")
        yield {
            "event": "status",
            "data": json.dumps({"status": "retrieving_documents"})
        }
        relevant_docs = await self._retrieve_from_multiple_collections(
            user_message,
            chat.collection_ids,
            intent=intent
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

        # Generate AI response using intent-specific RAG
        from rag.prompt_templates import get_prompt_by_intent

        prompt = get_prompt_by_intent(intent)

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
