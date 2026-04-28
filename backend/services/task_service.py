"""
Task management service for async operations.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import os
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urldefrag, urljoin, urlparse

from langchain_core.output_parsers import StrOutputParser

from crawler.simple_web_crawler import SimpleCrawlResult, create_simple_web_crawler
from data_processing.file_processor import create_file_processor
from data_processing.text_splitter import create_document_processor
from database.connection import transaction
from exception import HTTPNotFoundException
from models.dto import DocumentChunkDTO, DocumentDTO, TaskDTO, TaskLogDTO
from models.responses import TaskResponse
from repository.document import DocumentChunkRepository, DocumentRepository
from repository.task import TaskLogRepository, TaskRepository
from services.collection_service import CollectionService
from services.llm_service import LLMService
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


@dataclass
class FileTaskStats:
    files_processed: int = 0
    files_total: int = 0

@dataclass
class UrlTaskStats:
    urls_crawled: int = 0
    urls_crawl_total: int = 0
    pages_processed: int = 0
    pages_total: int = 0
    phase: str = "crawl"          # crawl | rewrite | readme
    rewrite_done: int = 0
    rewrite_total: int = 0

class TaskService:
    """Service for managing async tasks"""

    def __init__(self, config, collection_service: CollectionService, llm_service: LLMService):
        """Initialize task service"""
        self.config = config

        self.collection_service = collection_service

        # Task queue and workers
        self.task_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.running = False
        self._stop_flags: set[str] = set()  # Task IDs marked for stopping

        # Initialize repositories
        self.task_repo = TaskRepository()
        self.task_log_repo = TaskLogRepository()
        self.doc_repo = DocumentRepository()
        self.doc_chunk_repo = DocumentChunkRepository()

        # Shared components - created once and reused
        self.document_processor = create_document_processor()
        self.chroma_manager = create_chroma_manager()
        self.file_processor = create_file_processor(self.config)
        self.web_crawler = create_simple_web_crawler(self.config)

        # LLM service
        self.llm_service = llm_service

        logger.info("TaskService initialized successfully")

    def _to_response(self, task: TaskDTO) -> TaskResponse:
        """Convert Task model to response model"""
        try:
            input_params = json.loads(task.input_params) if task.input_params else {}
        except json.JSONDecodeError:
            input_params = {}

        urls = input_params.get("urls", [])
        if isinstance(urls, str):
            urls = [urls]
        recursive_prefix = input_params.get("recursive_prefix", "")

        return TaskResponse(
            task_id=task.id or "",
            type=task.type or "",
            status=task.status or "",
            progress=task.progress_percentage or 0,
            stats=input_params,
            collection_id=task.collection_id or "",
            created_at=task.created_at.isoformat() if task.created_at else "",
            updated_at=task.updated_at.isoformat() if task.updated_at else "",
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            urls=urls,
            recursive_prefix=recursive_prefix,
            error=task.error_message,
            title=input_params.get("title")
        )

    def _log_info_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "info", message)

    def _log_debug_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "debug", message)

    def _log_err_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "error", message)

    def _log_task(self, task_id: str, level: str, message: str):
        self.task_log_repo.add_log(task_id, level, message, None)
        logger.log(getattr(logging, level.upper()), message, exc_info=(level == "error"))

    async def _generate_task_title(
        self,
        urls: list[str],
        recursive_prefix: str,
        existing_titles: list[str]
    ) -> str:
        """Generate a Chinese title for a URL ingestion task using LLM."""
        urls_str = "\n".join(f"- {url}" for url in urls[:5])
        if len(urls) > 5:
            urls_str += f"\n... 等共 {len(urls)} 个 URL"

        prefix_str = f"递归前缀: {recursive_prefix}" if recursive_prefix else "递归前缀: 无"

        existing_titles_str = ""
        if existing_titles:
            existing_titles_str = "\n已有标题列表（请确保新标题不与以下重复）:\n" + "\n".join(f"- {t}" for t in existing_titles)

        prompt = (
            "请为以下网页抓取任务生成一个20字以内的中文标题。\n\n"
            f"初始URL:\n{urls_str}\n"
            f"{prefix_str}\n"
            f"{existing_titles_str}\n\n"
            "要求:\n"
            "1. 标题应简洁概括该任务抓取的内容范围\n"
            "2. 严格控制在20字以内\n"
            "3. 使用中文\n"
            "4. 不要与已有标题重复\n\n"
            "请只返回标题文字，不要任何解释。"
        )

        try:
            chain = self.llm_service.llm | StrOutputParser()
            title = await chain.ainvoke(prompt)
            title = title.strip().strip('"').strip("'").strip()
            if len(title) > 20:
                title = title[:20]
            return title
        except Exception as e:
            logger.warning(f"Failed to generate task title: {e}")
            # Fallback: use first URL hostname
            try:
                from urllib.parse import urlparse
                hostname = urlparse(urls[0]).netloc if urls else "未知"
                return f"{hostname} 网页抓取"
            except Exception:
                return "网页抓取"

    async def create_task(self, task_type: str, collection_id: str, input_params: dict[str, Any]) -> TaskResponse:
        """Create a new task"""
        # Generate AI title for URL ingestion tasks
        if task_type == "ingest_urls":
            urls = input_params.get("urls", [])
            recursive_prefix = input_params.get("recursive_prefix", "")

            # Get existing task titles for this collection
            existing_tasks = self.task_repo.list_tasks_with_filters(
                collection_id=collection_id, limit=200
            )
            existing_titles: list[str] = []
            for t in existing_tasks:
                try:
                    params = json.loads(t.input_params) if t.input_params else {}
                    if params.get("title"):
                        existing_titles.append(params["title"])
                except json.JSONDecodeError:
                    pass

            title = await self._generate_task_title(urls, recursive_prefix, existing_titles)
            input_params["title"] = title
            logger.info(f"Generated task title: {title}")

        created_task = self.task_repo.create_by_model(TaskDTO(
            type=task_type,
            collection_id=collection_id,
            input_params=json.dumps(input_params),
            status="pending"
        ))

        # Add task to queue
        await self.task_queue.put(created_task.id)

        logger.info(f"Created task {created_task.id} of type {task_type}")

        return self._to_response(created_task)

    async def get_task(self, task_id: str) -> TaskDTO:
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPNotFoundException(f"Task {task_id} not found")

        return task

    async def get_task_response(self, task_id: str) -> TaskResponse:
        task = await self.get_task(task_id)
        return self._to_response(task)

    async def list_task_responses(self, collection_id: str) -> list[TaskResponse]:
        tasks = self.task_repo.list_tasks_with_filters(collection_id=collection_id, limit=200)
        return [self._to_response(task) for task in tasks]

    async def get_task_logs(self, task_id: str, limit: int | None = None, offset: int = 0) -> list[TaskLogDTO]:
        return self.task_log_repo.list_by_task(task_id=task_id, limit=limit, offset=offset)

    async def stop_task(self, task_id: str) -> bool:
        """Mark a running task for graceful stop."""
        task = self.task_repo.get_by_id(task_id)
        if not task or task.status != "processing":
            return False
        self._stop_flags.add(task_id)
        self.task_repo.update_status(task_id, "stopped")
        self._log_info_task(task_id, "任务停止请求已接收")
        return True

    async def restart_task(self, task_id: str) -> TaskResponse:
        """Restart a completed or stopped task from scratch."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPNotFoundException(f"Task {task_id} not found")
        if task.status not in ("success", "failed", "stopped"):
            from exception import HTTPBadRequestException
            raise HTTPBadRequestException("只能重跑已完成或已停止的任务")

        # Delete old logs before restarting
        self.task_log_repo.delete_by_task(task_id)
        self.task_repo.reset_task(task_id)
        await self.task_queue.put(task_id)
        logger.info(f"Restarted task {task_id}")

        return self._to_response(self.task_repo.get_by_id(task_id))

    async def cleanup_task(self, task_id: str) -> bool:
        """Cleanup all resources produced by a task and reset it to pending."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            return False
        if task.status == "processing":
            from exception import HTTPBadRequestException
            raise HTTPBadRequestException("不能清理正在执行的任务")

        collection_id = task.collection_id

        # 1. Delete all documents produced by this task
        docs = self.doc_repo.get_by_task(task_id)
        if docs and collection_id:
            chroma_collection = await self.chroma_manager.get_collection(collection_id)
            for doc in docs:
                if chroma_collection and doc.id:
                    try:
                        chroma_collection.delete(where={"document_id": doc.id})
                    except Exception as e:
                        logger.warning(f"Failed to delete vectors for doc {doc.id}: {e}")
                self.doc_chunk_repo.delete_by_document(doc.id)
                self.doc_repo.delete_by_id(doc.id)

        # 2. Delete local crawl cache for URL tasks
        if task.type == "ingest_urls" and collection_id:
            self._delete_crawl_cache(collection_id)

        # 3. Clear task logs
        self.task_log_repo.delete_by_task(task_id)

        # 4. Reset task state
        self.task_repo.reset_task(task_id)

        # 5. Regenerate collection summary if documents remain
        if collection_id:
            remaining = self.doc_repo.count_by_collection(collection_id)
            if remaining > 0:
                await self.collection_service.refresh_collection_summary(collection_id)
            else:
                self.collection_service.collection_repo.update(
                    collection_id,
                    readme_content=None,
                    categories_json=None,
                    readme_content_zh=None,
                    categories_json_zh=None,
                    source_language=None,
                )

        logger.info(f"Cleaned up task {task_id}")
        return True

    def _delete_crawl_cache(self, collection_id: str) -> None:
        """Delete local crawl cache directory for a collection."""
        cache_root = Path(self.config.get_crawl_cache_dir())
        # Find domain dirs that belong to this collection's documents
        docs = self.doc_repo.get_by_collection(collection_id)
        domains = set()
        for doc in docs:
            if doc.uri and doc.uri.startswith("http"):
                domains.add(self._domain_key(doc.uri))
        for domain in domains:
            domain_dir = cache_root / domain
            if domain_dir.exists():
                import shutil
                shutil.rmtree(domain_dir)
                logger.info(f"Deleted crawl cache: {domain_dir}")

    async def get_task_stream_generator(self, task_id: str):
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPNotFoundException(f"Task {task_id} not found")

        # Send initial metadata
        yield {
            "event": "metadata",
            "data": json.dumps({
                "task_id": task_id,
                "type": task.type,
                "collection_id": task.collection_id
            })
        }

        last_progress = -1
        offset = 0
        while True:
            # Get current task status
            current_task = self.task_repo.get_by_id(task_id)
            task_logs = self.task_log_repo.list_by_task(task_id, limit=100, offset=offset)
            assert current_task

            # Send progress update if changed
            current_progress = current_task.progress_percentage or 0
            if current_progress != last_progress:
                yield {
                    "event": "progress",
                    "data": json.dumps({
                        "percentage": current_progress,
                        "stats": current_task.stats
                    })
                }
                last_progress = current_progress

            # send task logs
            for log in task_logs:
                yield {
                    "event": "log",
                    "data": json.dumps({
                        "level": log.level,
                        "message": log.message,
                        "timestamp": log.timestamp.isoformat() if log.timestamp else None,
                        "details": json.loads(log.details) if log.details else {}
                    })
                }
            offset += len(task_logs)

            # check if task is completed
            if current_task.status == "success":
                yield {
                    "event": "done",
                    "data": json.dumps({
                        "duration_ms": None  # Could calculate if needed
                    })
                }
                break
            elif current_task.status == "failed":
                yield {
                    "event": "error",
                    "data": json.dumps({
                        "message": current_task.error_message
                    })
                }
                break

            # Wait before next check
            await asyncio.sleep(1.0)

    async def update_file_task_progress(self, task_id: str, stats: FileTaskStats) -> bool:
        stats_json = json.dumps(asdict(stats))
        progress = stats.files_processed * 100 // stats.files_total if stats.files_total > 0 else 0
        return self.task_repo.update_progress(task_id, progress, stats_json)

    def update_url_task_progress(self, task_id: str, stats: UrlTaskStats) -> bool:
        stats_json = json.dumps(asdict(stats))
        progress = 0

        if stats.phase == "crawl":
            if stats.pages_total == 0:
                progress = stats.urls_crawled * 50 // stats.urls_crawl_total if stats.urls_crawl_total > 0 else 0
            else:
                progress = min(50, stats.pages_processed * 50 // stats.pages_total)
        elif stats.phase == "rewrite":
            if stats.rewrite_total > 0:
                progress = 50 + stats.rewrite_done * 35 // stats.rewrite_total
            else:
                progress = 50
        elif stats.phase == "readme":
            progress = 85

        return self.task_repo.update_progress(task_id, progress, stats_json)

    async def requeue_processing_task(self):
        tasks = self.task_repo.get_active_tasks()
        for task in tasks:
            await self.task_queue.put(task.id)
            logger.info(f"Re-queued processing task {task.id}")

    async def start_workers(self):
        """Start background task workers"""
        if self.running:
            logger.warning("Workers already running")
            return

        # Requeue processing tasks
        await self.requeue_processing_task()

        self.running = True
        self.executor.submit(self._sync_worker, "Task_queue_worker")

    async def stop_workers(self):
        """Stop background task workers"""
        if not self.running:
            return

        logger.info("Stopping task workers...")
        self.running = False

        # Cancel all workers
        self.executor.shutdown(wait=True)

        logger.info("Task workers stopped")

    def _sync_worker(self, worker_name: str):
        """Sync worker wrapper to ensure logging configuration is applied"""
        from config import get_config
        from logging_config import configure_logging

        # 确保在新线程中日志配置也正确
        configure_logging(get_config())

        # 重新获取 logger 以确保使用最新配置
        global logger
        import logging
        logger = logging.getLogger(__name__)

        logger.info(f"Sync worker {worker_name} starting")
        asyncio.run(self._worker(worker_name))

    async def _worker(self, worker_name: str):
        """Background worker that processes tasks from queue"""
        logger.info(f"Task worker {worker_name} started")

        while self.running:
            try:
                # Wait for task with timeout
                task_id = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )

                logger.info(f"Worker {worker_name} processing task {task_id}")

                # Process the task
                await self._process_task_with_exception(task_id)

                # Mark task as done in queue
                self.task_queue.task_done()

            except asyncio.TimeoutError:
                # No task available, continue loop
                continue
            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}", exc_info=True)
                # Continue processing other tasks
                continue

        logger.info(f"Task worker {worker_name} stopped")

    async def _process_task_with_exception(self, task_id: str):
        try:
            await self._process_task(task_id)
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            self.task_repo.mark_completed(task_id, success=False, error_message=str(e))

    async def _process_task(self, task_id: str):
        """Process a single task"""
        # Get task details
        task = self.task_repo.get_by_id(task_id)

        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # Mark as started
        self.task_repo.mark_started(task_id)

        # Parse input parameters
        assert task.input_params
        input_params = json.loads(task.input_params)

        # Route to appropriate handler
        assert task.collection_id
        if task.type == "ingest_files":
            await self._process_file_ingestion(task_id, task.collection_id, input_params)
        elif task.type == "ingest_urls":
            await self._process_url_ingestion(task_id, task.collection_id, input_params)
        else:
            error_msg = f"Unknown task type: {task.type}"
            logger.error(error_msg)
            self.task_repo.mark_completed(task_id, False, error_msg)

        # Check if task was stopped
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self.task_repo.update_status(task_id, "stopped")
            self._log_info_task(task_id, "任务已停止")
            return

        # 重新为目标知识库生成摘要
        await self.collection_service.refresh_collection_summary(task.collection_id)

    async def _check_document_exists(self, collection_id: str, uri: str) -> bool:
        """Check if document already exists and handle duplication logic"""
        existing_doc = self.doc_repo.find_by_uri(collection_id, uri)
        if existing_doc:
            return True
        else:
            return False

    async def _create_document_record(self, collection_id: str, name: str, uri: str,
                                      size_bytes: int, mime_type: Optional[str], doc_hash: str):
        """Create a new document record in database"""

        document = DocumentDTO(
            collection_id=collection_id,
            name=name,
            uri=uri,
            size_bytes=size_bytes,
            mime_type=mime_type,
            status="processing",
            hash_md5=doc_hash
        )

        created_doc = self.doc_repo.create_by_model(document)
        return created_doc.id

    async def _store_document(
        self,
        collection_id: str,
        doc_page_uri: str,
        doc_title: str,
        doc_content: str,
        doc_summary: str,
        doc_mime_type: str,
        doc_status: str,
        doc_error_message: str | None,
        chunks,
        chunk_embeddings,
        source_task_id: str | None = None,
    ):
        """Store document chunks in database and vector store"""
        collection = await self.chroma_manager.get_collection(collection_id)
        assert collection

        # remove exist document, chunks, embeddings
        exist_document = self.doc_repo.find_by_uri(collection_id, doc_page_uri)
        if exist_document:
            assert exist_document.id
            self.doc_chunk_repo.delete_by_document(exist_document.id)
            self.doc_repo.delete_by_id(exist_document.id)
            collection.delete(where={"document_id": exist_document.id})

        vector_ids = []
        embedding_list = []
        metadatas = []
        documents = []
        chunk_records = []

        # construct doc record
        doc_id = uuid.uuid4().hex
        doc_record = DocumentDTO(
            id=doc_id,
            collection_id=collection_id,
            name=doc_title or f"Page from {doc_page_uri}",
            uri=doc_page_uri,
            content=doc_content,
            summary=doc_summary,
            size_bytes=len(doc_content.encode()),
            mime_type=doc_mime_type,
            chunk_count=len(chunks),
            status=doc_status,
            error_message=doc_error_message,
            hash_md5=hashlib.md5(f"{doc_page_uri}:{doc_title}:{doc_content}".encode()).hexdigest(),
            source_task_id=source_task_id,
        )

        # Safety check: ensure chunks and embeddings have same length
        if len(chunks) != len(chunk_embeddings):
            raise ValueError(f"Chunks length ({len(chunks)}) doesn't match embeddings length ({len(chunk_embeddings)})")

        # construct chunk records
        for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
            # Create unique vector ID
            vector_id = f"{doc_id}_chunk_{i}"

            # Create chunk record
            chunk_record = DocumentChunkDTO(
                document_id=doc_id,
                collection_id=collection_id,
                chunk_index=i,
                content_preview=chunk.content[:200] if chunk.content else "",
                vector_id=vector_id,
                content_hash=hashlib.md5(chunk.content.encode()).hexdigest(),
                chunk_metadata=json.dumps(chunk.metadata)
            )

            chunk_records.append(chunk_record)

            vector_ids.append(vector_id)
            embedding_list.append(embedding)
            metadatas.append({
                "document_id": doc_id,
                "document_name": doc_title,
                "document_uri": doc_page_uri,
                "collection_id": collection_id,
                "chunk_index": i,
            })
            documents.append(chunk.content)

        async with transaction():
            # store document in database
            self.doc_repo.create_by_model(doc_record)

            # if no chunk_records, just return 0
            if not chunk_records:
                return 0

            # Store chunks in database
            for chunk_record in chunk_records:
                self.doc_chunk_repo.create_by_model(chunk_record)

            # Store embeddings in ChromaDB
            collection.add(
                ids=vector_ids,
                embeddings=embedding_list,
                metadatas=metadatas,
                documents=documents
            )


        return len(chunk_records)

    async def _process_file_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process file ingestion task with full integration"""
        self._log_info_task(task_id, "Starting file ingestion")

        # Get file paths from input params
        file_paths = input_params.get("files", [])
        override = input_params.get("override", True)
        if not file_paths:
            raise ValueError("No files specified for ingestion")

        # Collect all files to process
        all_files = []
        for file_path in file_paths:
            path_obj = Path(file_path)
            if path_obj.is_file():
                all_files.append(str(path_obj))
            elif path_obj.is_dir():
                # Get all supported files in directory
                for ext in ['.pdf', '.docx', '.txt', '.md']:
                    all_files.extend([str(f) for f in path_obj.rglob(f'*{ext}')])

        if not all_files:
            raise ValueError("No supported files found in specified paths")

        # init zero stats
        stats = FileTaskStats(files_total=len(all_files))
        await self.update_file_task_progress(task_id, stats)

        for file_path in all_files:
            # Check stop flag before processing next file
            if task_id in self._stop_flags:
                self._stop_flags.discard(task_id)
                self.task_repo.update_status(task_id, "stopped")
                self._log_info_task(task_id, "任务已停止")
                return

            try:
                await self._process_single_file(task_id, collection_id, file_path, override)
            except Exception as e:
                self._log_err_task(task_id, f"Error processing {file_path}: {str(e)}")
            finally:
                stats.files_processed += 1
                await self.update_file_task_progress(task_id, stats)

        self.task_repo.mark_completed(task_id, True)
        self._log_info_task(task_id, "File ingestion completed")

    async def _process_single_file(self, task_id: str, collection_id: str, file_path: str, override: bool = True):
        """Process a single file and return chunk count (None if skipped)"""
        file_path_obj = Path(file_path)
        self._log_info_task(task_id, f"Processing: {file_path_obj.name}")

        # Get file metadata
        mime_type, _ = mimetypes.guess_type(file_path)
        file_uri = f"file://{file_path_obj.absolute()}"

        # Check if file already exists
        exists = await self._check_document_exists(collection_id, file_uri)
        if exists:
            if override:
                self._log_info_task(task_id, f"Overriding existing file: {file_path_obj.name}")
            else:
                self._log_info_task(task_id, f"Skipping duplicate file: {file_path_obj.name}")
                return None
        else:
            self._log_info_task(task_id, f"Processing new file: {file_path_obj.name}")

        # Process file content
        result = self.file_processor.process_file(file_path)

        # Check stop flag before LLM call
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self._log_info_task(task_id, f"Stopped before summarizing: {file_path_obj.name}")
            return

        self._log_info_task(task_id, f"Summarizing content for: {file_path_obj.name}")
        summary = self.llm_service.summarize_document(result.content) if result.success else ""

        if not result.success:
            self._log_err_task(task_id, f"Failed to process {file_path_obj.name}: {result.error}")
            await self._store_document(
                collection_id=collection_id,
                doc_page_uri=file_uri,
                doc_title=result.file_path,
                doc_content=result.content,
                doc_summary=summary,
                doc_mime_type=mime_type or "text/plain",
                doc_status="failed",
                doc_error_message=result.error,
                chunks=[],
                chunk_embeddings=[],
                source_task_id=task_id,
            )
            return

        # Check stop flag before chunking and embedding
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self._log_info_task(task_id, f"Stopped before chunking: {file_path_obj.name}")
            return

        doc_status = "indexed"
        error_message = None

        # chunk and embedding
        chunks = []
        chunk_embeddings = []
        if result.content:
            try:
                chunks = self.document_processor.process_file_content(file_path, result.content, result.file_type)
                texts = [chunk.content for chunk in chunks]
                chunk_embeddings = await self.llm_service.embed_documents(texts)
            except Exception as e:
                doc_status = "failed"
                error_message = f"Error processing chunks for {file_path_obj.name}: {str(e)}"
                self._log_err_task(task_id, error_message)

        # Check stop flag before persisting to database and vector store
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self._log_info_task(task_id, f"Stopped before persisting: {file_path_obj.name}")
            return

        # persist
        try:
            await self._store_document(
                collection_id=collection_id,
                doc_page_uri=file_uri,
                doc_title=result.file_path,
                doc_content=result.content,
                doc_summary=summary,
                doc_mime_type=mime_type or "text/plain",
                doc_status=doc_status,
                doc_error_message=error_message,
                chunks=chunks,
                chunk_embeddings=chunk_embeddings,
                source_task_id=task_id,
            )
        except Exception as e:
            self._log_err_task(task_id, f"Storage failed for {file_uri}: {str(e)}")

    async def _process_url_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process URL ingestion task: crawl-and-store incrementally → rewrite links → generate README"""
        self._log_info_task(task_id, "Starting URL ingestion")

        urls = input_params["urls"]
        recursive_prefix = input_params["recursive_prefix"]

        if not urls:
            raise ValueError("No URLs specified for ingestion")

        stats = UrlTaskStats()
        self.update_url_task_progress(task_id, stats)

        def progress_callback(current_url: str, completed: int, total: int) -> None:
            stats.urls_crawled = completed
            stats.urls_crawl_total = total
            stats.pages_total = max(stats.pages_total, total)
            self.update_url_task_progress(task_id, stats)
            self._log_info_task(task_id, f"Crawling page {completed + 1}/{total}: {current_url}")

        # When not overriding, skip URLs already indexed in DB for this collection.
        # Failed pages will be retried on the next run.
        existing_docs = self.doc_repo.get_by_collection(collection_id)
        skip_urls = {
            d.uri for d in existing_docs if d.uri
        }

        # Recover URLs discovered by previously crawled pages so that an
        # interrupted crawl does not lose newly-found links.
        recovered_urls: set[str] = set()
        indexed_docs = self.doc_repo.get_by_collection(collection_id, status="indexed")
        for doc in indexed_docs:
            if doc.html_content and doc.uri:
                links = self.web_crawler.extract_links_from_html(doc.html_content, doc.uri)
                for link in links:
                    if link in skip_urls:
                        continue
                    if recursive_prefix and not link.startswith(recursive_prefix):
                        continue
                    recovered_urls.add(link)

        if recovered_urls:
            self._log_info_task(task_id, f"Recovered {len(recovered_urls)} URLs from previously crawled pages")

        seed_urls = list(dict.fromkeys(urls + list(recovered_urls)))

        # Stream crawl results and process pages concurrently.
        # The synchronous crawler runs in a background thread so its
        # rate-limit sleeps and HTTP requests do not block the event loop.
        # Storage and LLM summarizing run on the loop in parallel.
        crawl_count = 0
        sem = asyncio.Semaphore(5)
        stats_lock = asyncio.Lock()

        async def process_bg(crawl_result: SimpleCrawlResult) -> None:
            async with sem:
                await self._process_single_page(task_id, collection_id, crawl_result)
            async with stats_lock:
                stats.pages_processed += 1
                self.update_url_task_progress(task_id, stats)

        pending_tasks: list[asyncio.Task] = []

        def _next_crawl_result(gen):
            try:
                return next(gen)
            except StopIteration:
                return None

        crawl_gen = self.web_crawler.crawl_recursive_stream(
            urls=seed_urls,
            recursive_prefix=recursive_prefix,
            skip_urls=skip_urls,
            progress_callback=progress_callback,
        )

        while True:
            # Check stop flag before fetching next crawl result
            if task_id in self._stop_flags:
                self._stop_flags.discard(task_id)
                self.task_repo.update_status(task_id, "stopped")
                self._log_info_task(task_id, "任务已停止")
                # Cancel pending background tasks
                for pt in pending_tasks:
                    pt.cancel()
                return

            crawl_result = await asyncio.to_thread(_next_crawl_result, crawl_gen)
            if crawl_result is None:
                break
            crawl_count += 1
            task = asyncio.create_task(process_bg(crawl_result))
            pending_tasks.append(task)

        if pending_tasks:
            await asyncio.gather(*pending_tasks)
        self._log_info_task(task_id, f"Incremental crawl/store completed: {crawl_count} pages processed in this run")

        # Phase 2: rewrite in-page links to local routes
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self.task_repo.update_status(task_id, "stopped")
            self._log_info_task(task_id, "任务已停止")
            return

        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        crawled_docs = [d for d in docs if d.uri and d.source_path and d.clean_html]
        stats.phase = "rewrite"
        stats.rewrite_total = len(crawled_docs)
        stats.rewrite_done = 0
        self.update_url_task_progress(task_id, stats)
        await self._rewrite_html_links(task_id, collection_id, stats)

        # Phase 3: generate AI README
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self.task_repo.update_status(task_id, "stopped")
            self._log_info_task(task_id, "任务已停止")
            return

        stats.phase = "readme"
        self.update_url_task_progress(task_id, stats)
        await self._generate_readme(task_id, collection_id, stats)

        self.task_repo.update_progress(task_id, 100)
        self.task_repo.mark_completed(task_id, True)
        self._log_info_task(task_id, "URL ingestion completed")

    async def _process_single_page(
        self, task_id: str, collection_id: str, crawl_result: SimpleCrawlResult
    ):
        """Store a single crawled page. No RAG chunking or embedding."""
        if not crawl_result.success:
            is_not_found = bool(
                crawl_result.error
                and ("404" in crawl_result.error or "Not Found" in crawl_result.error)
            )
            doc_status = "not_found" if is_not_found else "failed"
            if is_not_found:
                self._log_info_task(task_id, f"Page not found (404): {crawl_result.url}")
            else:
                self._log_err_task(task_id, f"Crawl failed for page: {crawl_result.url}")
            await self._store_crawled_page(
                collection_id=collection_id,
                url=crawl_result.url,
                title=crawl_result.title,
                content=crawl_result.content,
                html_content=crawl_result.html_content,
                clean_html=crawl_result.clean_html,
                summary="",
                doc_status=doc_status,
                error_message=crawl_result.error,
                source_task_id=task_id,
            )
            return

        page_url = crawl_result.url
        exists = await self._check_document_exists(collection_id, page_url)
        if exists:
            self._log_info_task(task_id, f"Skipping duplicate page: {page_url}")
            return
        else:
            self._log_info_task(task_id, f"Storing page: {page_url}")

        # Check stop flag before LLM call
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self._log_info_task(task_id, f"Stopped before summarizing: {page_url}")
            return

        self._log_info_task(task_id, f"Summarizing: {page_url}")
        if crawl_result.content:
            summary = await asyncio.to_thread(self.llm_service.summarize_document, crawl_result.content)
        else:
            summary = ""

        # Check stop flag before persisting
        if task_id in self._stop_flags:
            self._stop_flags.discard(task_id)
            self._log_info_task(task_id, f"Stopped before persisting: {page_url}")
            return

        try:
            await self._store_crawled_page(
                collection_id=collection_id,
                url=page_url,
                title=crawl_result.title,
                content=crawl_result.content,
                html_content=crawl_result.html_content,
                clean_html=crawl_result.clean_html,
                summary=summary,
                doc_status="indexed",
                error_message=None,
                source_task_id=task_id,
            )
        except Exception as e:
            self._log_err_task(task_id, f"Storage failed for {page_url}: {e}")

    async def _store_crawled_page(
        self,
        collection_id: str,
        url: str,
        title: str,
        content: str,
        html_content: str,
        clean_html: str,
        summary: str,
        doc_status: str,
        error_message: str | None,
        source_task_id: str | None = None,
    ):
        """Persist a crawled page to the database. No Chroma / no chunks."""
        from urllib.parse import urlparse as _urlparse

        # Remove existing record if any (override case)
        exist_doc = self.doc_repo.find_by_uri(collection_id, url)
        if exist_doc:
            assert exist_doc.id
            self.doc_chunk_repo.delete_by_document(exist_doc.id)
            self.doc_repo.delete_by_id(exist_doc.id)

        source_path = _urlparse(url).path or "/"

        doc_record = DocumentDTO(
            id=uuid.uuid4().hex,
            collection_id=collection_id,
            name=title or f"Page from {url}",
            uri=url,
            content=content,
            html_content=html_content,
            clean_html=clean_html,
            summary=summary,
            source_path=source_path,
            size_bytes=len(content.encode()) if content else 0,
            mime_type="text/markdown",
            chunk_count=0,
            status=doc_status,
            error_message=error_message,
            hash_md5=hashlib.md5(f"{url}:{title}:{content}".encode()).hexdigest(),
            source_task_id=source_task_id,
        )
        self.doc_repo.create_by_model(doc_record)

    @staticmethod
    def _canonicalize_page_url(url: str) -> str:
        """Canonical URL for page matching: drop query/fragment and trailing slash."""
        stripped, _ = urldefrag(url.strip())
        parsed = urlparse(stripped)
        if not parsed.scheme or not parsed.netloc:
            return stripped
        canonical = parsed._replace(query="", fragment="")
        return canonical.geturl().rstrip("/")

    @staticmethod
    def _canonicalize_asset_url(url: str) -> str:
        """Canonical URL for asset deduplication: keep query, drop fragment."""
        stripped, _ = urldefrag(url.strip())
        parsed = urlparse(stripped)
        if not parsed.scheme or not parsed.netloc:
            return stripped
        return parsed.geturl()

    @staticmethod
    def _source_path_to_page_rel_path(source_path: str) -> str:
        """Map URL source_path to local HTML path under pages/."""
        clean = source_path.split("?", 1)[0].split("#", 1)[0].strip().lstrip("/")
        if not clean:
            return "pages/index.html"

        suffix = Path(clean).suffix.lower()
        if suffix in {".html", ".htm"}:
            return f"pages/{clean}"
        return f"pages/{clean}.html"

    @staticmethod
    def _relative_link(from_rel_path: str, to_rel_path: str) -> str:
        from_dir = str(Path(from_rel_path).parent)
        rel = os.path.relpath(to_rel_path, start=from_dir)
        return rel.replace("\\", "/")

    @staticmethod
    def _should_skip_reference(value: str) -> bool:
        ref = value.strip().lower()
        return (
            not ref
            or ref.startswith("#")
            or ref.startswith("javascript:")
            or ref.startswith("mailto:")
            or ref.startswith("tel:")
            or ref.startswith("data:")
            or ref.startswith("blob:")
            or ref.startswith("ftp:")
        )

    @staticmethod
    def _domain_key(url: str) -> str:
        return urlparse(url).netloc.lower().replace(":", "_")

    @staticmethod
    def _guess_asset_category(asset_url: str, content_type: str) -> str:
        ct = content_type.lower()
        suffix = Path(urlparse(asset_url).path).suffix.lower()

        if ct.startswith("text/css") or suffix == ".css":
            return "css"
        if "javascript" in ct or suffix in {".js", ".mjs"}:
            return "js"
        if ct.startswith("image/") or suffix in {
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".bmp", ".avif",
        }:
            return "img"
        if ct.startswith("font/") or suffix in {".woff", ".woff2", ".ttf", ".otf", ".eot"}:
            return "fonts"
        if ct.startswith("audio/") or ct.startswith("video/"):
            return "media"
        return "misc"

    def _mirror_asset(
        self,
        asset_url: str,
        domain_dir: Path,
        asset_map: dict[str, str],
        failed_assets: set[str],
    ) -> str | None:
        """Download one static asset and return its local relative path."""
        canonical = self._canonicalize_asset_url(asset_url)

        logger.debug(f"Processing asset: {asset_url} (canonical: {canonical})")

        if canonical in asset_map:
            logger.debug(f"Asset {canonical} already in cache, returning: {asset_map[canonical]}")
            return asset_map[canonical]
        if canonical in failed_assets:
            logger.debug(f"Asset {canonical} failed previously, skipping")
            return None
        failed_assets.add(canonical)

        try:
            logger.debug(f"Downloading asset: {canonical}")
            response = self.web_crawler.session.get(canonical, timeout=30)
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to download asset {canonical}: {e}")
            return None

        content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
        logger.debug(f"Asset {canonical} content-type: {content_type}")

        if content_type.startswith("text/html"):
            logger.debug(f"Skipping HTML asset: {canonical}")
            return None

        suffix = Path(urlparse(canonical).path).suffix.lower()
        if not suffix:
            suffix = mimetypes.guess_extension(content_type) or ""
        if suffix == ".jpe":
            suffix = ".jpg"

        category = self._guess_asset_category(canonical, content_type)
        file_hash = hashlib.sha1(canonical.encode()).hexdigest()[:24]
        local_rel_path = f"assets/{category}/{file_hash}{suffix}"
        local_abs_path = domain_dir / local_rel_path
        local_abs_path.parent.mkdir(parents=True, exist_ok=True)

        logger.debug(f"Asset {canonical} will be saved to: {local_rel_path} (category: {category})")

        content_bytes = response.content
        if category == "css":
            logger.debug(f"Rewriting CSS references in: {canonical}")
            encoding = response.encoding or "utf-8"
            try:
                css_text = response.content.decode(encoding, errors="replace")
            except Exception:
                css_text = response.content.decode("utf-8", errors="replace")
            css_text = self._rewrite_css_references(
                css_text=css_text,
                base_url=canonical,
                current_rel_path=local_rel_path,
                domain_dir=domain_dir,
                asset_map=asset_map,
                failed_assets=failed_assets,
            )
            content_bytes = css_text.encode("utf-8")

        local_abs_path.write_bytes(content_bytes)
        asset_map[canonical] = local_rel_path
        failed_assets.discard(canonical)
        logger.info(f"Successfully mirrored asset: {canonical} -> {local_rel_path} ({len(content_bytes)} bytes)")
        return local_rel_path

    def _rewrite_css_references(
        self,
        css_text: str,
        base_url: str,
        current_rel_path: str,
        domain_dir: Path,
        asset_map: dict[str, str],
        failed_assets: set[str],
    ) -> str:
        """Rewrite CSS url(...) and @import references to local mirrored assets."""
        url_pattern = re.compile(r"url\((?P<inner>[^)]+)\)", flags=re.IGNORECASE)
        import_pattern = re.compile(
            r"@import\s+(?P<quote>['\"])(?P<ref>.+?)(?P=quote)",
            flags=re.IGNORECASE,
        )

        def replace_import(match: re.Match[str]) -> str:
            ref = match.group("ref").strip()
            if self._should_skip_reference(ref):
                return match.group(0)
            target_url = urljoin(base_url, ref)
            logger.debug(f"Processing @import: {ref} (resolved: {target_url})")
            local_rel = self._mirror_asset(target_url, domain_dir, asset_map, failed_assets)
            if not local_rel:
                logger.warning(f"Failed to mirror CSS import asset: {target_url}")
                return match.group(0)
            rewritten = self._relative_link(current_rel_path, local_rel)
            logger.info(f"Rewriting @import: {ref} -> {rewritten}")
            quote = match.group("quote")
            return f"@import {quote}{rewritten}{quote}"

        def replace_url(match: re.Match[str]) -> str:
            inner = match.group("inner").strip()
            quote = ""
            if (inner.startswith('"') and inner.endswith('"')) or (
                inner.startswith("'") and inner.endswith("'")
            ):
                quote = inner[0]
                inner = inner[1:-1].strip()
            if self._should_skip_reference(inner):
                return match.group(0)
            target_url = urljoin(base_url, inner)
            logger.debug(f"Processing CSS url(): {inner} (resolved: {target_url})")
            local_rel = self._mirror_asset(target_url, domain_dir, asset_map, failed_assets)
            if not local_rel:
                logger.warning(f"Failed to mirror CSS url() asset: {target_url}")
                return match.group(0)
            rewritten = self._relative_link(current_rel_path, local_rel)
            logger.debug(f"Rewriting CSS url(): {inner} -> {rewritten}")
            if quote:
                return f"url({quote}{rewritten}{quote})"
            return f"url({rewritten})"

        css_text = import_pattern.sub(replace_import, css_text)
        css_text = url_pattern.sub(replace_url, css_text)
        return css_text

    def _rewrite_srcset(
        self,
        srcset: str,
        page_url: str,
        page_rel_path: str,
        domain_dir: Path,
        asset_map: dict[str, str],
        failed_assets: set[str],
    ) -> str:
        """Rewrite each srcset URL to local mirrored assets."""
        rewritten_entries: list[str] = []
        changed = False

        for raw_entry in srcset.split(","):
            entry = raw_entry.strip()
            if not entry:
                continue
            parts = entry.split()
            ref = parts[0]
            if self._should_skip_reference(ref):
                rewritten_entries.append(entry)
                continue
            target_url = urljoin(page_url, ref)
            logger.debug(f"Processing srcset entry: {ref} (resolved: {target_url})")
            local_rel = self._mirror_asset(target_url, domain_dir, asset_map, failed_assets)
            if not local_rel:
                logger.warning(f"Failed to mirror srcset asset: {target_url}")
                rewritten_entries.append(entry)
                continue
            rel_ref = self._relative_link(page_rel_path, local_rel)
            descriptor = " ".join(parts[1:]).strip()
            rewritten_entries.append(f"{rel_ref} {descriptor}".strip())
            logger.debug(f"Rewriting srcset entry: {entry} -> {rel_ref} {descriptor}")
            changed = True

        if not changed:
            return srcset
        return ", ".join(rewritten_entries)

    @staticmethod
    def _render_markdown_frontmatter(source_url: str, title: str, markdown_content: str) -> str:
        escaped_title = title.replace("\\", "\\\\").replace('"', '\\"')
        escaped_url = source_url.replace("\\", "\\\\").replace('"', '\\"')
        crawled_at = datetime.now(timezone.utc).isoformat()
        return (
            f"---\n"
            f"source_url: \"{escaped_url}\"\n"
            f"title: \"{escaped_title}\"\n"
            f"crawled_at: \"{crawled_at}\"\n"
            f"---\n\n"
            f"{markdown_content or ''}"
        )

    async def _rewrite_html_links(self, task_id: str, collection_id: str, stats: UrlTaskStats):
        """Phase 2: mirror static assets and rewrite links to local relative paths."""
        from bs4 import BeautifulSoup

        self._log_info_task(task_id, "Mirroring static assets and rewriting HTML links...")
        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        crawled_docs = [d for d in docs if d.uri and d.source_path and d.clean_html]
        if not crawled_docs:
            self._log_info_task(task_id, "No crawled HTML pages found, skipping link rewriting")
            return

        logger.info(f"Starting link rewriting for {len(crawled_docs)} crawled pages")

        page_rel_map: dict[str, str] = {}
        for doc in crawled_docs:
            assert doc.uri and doc.source_path
            page_rel_map[self._canonicalize_page_url(doc.uri)] = self._source_path_to_page_rel_path(doc.source_path)

        cache_root = Path(self.config.get_crawl_cache_dir())
        rewritten_pages = 0
        total_assets = 0
        total_failed_assets = 0

        docs_by_domain: dict[str, list[DocumentDTO]] = {}
        for doc in crawled_docs:
            assert doc.uri
            docs_by_domain.setdefault(self._domain_key(doc.uri), []).append(doc)

        for domain_key, domain_docs in docs_by_domain.items():
            domain_dir = cache_root / domain_key
            (domain_dir / "pages").mkdir(parents=True, exist_ok=True)
            (domain_dir / "assets").mkdir(parents=True, exist_ok=True)
            (domain_dir / "manifests").mkdir(parents=True, exist_ok=True)

            asset_map: dict[str, str] = {}
            failed_assets: set[str] = set()
            pages_manifest: dict[str, str] = {}

            for doc in domain_docs:
                if not doc.id or not doc.clean_html or not doc.uri or not doc.source_path:
                    continue

                canonical_page_url = self._canonicalize_page_url(doc.uri)
                page_rel_path = page_rel_map[canonical_page_url]
                pages_manifest[canonical_page_url] = page_rel_path

                logger.debug(f"Processing page: {doc.uri} -> {page_rel_path}")

                soup = BeautifulSoup(doc.clean_html, "lxml")
                changed = False

                for a_tag in soup.find_all("a", href=True):
                    raw_href = str(a_tag.get("href", "")).strip()
                    if self._should_skip_reference(raw_href):
                        continue
                    resolved = urljoin(doc.uri, raw_href)
                    target_rel = page_rel_map.get(self._canonicalize_page_url(resolved))
                    if not target_rel:
                        continue
                    new_href = self._relative_link(page_rel_path, target_rel)
                    if new_href != raw_href:
                        logger.info(f"Rewriting page link: {raw_href} -> {new_href} (resolves to {resolved})")
                        a_tag["href"] = new_href
                        changed = True

                for script_tag in soup.find_all("script", src=True):
                    raw_src = str(script_tag.get("src", "")).strip()
                    if self._should_skip_reference(raw_src):
                        continue
                    resolved = urljoin(doc.uri, raw_src)
                    logger.debug(f"Found script asset: {raw_src} (resolved: {resolved})")
                    local_rel = self._mirror_asset(resolved, domain_dir, asset_map, failed_assets)
                    if not local_rel:
                        logger.warning(f"Failed to mirror script asset: {resolved}")
                        continue
                    new_src = self._relative_link(page_rel_path, local_rel)
                    if new_src != raw_src:
                        logger.info(f"Rewriting script src: {raw_src} -> {new_src}")
                        script_tag["src"] = new_src
                        changed = True

                for media_tag in soup.find_all(
                    ["img", "source", "video", "audio", "track", "embed", "iframe", "input"]
                ):
                    for attr in ("src", "poster", "data-src"):
                        if not media_tag.has_attr(attr):
                            continue
                        raw_value = str(media_tag.get(attr, "")).strip()
                        if self._should_skip_reference(raw_value):
                            continue
                        resolved = urljoin(doc.uri, raw_value)
                        logger.debug(f"Found media asset: {raw_value} (resolved: {resolved})")
                        local_rel = self._mirror_asset(resolved, domain_dir, asset_map, failed_assets)
                        if not local_rel:
                            logger.warning(f"Failed to mirror media asset: {resolved}")
                            continue
                        new_value = self._relative_link(page_rel_path, local_rel)
                        if new_value != raw_value:
                            logger.info(f"Rewriting {attr} for <{media_tag.name}>: {raw_value} -> {new_value}")
                            media_tag[attr] = new_value
                            changed = True

                    if media_tag.has_attr("srcset"):
                        raw_srcset = str(media_tag.get("srcset", "")).strip()
                        if raw_srcset:
                            logger.debug(f"Found srcset: {raw_srcset}")
                            rewritten_srcset = self._rewrite_srcset(
                                srcset=raw_srcset,
                                page_url=doc.uri,
                                page_rel_path=page_rel_path,
                                domain_dir=domain_dir,
                                asset_map=asset_map,
                                failed_assets=failed_assets,
                            )
                            if rewritten_srcset != raw_srcset:
                                logger.info(f"Rewriting srcset: {raw_srcset} -> {rewritten_srcset}")
                                media_tag["srcset"] = rewritten_srcset
                                changed = True

                for link_tag in soup.find_all("link", href=True):
                    raw_href = str(link_tag.get("href", "")).strip()
                    if self._should_skip_reference(raw_href):
                        continue
                    resolved = urljoin(doc.uri, raw_href)
                    logger.debug(f"Found link asset: {raw_href} (resolved: {resolved})")
                    local_rel = self._mirror_asset(resolved, domain_dir, asset_map, failed_assets)
                    if not local_rel:
                        logger.warning(f"Failed to mirror link asset: {resolved}")
                        continue
                    new_href = self._relative_link(page_rel_path, local_rel)
                    if new_href != raw_href:
                        logger.info(f"Rewriting link href: {raw_href} -> {new_href}")
                        link_tag["href"] = new_href
                        changed = True

                for style_tag in soup.find_all("style"):
                    css_text = style_tag.string
                    if not css_text:
                        continue
                    logger.debug("Found style tag, rewriting CSS references")
                    rewritten_css = self._rewrite_css_references(
                        css_text=css_text,
                        base_url=doc.uri,
                        current_rel_path=page_rel_path,
                        domain_dir=domain_dir,
                        asset_map=asset_map,
                        failed_assets=failed_assets,
                    )
                    if rewritten_css != css_text:
                        logger.info("Rewriting style tag content with CSS references")
                        style_tag.string.replace_with(rewritten_css)
                        changed = True

                for styled_tag in soup.find_all(style=True):
                    inline_css = str(styled_tag.get("style", ""))
                    if not inline_css:
                        continue
                    logger.debug(f"Found inline style on <{getattr(styled_tag, 'name', 'tag')}>: {inline_css}")
                    rewritten_inline = self._rewrite_css_references(
                        css_text=inline_css,
                        base_url=doc.uri,
                        current_rel_path=page_rel_path,
                        domain_dir=domain_dir,
                        asset_map=asset_map,
                        failed_assets=failed_assets,
                    )
                    if rewritten_inline != inline_css:
                        logger.info(f"Rewriting inline style on <{getattr(styled_tag, 'name', 'tag')}>: {inline_css} -> {rewritten_inline}")
                        styled_tag["style"] = rewritten_inline
                        changed = True

                rewritten_html = str(soup)
                if changed:
                    self.doc_repo.update(doc.id, clean_html=rewritten_html)
                    rewritten_pages += 1

                stats.rewrite_done += 1
                self.update_url_task_progress(task_id, stats)

                page_file = domain_dir / page_rel_path
                page_file.parent.mkdir(parents=True, exist_ok=True)
                page_file.write_text(rewritten_html, encoding="utf-8")

                if page_rel_path.endswith(".html"):
                    markdown_rel_path = page_rel_path[:-5] + ".md"
                else:
                    markdown_rel_path = f"{page_rel_path}.md"
                markdown_file = domain_dir / markdown_rel_path
                markdown_file.parent.mkdir(parents=True, exist_ok=True)
                markdown_file.write_text(
                    self._render_markdown_frontmatter(
                        source_url=doc.uri,
                        title=doc.name or "",
                        markdown_content=doc.content or "",
                    ),
                    encoding="utf-8",
                )

            (domain_dir / "manifests" / "pages.json").write_text(
                json.dumps(pages_manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (domain_dir / "manifests" / "assets.json").write_text(
                json.dumps(asset_map, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (domain_dir / "manifests" / "failed_assets.json").write_text(
                json.dumps(sorted(failed_assets), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            total_assets += len(asset_map)
            total_failed_assets += len(failed_assets)
            logger.info(f"Domain {domain_key} complete: {len(asset_map)} assets mirrored, {len(failed_assets)} failed")

        summary_msg = (
            f"Link rewriting complete: {rewritten_pages} pages updated, "
            f"{total_assets} assets mirrored, {total_failed_assets} assets failed"
        )
        logger.info(summary_msg)
        self._log_info_task(
            task_id,
            summary_msg
        )

    @staticmethod
    def _detect_source_language(pages: list[dict]) -> str:
        """Detect if page titles are primarily Chinese or English."""
        total_chars = 0
        chinese_chars = 0
        for p in pages:
            title = p.get("title", "")
            for char in title:
                if "\u4e00" <= char <= "\u9fff":
                    chinese_chars += 1
                if char.isalpha():
                    total_chars += 1
        if total_chars == 0:
            return "unknown"
        ratio = chinese_chars / total_chars
        if ratio > 0.5:
            return "zh"
        return "en"

    async def _generate_readme(self, task_id: str, collection_id: str, stats: UrlTaskStats):
        """Phase 4: generate AI README navigation guide and categories data."""
        self._log_info_task(task_id, "Generating AI README...")
        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        crawled = [d for d in docs if d.source_path]

        if not crawled:
            self._log_info_task(task_id, "No crawled pages found, skipping README generation")
            return

        pages = [{"path": d.source_path, "title": d.name or ""} for d in crawled]

        try:
            import json as json_lib
            import re

            source_language = self._detect_source_language(pages)
            self._log_info_task(task_id, f"Detected source language: {source_language}")

            raw = await self.llm_service.generate_readme(pages, source_language)

            # Strip markdown fences if LLM wraps the response
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
                cleaned = re.sub(r"\n?```$", "", cleaned)
                cleaned = cleaned.strip()

            parsed = json_lib.loads(cleaned)
            readme_content = parsed.get("readme", "")
            categories = parsed.get("categories", [])
            categories_json = json_lib.dumps(categories, ensure_ascii=False)

            # For English source, also extract Chinese translations
            readme_content_zh = parsed.get("readme_zh", "") if source_language == "en" else ""
            categories_json_zh = ""
            if source_language == "en" and categories:
                categories_zh = []
                for cat in categories:
                    cat_zh = {
                        "category": cat.get("category_zh", cat.get("category", "")),
                        "pages": []
                    }
                    for page in cat.get("pages", []):
                        cat_zh["pages"].append({
                            "path": page.get("path", ""),
                            "title": page.get("title_zh", page.get("title", "")),
                            "description": page.get("description_zh", page.get("description", ""))
                        })
                    categories_zh.append(cat_zh)
                categories_json_zh = json_lib.dumps(categories_zh, ensure_ascii=False)

            # Update collection with README and source language
            await self.collection_service.update_readme(
                collection_id,
                readme_content=readme_content,
                categories_json=categories_json,
                readme_content_zh=readme_content_zh,
                categories_json_zh=categories_json_zh,
                source_language=source_language
            )

            # Update document name_translated for English source documents
            if source_language == "en":
                title_zh_map = {}
                for cat in categories:
                    for page in cat.get("pages", []):
                        path = page.get("path", "")
                        title_zh = page.get("title_zh", "")
                        if path and title_zh:
                            title_zh_map[path] = title_zh

                for doc in crawled:
                    if doc.source_path and doc.source_path in title_zh_map:
                        self.doc_repo.update(doc.id, name_translated=title_zh_map[doc.source_path])

            self._log_info_task(task_id, "README stored successfully")
        except Exception as e:
            self._log_err_task(task_id, f"README generation failed: {e}")

    def close(self):
        """Close connections and cleanup resources"""
        if self.running:
            asyncio.create_task(self.stop_workers())
        self.llm_service.close()
        logger.info("TaskService resources closed")
