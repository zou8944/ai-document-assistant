"""
Task management service for async operations.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

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
            progress = json.loads(task.stats) if task.stats else {}
            stats = json.loads(task.input_params) if task.input_params else {}
        except json.JSONDecodeError:
            progress = {}
            stats = {}

        return TaskResponse(
            task_id=task.id or "",
            type=task.type or "",
            status=task.status or "",
            progress={"percentage": task.progress_percentage, **progress},
            stats=stats,
            collection_id=task.collection_id or "",
            created_at=task.created_at.isoformat() if task.created_at else "",
            updated_at=task.updated_at.isoformat() if task.updated_at else "",
            error=task.error_message
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

    async def create_task(self, task_type: str, collection_id: str, input_params: dict[str, Any]) -> TaskResponse:
        """Create a new task"""
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

    async def get_task_logs(self, task_id: str, limit: int, offset: int = 0) -> list[TaskLogDTO]:
        return self.task_log_repo.list_by_task(task_id=task_id, limit=limit, offset=offset)

    async def cancel_task(self, task_id: str) -> bool:
        return self.task_repo.mark_cancelled(task_id)

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
        if stats.pages_total == 0:
            if stats.urls_crawl_total == 0:
                progress = 0
            else:
                progress = stats.urls_crawled * 50 // stats.urls_crawl_total
        else:
            progress = 50 + (stats.pages_processed * 50 // stats.pages_total)
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
        chunk_embeddings
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
            hash_md5=hashlib.md5(f"{doc_page_uri}:{doc_title}:{doc_content}".encode()).hexdigest()
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
                chunk_embeddings=[]
            )
            return

        doc_status= "indexed"
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
                chunk_embeddings=chunk_embeddings
            )
        except Exception as e:
            self._log_err_task(task_id, f"Storage failed for {file_uri}: {str(e)}")

    async def _process_url_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process URL ingestion task with full web crawling integration"""
        self._log_info_task(task_id, "Starting URL ingestion")

        # Get parameters from input
        urls = input_params["urls"]
        exclude_urls = input_params["exclude_urls"]
        recursive_prefix = input_params["recursive_prefix"]
        max_depth = input_params["max_depth"]
        override = input_params["override"]

        if not urls:
            raise ValueError("No URLs specified for ingestion")

        # init zero stats
        stats = UrlTaskStats()

        self.update_url_task_progress(task_id, stats)

        # Crawl this url, tracking progress asynchronously
        def progress_callback(current_url, completed, total):
            stats.urls_crawled = completed
            stats.urls_crawl_total = total
            self.update_url_task_progress(task_id, stats)
            self._log_info_task(task_id, f"Crawling page {completed + 1}/{total}: {current_url}")

        crawl_results = self.web_crawler.crawl_recursive(
            urls, exclude_urls, recursive_prefix, max_depth, progress_callback=progress_callback
        )
        successful_results = [r for r in crawl_results if r.success]

        # Process each crawled page
        for crawl_result in successful_results:
            await self._process_single_page(task_id, collection_id, crawl_result, override)
            stats.pages_total += 1
            self.update_url_task_progress(task_id, stats)

        self.task_repo.mark_completed(task_id, True)
        self._log_info_task(task_id, "URL ingestion completed")

    async def _process_single_page(self, task_id: str, collection_id: str, crawl_result: SimpleCrawlResult, override: bool):
        """Process a single crawled page and return status"""

        self._log_info_task(task_id, f"Summarizing content for: {crawl_result.url}")
        summary = self.llm_service.summarize_document(crawl_result.content) if crawl_result.success else ""

        # if crawl fail, create a document with status "failed"
        if not crawl_result.success:
            self._log_err_task(task_id, f"Crawl failed for page: {crawl_result.url}")
            await self._store_document(
                collection_id=collection_id,
                doc_page_uri=crawl_result.url,
                doc_title=crawl_result.title,
                doc_content=crawl_result.content,
                doc_summary=summary,
                doc_mime_type="text/html",
                doc_status="failed",
                doc_error_message=crawl_result.error,
                chunks=[],
                chunk_embeddings=[]
            )
            return

        page_url = crawl_result.url
        self._log_info_task(task_id, f"Processing page: {page_url}")

        # Check if document already exists
        exists = await self._check_document_exists(collection_id, page_url)
        if exists:
            if override:
                self._log_info_task(task_id, f"Overriding existing page: {page_url}")
            else:
                self._log_info_task(task_id, f"Skipping duplicate page: {page_url}")
                return
        else:
            self._log_info_task(task_id, f"New page detected: {page_url}")

        doc_status= "indexed"
        error_message = None

        # Chunk and embedding
        chunks = []
        chunk_embeddings = []
        if crawl_result.content:
            try:
                chunks = self.document_processor.process_web_content(page_url, crawl_result.content, crawl_result.title)
                texts = [chunk.content for chunk in chunks]
                chunk_embeddings = await self.llm_service.embed_documents(texts)
            except Exception as e:
                doc_status = "failed"
                error_message = f"Embedding failed: {str(e)}"
                self._log_err_task(task_id, error_message)

        # persist
        try:
            await self._store_document(
                collection_id=collection_id,
                doc_page_uri=page_url,
                doc_title=crawl_result.title,
                doc_content=crawl_result.content,
                doc_summary=summary,
                doc_mime_type="text/markdown",
                doc_status=doc_status,
                doc_error_message=error_message,
                chunks=chunks,
                chunk_embeddings=chunk_embeddings
            )
        except Exception as e:
            self._log_err_task(task_id, f"Storage failed for {page_url}: {str(e)}")

    def close(self):
        """Close connections and cleanup resources"""
        if self.running:
            asyncio.create_task(self.stop_workers())
        self.llm_service.close()
        logger.info("TaskService resources closed")
