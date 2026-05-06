import json
import logging
import time
from collections.abc import AsyncIterator

from chat.context.assembler import ContextAssembler
from chat.evaluation import SelfEvaluator
from chat.generation.base import BaseLLMService
from chat.models import (
    ProcessingMode,
    SSEEvent,
    SSEEventType,
)
from chat.retrieval.orchestrator import RetrievalOrchestrator
from chat.router import QueryRouter
from models.rag import ChatMessageRoleEnum, HistoryItem

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self,
                 router_llm: BaseLLMService,
                 fast_llm: BaseLLMService,
                 standard_llm: BaseLLMService,
                 deep_llm: BaseLLMService,
                 orchestrator: RetrievalOrchestrator,
                 assembler: ContextAssembler,
                 chat_repo,
                 chat_message_repo):
        self.router = QueryRouter(router_llm)
        self.llms = {
            ProcessingMode.FAST: fast_llm,
            ProcessingMode.STANDARD: standard_llm,
            ProcessingMode.DEEP: deep_llm,
        }
        self.orchestrator = orchestrator
        self.assembler = assembler
        self.chat_repo = chat_repo
        self.chat_message_repo = chat_message_repo
        self.evaluator = SelfEvaluator(fast_llm)

    def _get_chat_history(self, chat_id: str, max_messages: int = 10):
        history = self.chat_message_repo.get_conversation_history(chat_id, max_messages)
        items = []
        for msg in history:
            role = "user" if msg.role == "user" else "assistant"
            items.append(HistoryItem(
                role=ChatMessageRoleEnum.USER if role == "user" else ChatMessageRoleEnum.ASSISTANT,
                message=msg.content or ""
            ))
        return items

    async def process(self, chat_id: str, query: str) -> AsyncIterator[SSEEvent]:
        full_response = ""
        context = None
        timings = {}
        total_start = time.perf_counter()

        try:
            chat = self.chat_repo.get_by_id(chat_id)
            if not chat:
                yield SSEEvent(SSEEventType.ERROR, {"message": f"Chat '{chat_id}' not found"})
                return

            collection_ids = json.loads(chat.collection_ids) if chat.collection_ids else []
            chat_history = self._get_chat_history(chat_id)

            # Convert HistoryItem objects to dicts for router compatibility
            chat_history_dicts = [
                {"role": "user" if item.role == ChatMessageRoleEnum.USER else "assistant", "content": item.message}
                for item in chat_history
            ]

            # Persist user message so it appears in history even if generation fails
            self.chat_message_repo.add_message(
                chat_id=chat_id,
                role="user",
                content=query
            )

            yield SSEEvent(SSEEventType.STATUS, {"stage": "analyzing", "message": "分析查询意图..."})
            t0 = time.perf_counter()
            router_result = await self.router.analyze(query, chat_history_dicts)
            timings["intent_analysis_ms"] = round((time.perf_counter() - t0) * 1000)
            yield SSEEvent(SSEEventType.INTENT, {
                "intent": router_result.intent.value,
                "confidence": router_result.confidence,
                "suggested_mode": router_result.suggested_mode.value,
                "complexity_score": router_result.complexity_score
            })

            yield SSEEvent(SSEEventType.STATUS, {"stage": "searching", "message": "检索相关文档..."})

            if not router_result.requires_retrieval:
                timings["document_retrieval_ms"] = 0
                timings["evaluation_ms"] = 0
                yield SSEEvent(SSEEventType.SOURCES, {"documents": [], "total_found": 0})
                collection_infos = await self.orchestrator.fetch_collection_overviews(collection_ids)

                yield SSEEvent(SSEEventType.STATUS, {"stage": "assembling", "message": "整理上下文..."})
                t0 = time.perf_counter()
                context = self.assembler.assemble_lite(
                    intent=router_result.intent,
                    query=query,
                    collection_info=collection_infos,
                    chat_history=chat_history
                )
                timings["context_assembly_ms"] = round((time.perf_counter() - t0) * 1000)

                yield SSEEvent(SSEEventType.STATUS, {"stage": "generating", "message": "生成回答..."})
                llm = self.llms[context.mode]

                t0 = time.perf_counter()
                full_response = ""
                async for chunk in llm.stream_generate(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    temperature=0.7,
                    max_tokens=4096
                ):
                    if chunk:
                        full_response += chunk
                        yield SSEEvent(SSEEventType.CONTENT, {"delta": chunk})
                timings["generation_ms"] = round((time.perf_counter() - t0) * 1000)
                timings["total_ms"] = round((time.perf_counter() - total_start) * 1000)

                yield SSEEvent(SSEEventType.DONE, {"timings": timings})
            else:
                # First round: retrieval + generation
                t0 = time.perf_counter()
                search_result, collection_infos = await self.orchestrator.retrieve(
                    intent=router_result.intent,
                    queries=router_result.rewritten_queries,
                    collection_ids=collection_ids,
                    top_k=25
                )
                timings["document_retrieval_ms"] = round((time.perf_counter() - t0) * 1000)

                yield SSEEvent(SSEEventType.SOURCES, {
                    "documents": [
                        {
                            "document_id": d.document_id,
                            "document_name": d.document_name,
                            "relevance_score": d.relevance_score,
                            "source_type": d.source_type
                        }
                        for d in search_result.documents
                    ],
                    "total_found": search_result.total_found
                })

                yield SSEEvent(SSEEventType.STATUS, {"stage": "assembling", "message": "整理上下文..."})
                t0 = time.perf_counter()
                context = self.assembler.assemble(
                    mode=router_result.suggested_mode,
                    query=query,
                    search_result=search_result,
                    collection_info=collection_infos,
                    chat_history=chat_history
                )
                timings["context_assembly_ms"] = round((time.perf_counter() - t0) * 1000)

                yield SSEEvent(SSEEventType.STATUS, {"stage": "generating", "message": "生成回答..."})
                llm = self.llms[context.mode]

                t0 = time.perf_counter()
                full_response = ""
                async for chunk in llm.stream_generate(
                    system_prompt=context.system_prompt,
                    messages=context.messages,
                    temperature=0.7,
                    max_tokens=4096
                ):
                    if chunk:
                        full_response += chunk
                        yield SSEEvent(SSEEventType.CONTENT, {"delta": chunk})
                timings["generation_ms"] = round((time.perf_counter() - t0) * 1000)

                # Self-evaluation round (only for retrieval-based queries)
                t0 = time.perf_counter()
                eval_result = await self.evaluator.evaluate(
                    query=query,
                    draft=full_response,
                    context_docs=context.context_documents
                )
                timings["evaluation_ms"] = round((time.perf_counter() - t0) * 1000)

                if eval_result.confidence_score < 0.8 and eval_result.supplementary_queries:
                    yield SSEEvent(SSEEventType.STATUS, {"stage": "refining", "message": "正在深入检索更多信息..."})

                    # Second round retrieval with supplementary queries
                    t0 = time.perf_counter()
                    supplementary_result, _ = await self.orchestrator.retrieve(
                        intent=router_result.intent,
                        queries=eval_result.supplementary_queries,
                        collection_ids=collection_ids,
                        top_k=25
                    )
                    timings["document_retrieval_ms"] += round((time.perf_counter() - t0) * 1000)

                    # Merge results: combine documents from both rounds, keeping highest score
                    merged_docs: dict[str, dict] = {}
                    for doc in search_result.documents:
                        key = f"{doc.document_id}:{doc.chunk_index or 0}"
                        merged_docs[key] = {
                            "document_id": doc.document_id,
                            "document_name": doc.document_name,
                            "document_uri": doc.document_uri,
                            "content": doc.content,
                            "relevance_score": doc.relevance_score,
                            "source_type": doc.source_type,
                            "chunk_index": doc.chunk_index
                        }
                    for doc in supplementary_result.documents:
                        key = f"{doc.document_id}:{doc.chunk_index or 0}"
                        if key in merged_docs:
                            if doc.relevance_score > merged_docs[key]["relevance_score"]:
                                merged_docs[key]["relevance_score"] = doc.relevance_score
                        else:
                            merged_docs[key] = {
                                "document_id": doc.document_id,
                                "document_name": doc.document_name,
                                "document_uri": doc.document_uri,
                                "content": doc.content,
                                "relevance_score": doc.relevance_score,
                                "source_type": doc.source_type,
                                "chunk_index": doc.chunk_index
                            }

                    from chat.models import RetrievedDocument, SearchResult
                    merged_search_result = SearchResult(
                        documents=sorted(
                            [
                                RetrievedDocument(
                                    document_id=d["document_id"],
                                    document_name=d["document_name"],
                                    document_uri=d["document_uri"],
                                    content=d["content"],
                                    relevance_score=d["relevance_score"],
                                    source_type=d["source_type"],
                                    chunk_index=d["chunk_index"]
                                )
                                for d in merged_docs.values()
                            ],
                            key=lambda d: d.relevance_score,
                            reverse=True
                        )[:25],
                        search_type="hybrid+refined",
                        total_found=len(merged_docs)
                    )

                    yield SSEEvent(SSEEventType.SOURCES, {
                        "documents": [
                            {
                                "document_id": d.document_id,
                                "document_name": d.document_name,
                                "relevance_score": d.relevance_score,
                                "source_type": d.source_type
                            }
                            for d in merged_search_result.documents
                        ],
                        "total_found": merged_search_result.total_found
                    })

                    yield SSEEvent(SSEEventType.STATUS, {"stage": "assembling", "message": "重新整理上下文..."})
                    t0 = time.perf_counter()
                    context = self.assembler.assemble(
                        mode=router_result.suggested_mode,
                        query=query,
                        search_result=merged_search_result,
                        collection_info=collection_infos,
                        chat_history=chat_history
                    )
                    timings["context_assembly_ms"] += round((time.perf_counter() - t0) * 1000)

                    yield SSEEvent(SSEEventType.STATUS, {"stage": "generating", "message": "生成最终回答..."})
                    llm = self.llms[context.mode]

                    t0 = time.perf_counter()
                    full_response = ""
                    async for chunk in llm.stream_generate(
                        system_prompt=context.system_prompt,
                        messages=context.messages,
                        temperature=0.7,
                        max_tokens=4096
                    ):
                        if chunk:
                            full_response += chunk
                            yield SSEEvent(SSEEventType.CONTENT, {"delta": chunk})
                    timings["generation_ms"] += round((time.perf_counter() - t0) * 1000)

                timings["total_ms"] = round((time.perf_counter() - total_start) * 1000)
                yield SSEEvent(SSEEventType.DONE, {"timings": timings})

        except Exception as e:
            logger.error(f"Chat processing error: {e}", exc_info=True)
            yield SSEEvent(SSEEventType.ERROR, {"message": str(e)})
            return

        # Persist assistant message after successful generation
        try:
            if context and full_response:
                metadata = json.dumps({"timings": timings}) if timings else "{}"
                self.chat_message_repo.add_message(
                    chat_id=chat_id,
                    role="assistant",
                    content=full_response,
                    sources=json.dumps([{
                        "document_id": d.document_id,
                        "document_name": d.document_name,
                        "relevance_score": d.relevance_score
                    } for d in context.context_documents]),
                    metadata=metadata
                )
        except Exception as e:
            logger.error(f"Failed to persist assistant message: {e}", exc_info=True)

    def close(self) -> None:
        """Close all LLM clients."""
        for llm in self.llms.values():
            try:
                llm.close()
            except Exception as e:
                logger.warning(f"Error closing LLM client {llm.name}: {e}")
