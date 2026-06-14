"""
Task management service for async operations.
"""

import asyncio
import hashlib
import json
import logging
import mimetypes
import queue
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

from langchain_core.output_parsers import StrOutputParser

from crawler.manifest_store import ManifestStore, _domain_key
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
from services.llm_service import LLMConsecutiveFailureError, LLMService
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

    def __init__(self, config, collection_service: CollectionService, llm_service: LLMService,
                 document_index=None, keyword_index=None):
        """Initialize task service"""
        self.config = config

        self.collection_service = collection_service
        self.document_index = document_index
        self.keyword_index = keyword_index

        # Task queue and workers
        self.task_queue: queue.Queue = queue.Queue(maxsize=100)
        self.executor = ThreadPoolExecutor(max_workers=5)
        self.running = False
        self._stop_flags: set[str] = set()  # Task IDs marked for stopping

        # Per-task lifecycle tracking (written by worker thread, read by API thread)
        self._worker_loop: asyncio.AbstractEventLoop | None = None  # shared worker event loop
        self._task_events: dict[str, asyncio.Event] = {}            # task_id -> cancel event
        self._active_tasks: dict[str, asyncio.Task] = {}            # task_id -> running asyncio task
        self._task_lock = threading.Lock()  # guards the dicts above

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
        self.manifest_store = ManifestStore(self.config)

        # LLM service
        self.llm_service = llm_service

        logger.info("TaskService initialized successfully")

    def _check_task_cancelled(self, task_id: str) -> bool:
        """Check if a task has been asked to stop.  Safe to call from any thread."""
        with self._task_lock:
            event = self._task_events.get(task_id)
        if event and event.is_set():
            return True
        return task_id in self._stop_flags

    async def _apply_stop(self, task_id: str, pending_tasks: list[asyncio.Task] | None = None):
        """Centralised stop handling: cancel pending async tasks, cleanup tracking state."""
        if pending_tasks:
            for pt in pending_tasks:
                pt.cancel()
            await asyncio.gather(*pending_tasks, return_exceptions=True)
        # The status was already set to "stopped" by stop_task(); just clean up
        with self._task_lock:
            self._stop_flags.discard(task_id)
            self._task_events.pop(task_id, None)
            self._active_tasks.pop(task_id, None)
        self._log_info_task(task_id, "任务已停止，工作线程清理完成")

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
        recursive_prefixes = input_params.get("recursive_prefixes", [])

        return TaskResponse(
            task_id=task.id or "",
            type=task.type or "",
            status=task.status or "",
            stage=task.stage,
            progress=task.progress_percentage or 0,
            stats=input_params,
            collection_id=task.collection_id or "",
            created_at=task.created_at.isoformat() if task.created_at else "",
            updated_at=task.updated_at.isoformat() if task.updated_at else "",
            started_at=task.started_at.isoformat() if task.started_at else None,
            completed_at=task.completed_at.isoformat() if task.completed_at else None,
            urls=urls,
            recursive_prefix=recursive_prefix,
            recursive_prefixes=recursive_prefixes,
            error=task.error_message,
            title=input_params.get("title")
        )

    def _log_info_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "info", message)

    def _log_debug_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "debug", message)

    def _log_err_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "error", message)

    def _update_stage(self, task_id: str, stage: str) -> None:
        """Update task processing stage and log it."""
        self.task_repo.update_stage(task_id, stage)
        self._log_info_task(task_id, f"Stage: {stage}")

    def _log_task(self, task_id: str, level: str, message: str):
        self.task_log_repo.add_log(task_id, level, message, None)
        logger.log(getattr(logging, level.upper()), message, exc_info=(level == "error"))

    async def _generate_task_title(
        self,
        urls: list[str],
        recursive_prefix: str,
        existing_titles: list[str],
        url_configs: list[dict] | None = None,
    ) -> str:
        """Generate a Chinese title for a URL ingestion task using LLM."""
        # Multi-config: short circuit with a generic title
        if url_configs and len(url_configs) > 1:
            return f"多源抓取 ({len(url_configs)} 个配置)"

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
            chain = self.llm_service.crawl_llm | StrOutputParser()
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
            url_configs = input_params.get("url_configs", [])
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

            title = await self._generate_task_title(urls, recursive_prefix, existing_titles, url_configs)
            input_params["title"] = title
            logger.info(f"Generated task title: {title}")

        created_task = self.task_repo.create_by_model(TaskDTO(
            type=task_type,
            collection_id=collection_id,
            input_params=json.dumps(input_params),
            status="pending"
        ))

        # Try direct submission for immediate start; fall back to queue
        assert created_task.id
        loop = self._worker_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._process_task_with_exception(created_task.id), loop)
        else:
            self.task_queue.put(created_task.id)

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
        """Stop a running task. Returns immediately; worker cleans up in background."""
        task = self.task_repo.get_by_id(task_id)
        if not task or task.status != "processing":
            return False

        # Signal every layer immediately
        self._stop_flags.add(task_id)
        self.web_crawler.stop()
        with self._task_lock:
            event = self._task_events.get(task_id)
            active = self._active_tasks.get(task_id)
            loop = self._worker_loop

        if event:
            event.set()

        # Ask the worker event-loop to cancel the running asyncio.Task
        if active and loop and loop.is_running():
            loop.call_soon_threadsafe(active.cancel)

        # Immediately mark as stopped so the UI reflects the change right away
        self.task_repo.update_status(task_id, "stopped")
        self._log_info_task(task_id, "任务已停止")
        return True

    async def restart_task(self, task_id: str) -> TaskResponse:
        """Restart a completed or stopped task, resuming from last stage if available."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            raise HTTPNotFoundException(f"Task {task_id} not found")
        if task.status not in ("success", "failed", "stopped"):
            from exception import HTTPBadRequestException
            raise HTTPBadRequestException("只能重跑已完成或已停止的任务")

        # Clear any stale stop flags from a previous run
        with self._task_lock:
            self._stop_flags.discard(task_id)
            self._task_events.pop(task_id, None)
            self._active_tasks.pop(task_id, None)

        # Delete old logs before restarting
        self.task_log_repo.delete_by_task(task_id)
        # Keep stage info for resume support
        self.task_repo.reset_task(task_id, keep_stage=True)

        # Submit directly to the worker event-loop for immediate start
        loop = self._worker_loop
        if loop and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._process_task_with_exception(task_id), loop)
        else:
            self.task_queue.put(task_id)

        logger.info(f"Restarted task {task_id} from stage: {task.stage}")
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

    async def delete_task(self, task_id: str, cleanup_resources: bool = False) -> bool:
        """Permanently delete a task and its logs.

        When cleanup_resources is True, also delete all documents, vectors
        and crawl cache produced by this task.
        """
        task = self.task_repo.get_by_id(task_id)
        if not task:
            return False
        if task.status == "processing":
            from exception import HTTPBadRequestException
            raise HTTPBadRequestException("不能删除正在执行的任务")

        # Stop any async tracking for this task
        with self._task_lock:
            self._stop_flags.discard(task_id)
            self._task_events.pop(task_id, None)
            self._active_tasks.pop(task_id, None)

        collection_id = task.collection_id

        if cleanup_resources and collection_id:
            # 1. Delete all documents produced by this task
            docs = self.doc_repo.get_by_task(task_id)
            if docs:
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
            if task.type == "ingest_urls":
                self._delete_crawl_cache(collection_id)

            # 3. Regenerate collection summary if documents remain
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

        # 4. Delete task logs, then the task itself
        self.task_log_repo.delete_by_task(task_id)
        self.task_repo.delete(task_id)

        logger.info(f"Deleted task {task_id} (cleanup_resources={cleanup_resources})")
        return True

    def _delete_crawl_cache(self, collection_id: str) -> None:
        """Delete pages/ and assets/ from crawl cache, preserving manifests/."""
        import shutil
        cache_root = Path(self.config.get_crawl_cache_dir())
        docs = self.doc_repo.get_by_collection(collection_id)
        domains = set()
        for doc in docs:
            if doc.uri and doc.uri.startswith("http"):
                from crawler.manifest_store import _domain_key
                domains.add(_domain_key(doc.uri))
        for domain in domains:
            domain_dir = cache_root / domain
            for subdir in ("pages", "assets"):
                target = domain_dir / subdir
                if target.exists():
                    shutil.rmtree(target)
                    logger.info(f"Deleted crawl cache subdir: {target}")

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
            elif current_task.status == "stopped":
                yield {
                    "event": "stopped",
                    "data": json.dumps({})
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
            self.task_queue.put(task.id)
            logger.info(f"Re-queued processing task {task.id}")

    async def start_workers(self):
        """Start background task workers"""
        if self.running:
            logger.warning("Workers already running")
            return

        self.running = True
        # Re-queue any pending/processing tasks from previous sessions
        await self.requeue_processing_task()
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
                # queue.Queue.get is blocking; use to_thread to avoid blocking the event loop
                try:
                    task_id = await asyncio.to_thread(
                        self.task_queue.get, timeout=1.0
                    )
                except queue.Empty:
                    continue

                logger.info(f"Worker {worker_name} processing task {task_id}")

                # Process the task
                await self._process_task_with_exception(task_id)

                # Mark task as done in queue
                self.task_queue.task_done()

            except asyncio.CancelledError:
                logger.info(f"Worker {worker_name} cancelled")
                break
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}", exc_info=True)
                continue

        logger.info(f"Task worker {worker_name} stopped")

    async def _process_task_with_exception(self, task_id: str):
        try:
            await self._process_task(task_id)
        except asyncio.CancelledError:
            # Task was cancelled by stop_task — status already set to "stopped"
            current = self.task_repo.get_by_id(task_id)
            if not current or current.status != "stopped":
                self.task_repo.update_status(task_id, "stopped")
        except LLMConsecutiveFailureError as e:
            logger.error(f"Task {task_id} aborted: {e}")
            self.task_repo.mark_completed(task_id, success=False, error_message=str(e))
        except Exception as e:
            logger.error(f"Error processing task {task_id}: {e}", exc_info=True)
            self.task_repo.mark_completed(task_id, success=False, error_message=str(e))

    async def _process_task(self, task_id: str):
        """Process a single task — owns the per-task lifecycle state."""
        task = self.task_repo.get_by_id(task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return

        # Skip already-completed tasks to avoid duplicate execution
        # (e.g. when a task is re-queued while already running)
        if task.status == "success":
            logger.info(f"Task {task_id} already completed, skipping")
            return

        # Reset LLM failure counter at task start
        self.llm_service.reset_failure_counter()

        # Reset crawler stop state so a restarted task can run
        self.web_crawler.clear_stop()

        # Register per-task cancellation infrastructure so stop_task() can reach us
        cancel_event = asyncio.Event()
        with self._task_lock:
            self._worker_loop = asyncio.get_event_loop()
            self._task_events[task_id] = cancel_event
            self._active_tasks[task_id] = asyncio.current_task()  # type: ignore[assignment]

        self.task_repo.mark_started(task_id)

        try:
            assert task.input_params
            input_params = json.loads(task.input_params)

            assert task.collection_id
            if task.type == "ingest_files":
                await self._process_file_ingestion(task_id, task.collection_id, input_params)
            elif task.type == "ingest_urls":
                await self._process_url_ingestion(task_id, task.collection_id, input_params)
            elif task.type == "reindex_collection":
                await self._process_reindex_collection(task_id, task.collection_id)
            elif task.type == "regenerate_readme":
                await self._process_regenerate_readme(task_id, task.collection_id, input_params)
            elif task.type == "recategorize":
                await self._process_recategorize(task_id, task.collection_id, input_params)
            else:
                error_msg = f"Unknown task type: {task.type}"
                logger.error(error_msg)
                self.task_repo.mark_completed(task_id, False, error_msg)
                return

            # Final stop check
            if self._check_task_cancelled(task_id):
                await self._apply_stop(task_id)
                return

            # Write current index_version to collection on success
            from services.collection_service import compute_index_version
            self.collection_service.collection_repo.update(task.collection_id, index_version=compute_index_version())

            # Refresh collection summary on success
            await self.collection_service.refresh_collection_summary(task.collection_id)
        finally:
            # Always clean up tracking state
            with self._task_lock:
                self._task_events.pop(task_id, None)
                self._active_tasks.pop(task_id, None)

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

        # Index document for chat retrieval
        if doc_status == "indexed":
            if self.document_index:
                self.document_index.index_document(
                    document_id=doc_id,
                    keywords=[],
                    total_tokens=len(doc_content) // 4,
                )
            if self.keyword_index:
                self.keyword_index.index_document(
                    document_id=doc_id,
                    title=doc_title,
                    summary=doc_summary,
                    content=doc_content,
                    document_name=doc_title or doc_page_uri,
                )

        return len(chunk_records)

    async def _process_reindex_collection(self, task_id: str, collection_id: str):
        """Re-index all documents in a collection with current chunking parameters."""
        self._log_info_task(task_id, "Starting collection re-indexing")

        # Get all indexed documents for this collection
        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        indexed_docs = [doc for doc in docs if doc.status == "indexed" and doc.content]
        total = len(indexed_docs)

        if not indexed_docs:
            self._log_info_task(task_id, "No indexed documents to re-index")
            return

        self._log_info_task(task_id, f"Re-indexing {total} documents with current chunking parameters")

        # Delete all existing chunks and vectors for this collection
        chroma_collection = await self.chroma_manager.get_collection(collection_id)
        for doc in indexed_docs:
            if doc.id:
                try:
                    if chroma_collection:
                        chroma_collection.delete(where={"document_id": doc.id})
                    self.doc_chunk_repo.delete_by_document(doc.id)
                except Exception as e:
                    logger.warning(f"Failed to clean up existing data for doc {doc.id}: {e}")

        # Re-chunk, re-embed, and re-store each document
        completed = 0
        for doc in indexed_docs:
            if self._check_task_cancelled(task_id):
                return

            assert doc.id and doc.content
            title = doc.name or doc.uri or ""

            try:
                # Re-chunk with current parameters
                chunks = self.document_processor.process_file_content(
                    doc.uri or title, doc.content, doc.mime_type or "text"
                )
                texts = [chunk.content for chunk in chunks]

                if texts:
                    chunk_embeddings = await self.llm_service.embed_documents(texts)
                else:
                    chunk_embeddings = []

                # Re-store (reuse existing document ID to keep references intact)
                await self._store_document(
                    collection_id=collection_id,
                    doc_page_uri=doc.uri or f"file://reindex/{doc.id}",
                    doc_title=title,
                    doc_content=doc.content,
                    doc_summary=doc.summary or "",
                    doc_mime_type=doc.mime_type or "text/plain",
                    doc_status="indexed",
                    doc_error_message=None,
                    chunks=chunks,
                    chunk_embeddings=chunk_embeddings,
                    source_task_id=task_id,
                )

                completed += 1
                progress = int(completed / total * 100)
                self.task_repo.update_progress(task_id, progress)
                self._log_info_task(task_id, f"Re-indexed ({completed}/{total}): {title}")

            except Exception as e:
                self._log_err_task(task_id, f"Failed to re-index {title}: {e}")

        self._log_info_task(task_id, f"Re-indexing complete: {completed}/{total} documents")

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
            if self._check_task_cancelled(task_id):
                await self._apply_stop(task_id)
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
        if self._check_task_cancelled(task_id):
            self._log_info_task(task_id, f"Stopped before summarizing: {file_path_obj.name}")
            return

        self._log_info_task(task_id, f"Processing content for: {file_path_obj.name}")
        summary = ""

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
        if self._check_task_cancelled(task_id):
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
        if self._check_task_cancelled(task_id):
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
        """Process URL ingestion task with stage support for resume.

        Stages:
        - crawl: Crawl and store pages
        - vectorize: Generate embeddings for documents
        - rewrite: Rewrite in-page links to local routes
        - readme: Generate AI README and categories
        """
        self._log_info_task(task_id, "Starting URL ingestion")

        # Get task to check for resume stage
        task = self.task_repo.get_by_id(task_id)
        resume_stage = task.stage if task else None
        if resume_stage:
            self._log_info_task(task_id, f"Resuming from stage: {resume_stage}")

        # Support multi-prefix url_configs (new) or legacy urls+recursive_prefix
        url_configs = input_params.get("url_configs")
        if not url_configs:
            # Legacy format fallback
            urls = input_params.get("urls", [])
            recursive_prefix = input_params.get("recursive_prefix", "")
            url_configs = [{"seed_urls": urls, "recursive_prefix": recursive_prefix}]

        # Validate at least one config has URLs
        has_urls = any(cfg.get("seed_urls") for cfg in url_configs)
        if not has_urls:
            raise ValueError("No URLs specified for ingestion")

        stats = UrlTaskStats()
        self.update_url_task_progress(task_id, stats)

        # Determine stages dynamically based on user options
        categorize_mode = input_params.get("categorize_mode", "auto")
        generate_readme = input_params.get("generate_readme", True)
        active_stages = ["crawl", "vectorize"]
        if categorize_mode != "skip":
            active_stages.append("categorize")
        if generate_readme and categorize_mode != "skip":
            active_stages.append("readme")
        STAGES = active_stages
        start_index = STAGES.index(resume_stage) if resume_stage in STAGES else 0

        # ========================================
        # Stage: crawl
        # ========================================
        if start_index <= STAGES.index("crawl"):
            self._update_stage(task_id, "crawl")

            existing_docs = self.doc_repo.get_by_collection(collection_id)
            skip_urls = {d.uri for d in existing_docs if d.uri}

            crawl_count = 0
            sem = asyncio.Semaphore(5)
            stats_lock = asyncio.Lock()

            async def process_bg(crawl_result: SimpleCrawlResult) -> None:
                async with sem:
                    await self._process_single_page(task_id, collection_id, crawl_result)
                async with stats_lock:
                    stats.pages_processed += 1
                    self.update_url_task_progress(task_id, stats)

            def _next_crawl_result(gen):
                try:
                    return next(gen)
                except StopIteration:
                    return None

            for config_idx, config in enumerate(url_configs):
                if self._check_task_cancelled(task_id):
                    return

                urls = config.get("seed_urls", [])
                prefix = config.get("recursive_prefix", "")
                prefixes = config.get("recursive_prefixes", []) or ([prefix] if prefix else [])
                if not urls:
                    continue

                config_label = f"[{config_idx + 1}/{len(url_configs)}]" if len(url_configs) > 1 else ""
                prefix_repr = ", ".join(prefixes) if prefixes else "无"
                self._log_info_task(task_id, f"Crawling {config_label} prefixes=[{prefix_repr}], seeds={len(urls)}")

                # Recover URLs from manifest (links discovered in a previous interrupted run)
                seed_domain = _domain_key(urls[0]) if urls else ""
                recovered_urls: set[str] = set()
                if seed_domain:
                    recovered_urls = self.manifest_store.recover_links(
                        seed_domain, skip_urls, prefixes,
                    )
                if recovered_urls:
                    self._log_info_task(task_id, f"Recovered {len(recovered_urls)} URLs for prefixes [{prefix_repr}]")

                seed_urls = list(dict.fromkeys(urls + list(recovered_urls)))

                def progress_callback(current_url: str, completed: int, total: int, _label: str = config_label) -> None:
                    stats.urls_crawled = completed
                    stats.urls_crawl_total = total
                    stats.pages_total = max(stats.pages_total, total)
                    self.update_url_task_progress(task_id, stats)
                    self._log_info_task(task_id, f"Crawling {_label} page {completed + 1}/{total}: {current_url}")

                pending_tasks: list[asyncio.Task] = []

                crawl_gen = self.web_crawler.crawl_recursive_stream(
                    urls=seed_urls,
                    recursive_prefixes=prefixes,
                    skip_urls=skip_urls,
                    progress_callback=progress_callback,
                )

                loop_aborted = False
                try:
                    while True:
                        if self._check_task_cancelled(task_id):
                            loop_aborted = True
                            await self._apply_stop(task_id, pending_tasks)
                            return

                        try:
                            crawl_result = await asyncio.to_thread(_next_crawl_result, crawl_gen)
                        except RuntimeError:
                            loop_aborted = True
                            await self._apply_stop(task_id, pending_tasks)
                            return
                        if crawl_result is None:
                            break
                        crawl_count += 1
                        # Add crawled URL to skip_urls so cross-config dedup works
                        skip_urls.add(crawl_result.url)
                        t = asyncio.create_task(process_bg(crawl_result))
                        pending_tasks.append(t)
                except Exception:
                    loop_aborted = True
                    await self._apply_stop(task_id, pending_tasks)
                    raise
                finally:
                    if not loop_aborted and pending_tasks:
                        await asyncio.gather(*pending_tasks)

                # Deduplicate manifest after each config completes
                if seed_domain:
                    self.manifest_store.merge_and_dedup(seed_domain)

                self._log_info_task(task_id, f"Crawl {config_label} completed")

            self._log_info_task(task_id, f"All crawls completed: {crawl_count} pages processed")

        # ========================================
        # Stage: vectorize
        # ========================================
        if start_index <= STAGES.index("vectorize"):
            if self._check_task_cancelled(task_id):
                await self._apply_stop(task_id)
                return

            self._update_stage(task_id, "vectorize")

            unvectorized = [
                d for d in self.doc_repo.get_by_collection(collection_id, status="indexed")
                if (d.chunk_count or 0) == 0 and d.content
            ]
            if unvectorized:
                self._log_info_task(task_id, f"Vectorizing {len(unvectorized)} documents")
                for doc in unvectorized:
                    try:
                        chunks = self.document_processor.process_web_content(doc.uri or "", doc.content)
                        texts = [chunk.content for chunk in chunks]
                        chunk_embeddings = await self.llm_service.embed_documents(texts)
                        collection = await self.chroma_manager.get_collection(collection_id)
                        assert doc.id
                        vector_ids = []
                        embedding_list = []
                        metadatas_list = []
                        documents_list = []
                        for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
                            vector_id = f"{doc.id}_chunk_{i}"
                            chunk_record = DocumentChunkDTO(
                                document_id=doc.id,
                                collection_id=collection_id,
                                chunk_index=i,
                                content_preview=chunk.content[:200] if chunk.content else "",
                                vector_id=vector_id,
                                content_hash=hashlib.md5(chunk.content.encode()).hexdigest(),
                                chunk_metadata=json.dumps(chunk.metadata)
                            )
                            self.doc_chunk_repo.create_by_model(chunk_record)
                            vector_ids.append(vector_id)
                            embedding_list.append(embedding)
                            metadatas_list.append({
                                "document_id": doc.id,
                                "document_name": doc.name or "",
                                "document_uri": doc.uri or "",
                                "collection_id": collection_id,
                                "chunk_index": i,
                            })
                            documents_list.append(chunk.content)
                        if vector_ids and collection:
                            collection.add(ids=vector_ids, embeddings=embedding_list, metadatas=metadatas_list, documents=documents_list)
                        self.doc_repo.update(doc.id, chunk_count=len(chunks))
                    except Exception as e:
                        self._log_err_task(task_id, f"Vectorization failed for {doc.uri}: {e}")
            else:
                self._log_info_task(task_id, "No documents need vectorization")

        # ========================================
        # Stage: categorize
        # ========================================
        if "categorize" in STAGES and start_index <= STAGES.index("categorize"):
            if self._check_task_cancelled(task_id):
                await self._apply_stop(task_id)
                return

            self._update_stage(task_id, "categorize")
            # Incremental categorize if collection already has categories
            collection = self.collection_service.collection_repo.get_by_id(collection_id)
            if collection and collection.categories_json:
                await self._categorize_incremental(task_id, collection_id, categorize_mode)
            else:
                await self._categorize_collection(task_id, collection_id, categorize_mode)
                self._mark_categorized(collection_id)

        # ========================================
        # Stage: readme
        # ========================================
        if "readme" in STAGES and start_index <= STAGES.index("readme"):
            if self._check_task_cancelled(task_id):
                await self._apply_stop(task_id)
                return

            self._update_stage(task_id, "readme")

            stats.phase = "readme"
            self.update_url_task_progress(task_id, stats)
            await self._generate_readme(task_id, collection_id, stats)

        # Update collection preferences
        self.collection_service.collection_repo.update(
            collection_id,
            categorize_mode=categorize_mode,
            generate_readme=generate_readme,
        )

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
        if self._check_task_cancelled(task_id):
            self._log_info_task(task_id, f"Stopped before summarizing: {page_url}")
            return

        self._log_info_task(task_id, f"Processing: {page_url}")
        summary = ""

        # Check stop flag before persisting
        if self._check_task_cancelled(task_id):
            self._log_info_task(task_id, f"Stopped before persisting: {page_url}")
            return

        # chunk and embed
        chunks = []
        chunk_embeddings = []
        if crawl_result.content:
            try:
                chunks = self.document_processor.process_web_content(page_url, crawl_result.content)
                texts = [chunk.content for chunk in chunks]
                chunk_embeddings = await self.llm_service.embed_documents(texts)
            except Exception as e:
                self._log_err_task(task_id, f"Chunking/embedding failed for {page_url}: {e}")

        try:
            await self._store_crawled_page(
                collection_id=collection_id,
                url=page_url,
                title=crawl_result.title,
                content=crawl_result.content,
                summary=summary,
                doc_status="indexed",
                error_message=None,
                source_task_id=task_id,
                chunks=chunks,
                chunk_embeddings=chunk_embeddings,
            )
            # Record discovered links for checkpoint resume
            self.manifest_store.record_links(page_url, crawl_result.links)
        except Exception as e:
            self._log_err_task(task_id, f"Storage failed for {page_url}: {e}")

    async def _store_crawled_page(
        self,
        collection_id: str,
        url: str,
        title: str,
        content: str,
        summary: str,
        doc_status: str,
        error_message: str | None,
        source_task_id: str | None = None,
        chunks: list | None = None,
        chunk_embeddings: list | None = None,
    ):
        """Persist a crawled page to the database, with optional ChromaDB vectors."""
        from urllib.parse import urlparse as _urlparse

        # Remove existing record if any (override case)
        exist_doc = self.doc_repo.find_by_uri(collection_id, url)
        if exist_doc:
            assert exist_doc.id
            self.doc_chunk_repo.delete_by_document(exist_doc.id)
            self.doc_repo.delete_by_id(exist_doc.id)
            # Also delete vectors from ChromaDB
            try:
                collection = await self.chroma_manager.get_collection(collection_id)
                if collection:
                    collection.delete(where={"document_id": exist_doc.id})
            except Exception:
                pass

        source_path = _urlparse(url).path or "/"

        doc_record = DocumentDTO(
            id=uuid.uuid4().hex,
            collection_id=collection_id,
            name=title or f"Page from {url}",
            uri=url,
            content=content,
            summary=summary,
            source_path=source_path,
            size_bytes=len(content.encode()) if content else 0,
            mime_type="text/markdown",
            chunk_count=len(chunks) if chunks else 0,
            status=doc_status,
            error_message=error_message,
            hash_md5=hashlib.md5(f"{url}:{title}:{content}".encode()).hexdigest(),
            source_task_id=source_task_id,
        )
        self.doc_repo.create_by_model(doc_record)

        if chunks and chunk_embeddings and len(chunks) == len(chunk_embeddings):
            collection = await self.chroma_manager.get_collection(collection_id)
            vector_ids = []
            embedding_list = []
            metadatas = []
            documents = []
            doc_id = doc_record.id
            for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
                vector_id = f"{doc_id}_chunk_{i}"
                chunk_record = DocumentChunkDTO(
                    document_id=doc_id,
                    collection_id=collection_id,
                    chunk_index=i,
                    content_preview=chunk.content[:200] if chunk.content else "",
                    vector_id=vector_id,
                    content_hash=hashlib.md5(chunk.content.encode()).hexdigest(),
                    chunk_metadata=json.dumps(chunk.metadata)
                )
                self.doc_chunk_repo.create_by_model(chunk_record)
                vector_ids.append(vector_id)
                embedding_list.append(embedding)
                metadatas.append({
                    "document_id": doc_id,
                    "document_name": title,
                    "document_uri": url,
                    "collection_id": collection_id,
                    "chunk_index": i,
                })
                documents.append(chunk.content)
            if vector_ids and collection:
                collection.add(ids=vector_ids, embeddings=embedding_list, metadatas=metadatas, documents=documents)

        # Index document for chat retrieval
        if doc_status == "indexed":
            if self.document_index:
                self.document_index.index_document(
                    document_id=doc_record.id,
                    keywords=[],
                    total_tokens=len(content) // 4 if content else 0,
                )
            if self.keyword_index:
                self.keyword_index.index_document(
                    document_id=doc_record.id,
                    title=title,
                    summary=summary,
                    content=content or "",
                    document_name=title or url,
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

    @staticmethod
    @staticmethod
    def _longest_common_prefix(paths: list[str]) -> list[str]:
        """Find the longest common path prefix (list of segments).

        For ["/docs/sdk/ios/ui", "/docs/sdk/android/ui"] returns ["docs", "sdk"].
        For ["/guide/intro", "/api/ref"] returns [].
        """
        if not paths:
            return []

        split_paths = []
        for p in paths:
            norm = p.strip("/")
            split_paths.append(norm.split("/") if norm else [])

        if not split_paths:
            return []

        prefix: list[str] = []
        for segments in zip(*split_paths):
            if len(set(segments)) == 1:
                prefix.append(segments[0])
            else:
                break
        return prefix

    @staticmethod
    def _build_trie(pages: list[dict]) -> dict:
        """Build a trie from pages using their relative paths (after LCP stripping)."""
        trie: dict = {}
        for page in pages:
            path = page.get("path", "")
            norm = path.strip("/")
            segments = norm.split("/") if norm else []
            node = trie
            for seg in segments:
                if seg not in node:
                    node[seg] = {"_pages": [], "_children": {}}
                node = node[seg]["_children"]
            # Attach page at the terminal node's parent's _pages
            # Walk back to attach at the correct level
            node_ref = trie
            for seg in segments[:-1]:
                node_ref = node_ref[seg]["_children"]
            if segments:
                node_ref[segments[-1]]["_pages"].append(page)
            else:
                # Root-level page (empty path)
                if "__root_pages__" not in trie:
                    trie["__root_pages__"] = []
                trie["__root_pages__"].append(page)
        return trie

    @classmethod
    def _prune_trie(cls, trie: dict, min_group_size: int, depth: int = 0, max_depth: int = 3, index_page: dict | None = None) -> list[dict]:
        """Prune trie into nested CategoryNode list.

        - Merge single-child chains (e.g. sdk -> ios -> ui becomes "sdk/ios/ui")
        - Nodes with < min_group_size pages are merged into "Other" (or "详情" if index_page is set)
        - Depth capped at max_depth
        - index_page: if set (LCP matched a page path exactly), that page sits at category level
          and remaining pages go into a "详情" subcategory instead of "Other"
        """
        nodes: list[dict] = []

        for key, subtree in trie.items():
            if key == "__root_pages__":
                continue

            direct_pages = subtree.get("_pages", [])
            child_trie = subtree.get("_children", {})

            # Merge single-child chains: if this node has no direct pages
            # and exactly one child, concatenate names
            if not direct_pages and len(child_trie) == 1:
                child_key = next(iter(child_trie))
                merged_name = f"{key}/{child_key}"
                merged_subtree = child_trie[child_key]
                # Continue merging if the merged node also has no pages and one child
                while not merged_subtree.get("_pages", []) and len(merged_subtree.get("_children", {})) == 1:
                    next_key = next(iter(merged_subtree["_children"]))
                    merged_name = f"{merged_name}/{next_key}"
                    merged_subtree = merged_subtree["_children"][next_key]
                # Build a virtual subtree for the merged chain
                virtual = {merged_name: merged_subtree}
                child_nodes = cls._prune_trie(virtual, min_group_size, depth, max_depth)
                if child_nodes:
                    nodes.extend(child_nodes)
                continue

            if depth >= max_depth:
                # At max depth, collect all pages under this node
                all_pages = list(direct_pages)
                cls._collect_all_pages(child_trie, all_pages)
                if all_pages:
                    nodes.append({"category": key, "pages": all_pages, "children": []})
                continue

            # Recurse into children
            child_nodes = cls._prune_trie(child_trie, min_group_size, depth + 1, max_depth)

            if direct_pages or child_nodes:
                nodes.append({
                    "category": key,
                    "pages": direct_pages,
                    "children": child_nodes,
                })

        # Merge "Other" pages: small groups and root-level pages
        other_pages: list[dict] = []
        root_pages = trie.get("__root_pages__", [])
        other_pages.extend(root_pages)

        final_nodes: list[dict] = []
        for node in nodes:
            total = cls._count_pages(node)
            if total < min_group_size:
                other_pages.extend(cls._flatten_pages(node))
            else:
                final_nodes.append(node)

        if other_pages:
            if index_page is not None:
                # Index page sits at category level; remaining pages form "详情"
                final_nodes.append({
                    "category": "详情",
                    "pages": other_pages,
                    "children": [],
                })
            else:
                final_nodes.append({"category": "Other", "pages": other_pages, "children": []})

        return final_nodes

    @staticmethod
    def _collect_all_pages(trie: dict, result: list[dict]) -> None:
        """Recursively collect all pages from a trie subtree."""
        for key, subtree in trie.items():
            if key == "__root_pages__":
                result.extend(subtree)
                continue
            result.extend(subtree.get("_pages", []))
            child_trie = subtree.get("_children", {})
            if child_trie:
                TaskService._collect_all_pages(child_trie, result)

    @staticmethod
    def _count_pages(node: dict) -> int:
        """Count total pages in a nested CategoryNode (including children)."""
        count = len(node.get("pages", []))
        for child in node.get("children", []):
            count += TaskService._count_pages(child)
        return count

    @staticmethod
    def _flatten_pages(node: dict) -> list[dict]:
        """Collect all pages from a nested CategoryNode (including children)."""
        pages = list(node.get("pages", []))
        for child in node.get("children", []):
            pages.extend(TaskService._flatten_pages(child))
        return pages

    @classmethod
    def _build_nested_path_groups(cls, pages: list[dict], min_group_size: int = 3) -> list[dict]:
        """
        Cluster pages by URL path prefix with nested multi-level grouping.

        Algorithm:
        1. Find longest common path prefix (LCP), strip it
        2. If a page's path exactly matches LCP, extract it as "index page"
        3. Build trie from remaining relative paths
        4. Prune trie: merge single-child chains, collapse small groups, cap depth at 3
        """
        if not pages:
            return []

        paths = [p.get("path", "") for p in pages]
        lcp_segments = cls._longest_common_prefix(paths)
        lcp_str = "/" + "/".join(lcp_segments) if lcp_segments else ""

        # Detect index page: a page whose path exactly matches the LCP
        # Only meaningful when there are other pages to organize under it
        index_page: dict | None = None
        remaining_pages: list[dict] = []
        if len(pages) > 1:
            for page in pages:
                if page["path"].strip("/") == lcp_str.strip("/") and not index_page:
                    index_page = page
                else:
                    remaining_pages.append(page)

        work_pages = remaining_pages if index_page else pages

        # Strip LCP from each page's path to get relative paths
        offset = len(lcp_segments)
        pages_with_rel: list[dict] = []
        for page in work_pages:
            norm = page["path"].strip("/")
            segments = norm.split("/") if norm else []
            rel_segments = segments[offset:]
            rel_path = "/".join(rel_segments)
            pages_with_rel.append({**page, "_rel_path": rel_path})

        # Build trie using relative paths
        trie: dict = {}
        for page in pages_with_rel:
            rel = page["_rel_path"]
            segments = rel.split("/") if rel else []
            node = trie
            for seg in segments:
                if seg not in node:
                    node[seg] = {"_pages": [], "_children": {}}
                node = node[seg]["_children"]
            # Attach page at terminal node
            if segments:
                parent = trie
                for seg in segments[:-1]:
                    parent = parent[seg]["_children"]
                parent[segments[-1]]["_pages"].append(page)
            else:
                if "__root_pages__" not in trie:
                    trie["__root_pages__"] = []
                trie["__root_pages__"].append(page)

        # Prune trie into nested groups
        groups = cls._prune_trie(trie, min_group_size, index_page=index_page)

        # If index page was extracted, wrap trie results in a parent category
        if index_page:
            clean_index = {k: v for k, v in index_page.items() if k != "_rel_path"}
            cat_name = lcp_segments[-1] if lcp_segments else "Root"
            groups = [{"category": cat_name, "pages": [clean_index], "children": groups}]

        # Clean up _rel_path from pages in output
        def clean_pages(nodes: list[dict]) -> list[dict]:
            result = []
            for node in nodes:
                clean_node = {
                    "category": node["category"],
                    "pages": [{k: v for k, v in p.items() if k != "_rel_path"} for p in node.get("pages", [])],
                    "children": clean_pages(node.get("children", [])),
                }
                result.append(clean_node)
            return result

        return clean_pages(groups)

    def _log_groups(self, groups: list[dict], task_id: str, indent: int = 0) -> None:
        """Log nested group structure for debugging."""
        prefix = "  " * indent
        for g in groups:
            count = self._count_pages(g)
            child_count = len(g.get("children", []))
            if child_count > 0:
                self._log_info_task(task_id, f"{prefix}Group '{g['category']}': {count} pages, {child_count} sub-groups")
                self._log_groups(g.get("children", []), task_id, indent + 1)
            else:
                self._log_info_task(task_id, f"{prefix}Group '{g['category']}': {count} pages")

    @staticmethod
    def _collect_category_names(groups: list[dict]) -> list[str]:
        """Collect all category names from nested structure."""
        names: list[str] = []
        for g in groups:
            names.append(g["category"])
            names.extend(TaskService._collect_category_names(g.get("children", [])))
        return names

    async def _refine_with_ai(self, path_groups: list[dict], pages: list[dict], task_id: str) -> list[dict]:
        """Use AI to refine path-based classification.

        Passes the path grouping result as context to the LLM, asking it to
        merge overly granular groups, split overly large ones, and improve naming.
        """
        # Build a summary of the path groups for the AI
        def summarize_groups(groups: list[dict], indent: int = 0) -> list[str]:
            lines: list[str] = []
            prefix = "  " * indent
            for g in groups:
                count = self._count_pages(g)
                children = g.get("children", [])
                if children:
                    lines.append(f"{prefix}{g['category']}/ ({count} pages, {len(children)} sub-groups):")
                    lines.extend(summarize_groups(children, indent + 1))
                else:
                    sample = [p["title"] for p in g.get("pages", [])[:3]]
                    sample_str = ", ".join(sample)
                    lines.append(f"{prefix}{g['category']}/ ({count} pages) — e.g. {sample_str}")
            return lines

        groups_summary = "\n".join(summarize_groups(path_groups))

        prompt = f"""You are refining a documentation classification that was generated by URL path analysis.

Current path-based groups:
{groups_summary}

Total pages: {len(pages)}

Instructions:
1. If some groups are too granular (few pages), merge them with related parent or sibling groups
2. If some groups are too large (>20 pages), consider splitting them into meaningful sub-groups
3. Improve category names to be more descriptive if the path segments are unclear (e.g., "sdk" -> "SDK", "ref" -> "Reference")
4. Keep the hierarchical structure — use "children" for sub-groups
5. Maximum 3 levels of nesting
6. Every page must be in exactly one group
7. Pages that don't fit anywhere go in "Other"

Return ONLY a JSON array in this exact format:
[
  {{
    "category": "Group Name",
    "pages": [
      {{"id": "page_id", "path": "/path", "title": "Title"}}
    ],
    "children": [
      {{
        "category": "Sub Group",
        "pages": [...],
        "children": []
      }}
    ]
  }}
]"""

        self._log_info_task(task_id, f"Sending path groups to AI for refinement ({len(groups_summary)} chars)...")
        raw = await self.llm_service._invoke_crawl_llm(prompt, max_tokens=self.config.llm.max_tokens)

        cleaned = raw.strip()
        if cleaned.startswith("```"):
            import re
            cleaned = re.sub(r"^```(?:json)?\n?", "", cleaned)
            cleaned = re.sub(r"\n?```$", "", cleaned)
            cleaned = cleaned.strip()

        try:
            import json as json_lib
            result = json_lib.loads(cleaned)
            if isinstance(result, list) and len(result) > 0:
                # Validate coverage: ensure all pages are accounted for
                all_ids = {p["id"] for p in pages}
                covered_ids: set[str] = set()

                def collect_ids(nodes: list[dict]) -> None:
                    for n in nodes:
                        for p in n.get("pages", []):
                            if "id" in p:
                                covered_ids.add(p["id"])
                        collect_ids(n.get("children", []))

                collect_ids(result)
                missing = all_ids - covered_ids
                if missing:
                    self._log_info_task(task_id, f"AI refinement missing {len(missing)} pages, falling back to path groups")
                    return path_groups
                self._log_info_task(task_id, f"AI refinement produced {len(result)} top-level groups")
                return result
        except Exception as e:
            self._log_err_task(task_id, f"AI refinement failed: {e}, using path groups")

        return path_groups

    @staticmethod
    def _evaluate_path_quality(groups: list[dict], total_pages: int) -> tuple[bool, str]:
        """Evaluate whether path-based classification is good enough.

        Checks three dimensions:
        - Coverage: non-"Other" page ratio >= 70%
        - Group count: 3-15 groups
        - Balance: largest group < 50% of total pages

        Returns (passed, reason).
        """
        if total_pages == 0:
            return False, "no pages"

        non_other_count = 0
        group_counts: list[int] = []

        for g in groups:
            count = TaskService._count_pages(g)
            if g["category"] != "Other":
                non_other_count += count
                group_counts.append(count)

        coverage = non_other_count / total_pages if total_pages > 0 else 0
        num_groups = len(group_counts)
        max_group = max(group_counts) if group_counts else 0
        max_ratio = max_group / total_pages if total_pages > 0 else 0

        reasons: list[str] = []
        passed = True

        if coverage < 0.7:
            passed = False
            reasons.append(f"coverage {coverage:.0%} < 70%")
        if num_groups < 3:
            passed = False
            reasons.append(f"only {num_groups} groups (need >= 3)")
        if num_groups > 15:
            passed = False
            reasons.append(f"too many groups: {num_groups} > 15")
        if max_ratio >= 0.5:
            passed = False
            reasons.append(f"largest group {max_ratio:.0%} >= 50%")

        if not reasons:
            return True, f"OK: {num_groups} groups, coverage {coverage:.0%}, max group {max_ratio:.0%}"
        return passed, "; ".join(reasons)

    async def _categorize_collection(self, task_id: str, collection_id: str, categorize_mode: str = "auto"):
        """Categorize pages and store results for later README generation.

        categorize_mode:
        - "auto": path-first, AI refine if quality is poor
        - "path_only": path classification only, no LLM
        - "ai_only": AI classification only
        - "skip": no categorization
        """
        self._log_info_task(task_id, "Categorizing collection pages...")
        docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        crawled = [d for d in docs if d.source_path]

        if not crawled:
            self._log_info_task(task_id, "No crawled pages found, skipping categorization")
            return

        pages = [{"id": d.id, "path": d.source_path, "title": d.name or ""} for d in crawled]
        import json as json_lib

        source_language = self._detect_source_language(pages)
        self._log_info_task(task_id, f"Detected source language: {source_language}")

        # Normalize legacy mode names
        if categorize_mode == "path_prefix":
            categorize_mode = "auto"

        groups: list[dict] = []

        if categorize_mode == "path_only":
            # Path-only: no LLM calls
            self._log_info_task(task_id, "Categorizing pages by path prefix (nested)...")
            groups = self._build_nested_path_groups(pages)
            self._log_info_task(task_id, f"Built {len(groups)} nested path groups from {len(pages)} pages")
            self._log_groups(groups, task_id)

        elif categorize_mode == "ai_only":
            # AI-only classification
            self._log_info_task(task_id, "Categorizing pages with AI...")
            groups = await self.llm_service.categorize_pages(pages)
            # Wrap flat AI result into nested format
            groups = [{"category": g["category"], "pages": g["pages"], "children": []} for g in groups]
            self._log_info_task(task_id, f"Built {len(groups)} AI groups from {len(pages)} pages")
            self._log_groups(groups, task_id)

            # Reorder by complexity
            self._log_info_task(task_id, "Ordering categories by complexity...")
            flat_for_order = [{"category": g["category"], "pages": g["pages"]} for g in groups]
            ordered_flat = await self.llm_service.order_categories_by_complexity(flat_for_order)
            # Re-apply ordering to nested structure
            order_map = {g["category"]: g["pages"] for g in ordered_flat}
            for g in groups:
                if g["category"] in order_map:
                    g["pages"] = order_map[g["category"]]
            self._log_info_task(task_id, f"Categories reordered: {[g['category'] for g in groups]}")

        else:  # "auto" (default)
            # Step 1: Path classification
            self._log_info_task(task_id, "Categorizing pages by path prefix (nested)...")
            path_groups = self._build_nested_path_groups(pages)
            self._log_info_task(task_id, f"Built {len(path_groups)} nested path groups from {len(pages)} pages")
            self._log_groups(path_groups, task_id)

            # Step 2: Evaluate quality
            passed, reason = self._evaluate_path_quality(path_groups, len(pages))
            self._log_info_task(task_id, f"Path quality check: {'PASS' if passed else 'FAIL'} — {reason}")

            if passed:
                groups = path_groups
                self._log_info_task(task_id, "Using path-based classification")
            else:
                # AI refine: pass path result as hint
                self._log_info_task(task_id, "Path classification insufficient, refining with AI...")
                groups = await self._refine_with_ai(path_groups, pages, task_id)

        # Translate if English source
        category_names_zh: dict[str, str] = {}
        page_titles_zh: dict[str, str] = {}

        if source_language == "en":
            # Collect flat category names for translation
            flat_cat_names = self._collect_category_names(groups)
            try:
                self._log_info_task(task_id, "Translating category names...")
                category_names_zh = await self.llm_service.translate_category_names(flat_cat_names)
                self._log_info_task(task_id, f"Category names translated: {len(category_names_zh)}")
            except Exception as e:
                self._log_err_task(task_id, f"Category name translation failed: {e}")

            try:
                self._log_info_task(task_id, f"Translating all {len(pages)} page titles...")
                page_titles_zh = await self.llm_service.translate_all_page_titles(pages)
                self._log_info_task(task_id, f"Page titles translated: {len(page_titles_zh)}")
            except Exception as e:
                self._log_err_task(task_id, f"Page title translation failed: {e}")

        # Step 4: Build categories JSON (recursive for nested structures)
        def build_category_json(nodes: list[dict], is_zh: bool = False) -> list[dict]:
            result = []
            for g in nodes:
                cat_name = g["category"]
                if is_zh:
                    cat_name = category_names_zh.get(cat_name, cat_name)
                cat_pages = []
                for p in g.get("pages", []):
                    path = p["path"]
                    title = p["title"]
                    if is_zh:
                        title = page_titles_zh.get(path, title)
                    cat_pages.append({"path": path, "title": title, "description": ""})
                children = build_category_json(g.get("children", []), is_zh)
                result.append({
                    "category": cat_name,
                    "pages": cat_pages,
                    "children": children,
                })
            return result

        categories_for_json = build_category_json(groups, is_zh=False)
        categories_zh_for_json = build_category_json(groups, is_zh=True) if source_language == "en" else []

        categories_json = json_lib.dumps(categories_for_json, ensure_ascii=False)
        categories_json_zh = json_lib.dumps(categories_zh_for_json, ensure_ascii=False) if source_language == "en" else ""

        # Step 5: Store category data and source_language (readme_content will be filled later)
        try:
            await self.collection_service.update_readme(
                collection_id,
                readme_content="",  # will be filled in readme stage
                categories_json=categories_json,
                readme_content_zh="",
                categories_json_zh=categories_json_zh,
                source_language=source_language
            )
        except Exception as e:
            self._log_err_task(task_id, f"Failed to persist categories: {e}")
            return

        # Step 6: Update document name_translated for English source documents
        if source_language == "en":
            for doc in crawled:
                if doc.source_path and doc.source_path in page_titles_zh:
                    self.doc_repo.update(doc.id, name_translated=page_titles_zh[doc.source_path])

        self._log_info_task(task_id, f"Categorization completed: {len(groups)} groups")

    def _mark_categorized(self, collection_id: str) -> None:
        """Mark all indexed documents in a collection as categorized."""
        count = self.doc_repo.mark_categorized(collection_id)
        logger.info(f"Marked {count} documents as categorized in {collection_id}")

    async def _categorize_incremental(self, task_id: str, collection_id: str, categorize_mode: str = "auto"):
        """Incrementally categorize: only process new (uncategorized) documents, merge with existing."""
        # Normalize legacy mode
        if categorize_mode == "path_prefix":
            categorize_mode = "auto"

        # Path-based modes: just rebuild from scratch (path classification is fast, no LLM cost)
        if categorize_mode in ("path_only", "auto"):
            self._log_info_task(task_id, f"Mode '{categorize_mode}': rebuilding categories from all docs")
            await self._categorize_collection(task_id, collection_id, categorize_mode)
            self._mark_categorized(collection_id)
            return

        self._log_info_task(task_id, "Starting incremental categorization...")

        all_docs = self.doc_repo.get_by_collection(collection_id, exclude_statuses=["not_found"])
        new_docs = [d for d in all_docs if d.source_path and not d.categorized_at]
        existing_categorized = [d for d in all_docs if d.source_path and d.categorized_at]

        if not new_docs:
            self._log_info_task(task_id, "No new documents to categorize, skipping")
            return

        if not existing_categorized:
            # First categorization — use full flow
            self._log_info_task(task_id, "No existing categorized docs, running full categorization")
            await self._categorize_collection(task_id, collection_id, categorize_mode)
            self._mark_categorized(collection_id)
            return

        self._log_info_task(task_id, f"Incremental: {len(new_docs)} new, {len(existing_categorized)} existing")

        # Get existing categories
        collection = self.collection_service.collection_repo.get_by_id(collection_id)
        if not collection or not collection.categories_json:
            self._log_info_task(task_id, "No existing categories found, running full categorization")
            await self._categorize_collection(task_id, collection_id, categorize_mode)
            self._mark_categorized(collection_id)
            return

        old_categories = json.loads(collection.categories_json)
        old_categories_zh = json.loads(collection.categories_json_zh) if collection.categories_json_zh else None

        # Build new page records
        new_page_records = [
            {"id": d.id, "path": d.source_path, "title": d.name or ""}
            for d in new_docs
        ]

        # Step 1: Merge new pages into existing categories
        self._log_info_task(task_id, "Merging new pages into existing categories...")
        merged = await self.llm_service.merge_categories(
            existing_categories=old_categories,
            new_pages=new_page_records,
        )
        self._log_info_task(task_id, f"Merge produced {len(merged)} categories")

        # Step 2: Optimize merged categories
        all_page_records = [
            {"id": d.id, "path": d.source_path, "title": d.name or ""}
            for d in all_docs if d.source_path
        ]
        self._log_info_task(task_id, "Optimizing merged categories...")
        optimized = await self.llm_service.optimize_categories(
            categories=merged,
            all_pages=all_page_records,
        )
        self._log_info_task(task_id, f"Optimization produced {len(optimized)} categories")

        # Step 3: Handle Chinese translation for English source
        source_language = collection.source_language or "en"
        if source_language == "en" and old_categories_zh:
            self._log_info_task(task_id, "Merging Chinese categories...")
            merged_zh = await self.llm_service.merge_categories(
                existing_categories=old_categories_zh,
                new_pages=new_page_records,
            )
            optimized_zh = await self.llm_service.optimize_categories(
                categories=merged_zh,
                all_pages=all_page_records,
            )
            # Translate page titles for new docs
            try:
                page_titles_zh = await self.llm_service.translate_all_page_titles(new_page_records)
                for doc in new_docs:
                    if doc.source_path and doc.source_path in page_titles_zh:
                        self.doc_repo.update(doc.id, name_translated=page_titles_zh[doc.source_path])
            except Exception as e:
                self._log_err_task(task_id, f"Page title translation failed: {e}")
        else:
            optimized_zh = optimized

        # Step 4: Store merged categories
        categories_json = json.dumps(optimized, ensure_ascii=False)
        categories_json_zh = json.dumps(optimized_zh, ensure_ascii=False) if source_language == "en" else ""
        try:
            await self.collection_service.update_readme(
                collection_id,
                readme_content="",  # will be regenerated in readme stage
                categories_json=categories_json,
                readme_content_zh="",
                categories_json_zh=categories_json_zh,
                source_language=source_language,
            )
        except Exception as e:
            self._log_err_task(task_id, f"Failed to persist merged categories: {e}")
            return

        # Step 5: Mark all documents as categorized
        self._mark_categorized(collection_id)
        self._log_info_task(task_id, f"Incremental categorization completed: {len(optimized)} groups")

    async def _generate_readme(self, task_id: str, collection_id: str, _stats: UrlTaskStats):
        """Generate README content from previously stored categories."""
        import json as json_lib

        collection = self.collection_service.collection_repo.get_by_id(collection_id)
        if not collection:
            self._log_err_task(task_id, "Collection not found")
            return

        categories_json = collection.categories_json
        if not categories_json:
            self._log_err_task(task_id, "No categories found - run categorize stage first")
            return

        groups = json_lib.loads(categories_json)
        source_language = collection.source_language or "en"

        def count_all_pages(nodes: list[dict]) -> int:
            total = 0
            for n in nodes:
                total += len(n.get("pages", []))
                total += count_all_pages(n.get("children", []))
            return total

        total_pages = count_all_pages(groups)

        if total_pages == 0:
            self._log_info_task(task_id, "No pages in categories, skipping README generation")
            return

        self._log_info_task(task_id, f"Generating README for {len(groups)} groups, {total_pages} pages...")

        # Generate README content
        readme_content = await self.llm_service.generate_readme_content(
            groups, source_language, total_pages=total_pages
        )
        self._log_info_task(task_id, f"README generated, length={len(readme_content)}")

        # Translate if English source
        readme_content_zh = ""
        if source_language == "en":
            try:
                self._log_info_task(task_id, "Translating README to Chinese...")
                readme_content_zh = await self.llm_service.translate_readme(readme_content)
                self._log_info_task(task_id, f"README translated, length={len(readme_content_zh)}")
            except Exception as e:
                self._log_err_task(task_id, f"README translation failed: {e}")

        # Persist to database (keep existing categories)
        try:
            await self.collection_service.update_readme(
                collection_id,
                readme_content=readme_content,
                categories_json=categories_json,
                readme_content_zh=readme_content_zh,
                categories_json_zh=collection.categories_json_zh or "",
                source_language=source_language
            )
        except Exception as e:
            self._log_err_task(task_id, f"Failed to persist README: {e}")
            return

        self._log_info_task(task_id, "README stored successfully")

    async def _process_regenerate_readme(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Re-categorize all documents and regenerate README without re-crawling."""
        self._log_info_task(task_id, "Starting README regeneration")

        # Use collection's saved categorize_mode, default to ai
        collection = self.collection_service.collection_repo.get_by_id(collection_id)
        categorize_mode = collection.categorize_mode if collection and collection.categorize_mode else "auto"

        # Stage: categorize — clear all marks and re-categorize from scratch
        self._update_stage(task_id, "categorize")
        self.doc_repo.clear_categorized(collection_id)
        await self._categorize_collection(task_id, collection_id, categorize_mode)
        self._mark_categorized(collection_id)

        # Stage: readme
        self._update_stage(task_id, "readme")
        stats = UrlTaskStats()
        await self._generate_readme(task_id, collection_id, stats)

        self.task_repo.mark_completed(task_id, True)
        self._log_info_task(task_id, "README regeneration completed")

    async def _process_recategorize(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Re-categorize all documents without re-crawling or regenerating README."""
        categorize_mode = input_params.get("categorize_mode", "auto")
        self._log_info_task(task_id, f"Starting recategorization with mode: {categorize_mode}")

        # Stage: categorize — clear all marks and re-categorize from scratch
        self._update_stage(task_id, "categorize")
        self.doc_repo.clear_categorized(collection_id)
        await self._categorize_collection(task_id, collection_id, categorize_mode)
        self._mark_categorized(collection_id)

        # Update collection's categorize_mode
        self.collection_service.collection_repo.update(
            collection_id, categorize_mode=categorize_mode
        )

        self.task_repo.mark_completed(task_id, True)
        self._log_info_task(task_id, "Recategorization completed")

    def close(self):
        """Close connections and cleanup resources"""
        if self.running:
            asyncio.create_task(self.stop_workers())
        self.llm_service.close()
        logger.info("TaskService resources closed")
