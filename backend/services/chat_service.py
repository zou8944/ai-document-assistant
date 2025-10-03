"""
Chat service for managing conversations and AI responses.
"""

import json
import logging
from typing import Any, Optional

from exception import HTTPNotFoundException
from models.dto import ChatDTO, ChatMessageDTO
from models.rag import ChatMessageRoleEnum, CollectionSummary, DocChunk, HistoryItem
from models.responses import ChatMessageResponse, ChatResponse, SourceReference
from repository.chat import ChatMessageRepository, ChatRepository
from repository.collection import CollectionRepository
from repository.document import DocumentRepository
from services.llm_service import LLMService
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


class ChatService:
    """Service for managing conversations and AI responses"""

    def __init__(self, config, llm_service: LLMService):
        """Initialize chat service"""
        self.config = config

        # Initialize repository instance
        self.chat_repo = ChatRepository()
        self.chat_message_repo = ChatMessageRepository()
        self.collection_repo = CollectionRepository()
        self.document_repo = DocumentRepository()

        # Initialize components that will be reused
        self.chroma_manager = create_chroma_manager()

        # Initialize LLM service
        self.llm_service = llm_service

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
        self, collection_ids: list[str], queries: list[str], top_k_per_collection: int = 5
    ) -> list[dict[str, Any]]:
        """Retrieve documents from multiple collections with intent-based strategy"""
        all_results = []
        score_threshold = 0.4

        for query in queries:
            query_embedding = await self.llm_service.embed_query(query)
            for collection_id in collection_ids:
                results = await self.chroma_manager.search_similar(
                    collection_name=collection_id,
                    query_embedding=query_embedding,
                    limit=top_k_per_collection,
                    score_threshold=score_threshold
                )
                for result in results:
                    result['collection_id'] = collection_id

                all_results.extend(results)

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

    def _get_collection_summaries(self, collection_ids: list[str]) -> list[CollectionSummary]:
        summaries = []
        for collection_id in collection_ids:
            collection = self.collection_repo.get_by_id(collection_id)
            assert collection and collection.name
            summaries.append(CollectionSummary(
                name=collection.name,
                summary=collection.summary or ""
            ))
        return summaries

    def _get_chat_history(self, chat_id: str, max_messages: int = 10) -> list[HistoryItem]:
        history = self.chat_message_repo.get_conversation_history(chat_id, max_messages)
        history_items = []
        for chat_message in history:
            if chat_message.role == "user":
                role_enum = ChatMessageRoleEnum.USER
            else:
                role_enum = ChatMessageRoleEnum.ASSISTANT
            history_items.append(HistoryItem(
                role=role_enum,
                message=chat_message.content or ""
            ))
        return history_items

    def _format_doc_chunks(
        self, documents: list[dict[str, Any]], colletcion_summaries: list[CollectionSummary],
    ) -> list[DocChunk]:
        result = []
        for doc in documents:
            doc_name = doc.get('document_name', 'Unknown')
            content = doc.get('content', '')
            collection_id = doc.get('collection_id', 'unknown')
            collection_name = next((col.name for col in colletcion_summaries if col.name == collection_id), collection_id)
            result.append(DocChunk(
                doc_name=doc_name,
                collection_name=collection_name,
                content=content,
            ))
        return result

    async def chat(self, chat_id: str, user_message: str, document_ids: list[str]) -> Optional[ChatMessageResponse]:
        """Send a message and get AI response with intent-based processing"""
        # Get chat information
        chat = await self.get_chat(chat_id)
        if not chat:
            raise HTTPNotFoundException(detail=f"Chat '{chat_id}' not found")

        # 用户提问先入库
        self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=user_message
        )

        collection_summaries = self._get_collection_summaries(chat.collection_ids)
        chat_histories = self._get_chat_history(chat_id, max_messages=10)

        # 如果指定了文档 id，则直接使用这些文档
        sources = []
        doc_chunks = []
        if document_ids:
            docs = [self.document_repo.get_by_id(document_id) for document_id in document_ids]
            doc_chunks = [DocChunk(
                doc_name=doc.name or "Unknown Document",
                collection_name=next((col.name for col in collection_summaries if col.name == doc.collection_id), doc.collection_id or "Unknown Collection"),
                content=doc.content or ""
            ) for doc in docs if doc]
            sources = [SourceReference(
                document_id=doc.id or "",
                document_name=doc.name or "Unknown Document",
                document_uri=doc.uri or "",
                chunk_index=0,
                content_preview="",
                relevance_score=1.0
            ) for doc in docs if doc]
        else:
            # 意图分析
            intent_info = await self.llm_service.analyze_intent(user_message)

            # 向量检索
            relevant_docs = []
            sources = []
            if len(intent_info.queries) > 1:
                relevant_docs = await self._retrieve_from_multiple_collections(chat.collection_ids, intent_info.queries)
                sources = self._format_sources(relevant_docs)

            ## 提示词素材准备
            doc_chunks = self._format_doc_chunks(relevant_docs, collection_summaries)
        # 提示词构建
        prompt = self.llm_service.build_rag_prompt(
            collections=collection_summaries,
            histories=chat_histories,
            reference_chunks=doc_chunks,
            user_query=user_message
        )
        # 阻塞式 AI 生成
        ai_response = await self.llm_service.generate_chat_response(prompt)

        # 结果入库
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

        # 返回 AI 回复
        return self._to_message_response(ai_msg)

    async def chat_stream_generator(self, chat_id: str, user_message: str, document_ids: list[str]):
        # Get chat information
        chat = await self.get_chat(chat_id)
        if not chat:
            raise HTTPNotFoundException(detail=f"Chat '{chat_id}' not found")

        # 用户提问先入库
        self.chat_message_repo.add_message(
            chat_id=chat_id,
            role="user",
            content=user_message
        )

        collection_summaries = self._get_collection_summaries(chat.collection_ids)
        chat_histories = self._get_chat_history(chat_id, max_messages=10)

        doc_chunks = []
        sources = []
        if document_ids:
            docs = [self.document_repo.get_by_id(document_id) for document_id in document_ids]
            doc_chunks = [DocChunk(
                doc_name=doc.name or "Unknown Document",
                collection_name=next((col.name for col in collection_summaries if col.name == doc.collection_id), doc.collection_id or "Unknown Collection"),
                content=doc.content or ""
            ) for doc in docs if doc]
            sources = [SourceReference(
                document_id=doc.id or "",
                document_name=doc.name or "Unknown Document",
                document_uri=doc.uri or "",
                chunk_index=0,
                content_preview="",
                relevance_score=1.0
            ) for doc in docs if doc]
        else:
            # 意图分析
            yield {
                "event": "status",
                "data": json.dumps({"status": "analyzing_intent"})
            }
            intent_info = await self.llm_service.analyze_intent(user_message)

            # 向量检索
            relevant_docs = []
            if len(intent_info.queries) > 1:
                yield {
                    "event": "status",
                    "data": json.dumps({"status": "retrieving_documents"})
                }
                relevant_docs = await self._retrieve_from_multiple_collections(chat.collection_ids, intent_info.queries)

                sources = self._format_sources(relevant_docs)
                yield {
                    "event": "sources",
                    "data": json.dumps({
                        "sources": [source.model_dump() for source in sources],
                        "count": len(sources)
                    })
                }
            doc_chunks = self._format_doc_chunks(relevant_docs, collection_summaries)

        # AI 生成
        yield {
            "event": "status",
            "data": json.dumps({"status": "generating_response"})
        }
        # 提示词构建
        prompt = self.llm_service.build_rag_prompt(
            collections=collection_summaries,
            histories=chat_histories,
            reference_chunks=doc_chunks,
            user_query=user_message
        )

        # 结果流式相应
        full_response = ""
        async for content in self.llm_service.stream_chat_response(prompt):
            if content:
                full_response += str(content)
                yield {
                    "event": "content",
                    "data": json.dumps({"content": content}, ensure_ascii=False)
                }

        # 完成后，AI 回复入库
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

        # 发送结束事件
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
        self.llm_service.close()
        logger.info("ChatService resources closed")
