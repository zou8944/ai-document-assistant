"""
Task management service for async operations.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from typing import Any, Optional

from langchain_openai import OpenAIEmbeddings

from crawler.simple_web_crawler import create_simple_web_crawler
from data_processing.file_processor import create_file_processor
from data_processing.text_splitter import create_document_processor
from models.database.document import DocumentChunk
from models.dto import DocumentDTO, TaskDTO
from models.responses import TaskResponse
from repository.document import DocumentChunkRepository, DocumentRepository
from repository.task import TaskLogRepository, TaskRepository
from vector_store.chroma_client import create_chroma_manager

logger = logging.getLogger(__name__)


@dataclass
class FileTaskProgressBody:
    files_processed: int = 0
    files_total: int = 0
    chunks_created: int = 0
    chunks_indexed: int = 0
    files_skipped: int = 0

@dataclass
class UrlTaskProgressItem:
    urls_processed: int = 0
    urls_total: int = 0
    pages_crawled: int = 0
    pages_indexed: int = 0
    pages_skipped: int = 0

class TaskService:
    """Service for managing async tasks"""

    def __init__(self, config=None):
        """Initialize task service"""
        from config import get_config

        self.config = config or get_config()

        # Task queue and workers
        self.task_queue: asyncio.Queue = asyncio.Queue()
        self.workers: list[asyncio.Task] = []
        self.running = False

        # Initialize repositories
        self.task_repo = TaskRepository()
        self.task_log_repo = TaskLogRepository()
        self.doc_repo = DocumentRepository()
        self.doc_chunk_repo = DocumentChunkRepository()

        # Shared components - created once and reused
        self.document_processor = create_document_processor(self.config)
        self.chroma_manager = create_chroma_manager(self.config)
        self.file_processor = create_file_processor(self.config)
        self.web_crawler = create_simple_web_crawler(self.config)

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

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

    def log_info_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "info", message)

    def log_debug_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "debug", message)

    def log_err_task(self, task_id: str, message: str) -> None:
        self._log_task(task_id, "error", message)

    def _log_task(self, task_id: str, level: str, message: str):
        self.task_log_repo.add_log(task_id, level, message, None)
        logger.log(getattr(logging, level.upper()), message)

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

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        task = self.task_repo.get_by_id(task_id)

        if not task:
            return None

        return self._to_response(task)

    async def update_task_progress(self, task_id: str, progress: int, stats: Optional[FileTaskProgressBody|UrlTaskProgressItem] = None) -> bool:
        stats_json = json.dumps(asdict(stats)) if stats else None
        return self.task_repo.update_progress(task_id, progress, stats_json)

    async def requeue_processing_task(self):
        tasks = self.task_repo.get_active_tasks()
        for task in tasks:
            await self.task_queue.put(task.id)
            logger.info(f"Re-queued processing task {task.id}")

    async def start_workers(self, num_workers: int = 2):
        """Start background task workers"""
        if self.running:
            logger.warning("Workers already running")
            return

        # Requeue processing tasks
        await self.requeue_processing_task()

        self.running = True
        logger.info(f"Starting {num_workers} task workers")

        for i in range(num_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)

    async def stop_workers(self):
        """Stop background task workers"""
        if not self.running:
            return

        logger.info("Stopping task workers...")
        self.running = False

        # Cancel all workers
        for worker in self.workers:
            worker.cancel()

        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers.clear()

        logger.info("Task workers stopped")

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
                await self._process_task(task_id)

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

    async def _check_document_exists(self, collection_id: str, doc_hash: str) -> bool:
        """Check if document already exists and handle duplication logic"""
        existing_doc = self.doc_repo.find_by_hash(collection_id, doc_hash)
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

    def _mark_document_failed(self, doc_id: str, error_message: str):
        """Mark document as failed with error message"""
        self.doc_repo.update_by_model(DocumentDTO(
            id=doc_id,
            status="failed",
            error_message=error_message,
        ))

    async def _store_document_chunks(
        self, task_id: str, doc_id: str, collection_id: str,
        chunks, embeddings, source_name: str, extra_metadata: Optional[dict] = None
    ):
        """Store document chunks in database and vector store"""
        import hashlib
        import json

        chunk_records = []
        vector_data = []

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Create unique vector ID
            vector_id = f"{doc_id}_chunk_{i}"

            # Create chunk record
            chunk_record = DocumentChunk(
                document_id=doc_id,
                collection_id=collection_id,
                chunk_index=i,
                content_preview=chunk.content[:200] if chunk.content else "",
                vector_id=vector_id,
                content_hash=hashlib.md5(chunk.content.encode()).hexdigest(),
                chunk_metadata=json.dumps(chunk.metadata)
            )

            chunk_records.append(chunk_record)

            # Prepare vector data for ChromaDB
            metadata = {
                "document_id": doc_id,
                "collection_id": collection_id,
                "chunk_index": i,
                "source": f"{source_name}#chunk_{i}",
                "content_preview": chunk.content[:200] if chunk.content else ""
            }

            # Add extra metadata if provided
            if extra_metadata:
                metadata.update(extra_metadata)

            vector_data.append({
                "id": vector_id,
                "embedding": embedding,
                "metadata": metadata,
                "document": chunk.content
            })

        # Store chunks in database
        for chunk_record in chunk_records:
            self.doc_chunk_repo.create_by_model(chunk_record)

        # Store vectors in ChromaDB
        try:
            collection = await self.chroma_manager.get_collection(collection_id)
            if collection:
                ids = [v["id"] for v in vector_data]
                embeddings_list = [v["embedding"] for v in vector_data]
                metadatas = [v["metadata"] for v in vector_data]
                documents = [v["document"] for v in vector_data]

                collection.add(
                    ids=ids,
                    embeddings=embeddings_list,
                    metadatas=metadatas,
                    documents=documents
                )

                self.log_info_task(task_id, f"Indexed {len(chunk_records)} chunks from {source_name}")
            else:
                raise Exception("ChromaDB collection not found")

        except Exception as e:
            # Mark document as failed
            self.doc_repo.update_by_model(DocumentDTO(
                id=doc_id,
                status="failed",
                error_message=f"Vector storage failed: {str(e)}"
            ))

            self.log_err_task(task_id, f"Vector storage failed for {source_name}: {str(e)}")
            raise e

        # Mark document as successfully indexed
        self.doc_repo.update_by_model(DocumentDTO(
            id=doc_id,
            status="indexed",
            chunk_count=len(chunk_records)
        ))

        return len(chunk_records)

    async def _process_file_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process file ingestion task with full integration"""
        self.log_info_task(task_id, "Starting file ingestion")

        # Get file paths from input params
        file_paths = input_params.get("files", [])
        if not file_paths:
            raise ValueError("No files specified for ingestion")

        # Import necessary modules for file processing
        from pathlib import Path

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

        total_files = len(all_files)
        processed_files = 0
        total_chunks = 0
        indexed_chunks = 0
        skipped_files = 0

        await self.update_task_progress(task_id, 0,  FileTaskProgressBody(
            files_processed=0,
            files_total=total_files,
            chunks_created=0,
            chunks_indexed=0,
            files_skipped=0
        ))

        for file_path in all_files:
            try:
                chunk_count = await self._process_single_file(task_id, collection_id, file_path)

                if chunk_count is None:  # Skipped file
                    skipped_files += 1
                elif chunk_count > 0:  # Successfully processed
                    indexed_chunks += chunk_count
                    total_chunks += chunk_count

                processed_files += 1

                # Update progress
                progress = int((processed_files / total_files) * 100)
                await self.update_task_progress(task_id, progress, FileTaskProgressBody(
                    files_processed=processed_files,
                    files_total=total_files,
                    chunks_created=total_chunks,
                    chunks_indexed=indexed_chunks,
                    files_skipped=skipped_files
                ))

            except Exception as e:
                self.log_err_task(task_id, f"Error processing {file_path}: {str(e)}")
                processed_files += 1
                continue

        # Final status update
        success = indexed_chunks > 0
        await self.update_task_progress(task_id, 100, FileTaskProgressBody(
            files_processed=processed_files,
            files_total=total_files,
            chunks_created=total_chunks,
            chunks_indexed=indexed_chunks,
            files_skipped=skipped_files
        ))

        if success:
            self.task_repo.mark_completed(task_id, True)
            self.log_info_task(task_id, f"File ingestion completed: {indexed_chunks} chunks indexed from {processed_files} files")
        else:
            self.task_repo.mark_completed(task_id, False, "No files were successfully processed")
            self.log_err_task(task_id, "File ingestion failed: No files were successfully processed")

    async def _process_single_file(self, task_id: str, collection_id: str, file_path: str):
        """Process a single file and return chunk count (None if skipped)"""
        import hashlib
        import mimetypes
        from pathlib import Path

        file_path_obj = Path(file_path)
        self.log_info_task(task_id, f"Processing: {file_path_obj.name}")

        # Calculate file hash for deduplication
        with open(file_path, 'rb') as f:
            file_hash = hashlib.md5(f.read()).hexdigest()

        # Check if file already exists
        exists = await self._check_document_exists(collection_id, file_hash)
        if exists:
            self.log_info_task(task_id, f"Skipping duplicate file: {file_path_obj.name}")
            return None

        # Process file content
        result = self.file_processor.process_file(file_path)
        if not result.success:
            self.log_err_task(task_id, f"Failed to process {file_path_obj.name}: {result.error}")
            return 0

        # Get file metadata
        file_size = file_path_obj.stat().st_size
        mime_type, _ = mimetypes.guess_type(file_path)
        file_uri = f"file://{file_path_obj.absolute()}"

        # Create document record
        doc_id = await self._create_document_record(
            collection_id, file_path_obj.name, file_uri, file_size, mime_type, file_hash
        )
        assert doc_id

        # Process text into chunks
        chunks = self.document_processor.process_file_content(
            file_path=file_path,
            content=result.content,
            file_type=result.file_type
        )

        if not chunks:
            self._mark_document_failed(doc_id, "No content chunks extracted")
            self.log_err_task(task_id, f"No content extracted from {file_path_obj.name}")
            return 0

        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        try:
            chunk_embeddings = await self.embeddings.aembed_documents(texts)
        except Exception as e:
            self._mark_document_failed(doc_id, f"Embedding generation failed: {str(e)}")
            self.log_err_task(task_id, f"Embedding failed for {file_path_obj.name}: {str(e)}")
            return 0

        # Store chunks
        try:
            chunk_count = await self._store_document_chunks(
                task_id, doc_id, collection_id, chunks, chunk_embeddings, file_path_obj.name
            )
            return chunk_count
        except Exception as e:
            self.log_err_task(task_id, f"Storage failed for {file_path_obj.name}: {str(e)}")
            return 0

    async def _process_url_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process URL ingestion task with full web crawling integration"""
        self.log_info_task(task_id, "Starting URL ingestion")

        # Get parameters from input
        urls = input_params.get("urls", [])
        override = input_params.get("override", True)

        if not urls:
            raise ValueError("No URLs specified for ingestion")

        total_urls = len(urls)
        processed_urls = 0
        total_pages = 0
        indexed_pages = 0
        skipped_pages = 0

        await self.update_task_progress(task_id, 0, UrlTaskProgressItem(
            urls_processed=0,
            urls_total=total_urls,
            pages_crawled=0,
            pages_indexed=0,
            pages_skipped=0
        ))

        for url in urls:
            try:
                self.log_info_task(task_id, f"Crawling URL: {url}")

                # Crawl this url, tracking progress asynchronously
                def progress_callback(current_url, completed, total):
                    self.log_info_task(task_id, f"Crawling page {completed + 1}/{total}: {current_url}")

                crawl_results = self.web_crawler.crawl_recursive(url, progress_callback=progress_callback)
                successful_results = [r for r in crawl_results if r.success]

                self.log_info_task(task_id, f"Crawled {len(successful_results)}/{len(crawl_results)} pages successfully from {url}")

                indexed_pages = 0
                skipped_pages = 0
                total_pages = 0

                # Process each crawled page
                for crawl_result in successful_results:
                    try:
                        page_result = await self._process_single_page(
                            task_id, collection_id, crawl_result, override,
                        )

                        total_pages += 1
                        if page_result == "indexed":
                            indexed_pages += 1
                        elif page_result == "skipped":
                            skipped_pages += 1

                    except Exception as e:
                        self.log_err_task(task_id, f"Error processing page {crawl_result.url}: {str(e)}")
                        total_pages += 1
                        continue

                # Update progress
                progress = int((processed_urls / total_urls) * 100)
                await self.update_task_progress(task_id, progress, UrlTaskProgressItem(
                    urls_processed=processed_urls,
                    urls_total=total_urls,
                    pages_crawled=total_pages,
                    pages_indexed=indexed_pages,
                    pages_skipped=skipped_pages
                ))

            except Exception as e:
                self.log_err_task(task_id, f"Error crawling {url}: {str(e)}")
            finally:
                processed_urls += 1

        # Final status update
        success = indexed_pages > 0
        await self.update_task_progress(task_id, 100, UrlTaskProgressItem(
            urls_processed=processed_urls,
            urls_total=total_urls,
            pages_crawled=total_pages,
            pages_indexed=indexed_pages,
            pages_skipped=skipped_pages
        ))

        if success:
            self.task_repo.mark_completed(task_id, True)
            self.log_info_task(task_id, f"URL ingestion completed: {indexed_pages} pages indexed from {processed_urls} URLs")
        else:
            self.task_repo.mark_completed(task_id, False, "No pages were successfully processed")
            self.log_err_task(task_id, "URL ingestion failed: No pages were successfully processed")

    async def _process_single_page(self, task_id: str, collection_id: str, crawl_result, override: bool) -> str:
        """Process a single crawled page and return status"""
        import hashlib
        from urllib.parse import urlparse

        page_url = crawl_result.url
        self.log_info_task(task_id, f"Processing page: {page_url}")

        # Generate document hash for deduplication
        content_for_hash = f"{page_url}:{crawl_result.title}:{crawl_result.content}"
        doc_hash = hashlib.md5(content_for_hash.encode()).hexdigest()

        # Check if document already exists
        exists = await self._check_document_exists(collection_id, doc_hash)
        if exists:
            if override:
                self.log_info_task(task_id, f"Overriding existing page: {page_url}")
            else:
                self.log_info_task(task_id, f"Skipping duplicate page: {page_url}")
                return "skipped"
        else:
            self.log_info_task(task_id, f"New page detected: {page_url}")

        # Create document record
        parsed_url = urlparse(page_url)
        domain = parsed_url.netloc

        doc_id = await self._create_document_record(
            collection_id,
            crawl_result.title or f"Page from {domain}",
            page_url,
            len(crawl_result.content.encode()),
            "text/html",
            doc_hash
        )
        assert doc_id

        # Process content into chunks
        if not crawl_result.content.strip():
            self._mark_document_failed(doc_id, "No content extracted from page")
            self.log_err_task(task_id, f"No content extracted from {page_url}")
            return "failed"

        # Create chunks from web content
        chunks = self.document_processor.process_web_content(
            url=page_url,
            content=crawl_result.content,
            page_title=crawl_result.title
        )

        if not chunks:
            self._mark_document_failed(doc_id, "No content chunks extracted")
            self.log_err_task(task_id, f"No content chunks extracted from {page_url}")
            return "failed"

        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        try:
            chunk_embeddings = await self.embeddings.aembed_documents(texts)
        except Exception as e:
            self._mark_document_failed(doc_id, f"Embedding generation failed: {str(e)}")
            self.log_err_task(task_id, f"Embedding failed for {page_url}: {str(e)}")
            return "failed"

        # Prepare extra metadata for URL content
        extra_metadata = {
            "url": page_url,
            "title": crawl_result.title or ""
        }

        # Store chunks
        try:
            await self._store_document_chunks(
                task_id, doc_id, collection_id, chunks, chunk_embeddings, page_url, extra_metadata
            )
            return "indexed"
        except Exception as e:
            self.log_err_task(task_id, f"Storage failed for {page_url}: {str(e)}")
            return "failed"

    def close(self):
        """Close connections and cleanup resources"""
        if self.running:
            asyncio.create_task(self.stop_workers())
        logger.info("TaskService resources closed")
