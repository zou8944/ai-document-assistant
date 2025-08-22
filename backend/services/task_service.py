"""
Task management service for async operations.
"""

import asyncio
import json
import logging
from typing import Any, Optional

from database.connection import get_db_session_context
from models.database.task import Task
from models.responses import TaskResponse
from repository.task import TaskLogRepository, TaskRepository

logger = logging.getLogger(__name__)


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

        logger.info("TaskService initialized successfully")

    def _to_response(self, task: Task) -> TaskResponse:
        """Convert Task model to response model"""
        try:
            progress = json.loads(task.stats) if task.stats else {}
            stats = json.loads(task.input_params) if task.input_params else {}
        except json.JSONDecodeError:
            progress = {}
            stats = {}

        return TaskResponse(
            task_id=task.id,
            type=task.type,
            status=task.status,
            progress={"percentage": task.progress_percentage, **progress},
            stats=stats,
            collection_id=task.collection_id,
            created_at=task.created_at.isoformat(),
            updated_at=task.updated_at.isoformat(),
            error=task.error_message
        )

    async def create_task(
        self,
        task_type: str,
        collection_id: str,
        input_params: dict[str, Any]
    ) -> TaskResponse:
        """Create a new task"""
        with get_db_session_context() as session:
            repo = TaskRepository(session)

            task = Task(
                type=task_type,
                collection_id=collection_id,
                input_params=json.dumps(input_params),
                status="pending"
            )

            created_task = repo.create_by_model(task)

            # Add task to queue
            await self.task_queue.put(created_task.id)

            logger.info(f"Created task {created_task.id} of type {task_type}")

            return self._to_response(created_task)

    async def get_task(self, task_id: str) -> Optional[TaskResponse]:
        """Get task by ID"""
        with get_db_session_context() as session:
            repo = TaskRepository(session)
            task = repo.get_by_id(task_id)

            if not task:
                return None

            return self._to_response(task)

    async def update_task_progress(
        self,
        task_id: str,
        progress: int,
        stats: Optional[dict[str, Any]] = None
    ) -> bool:
        """Update task progress"""
        with get_db_session_context() as session:
            repo = TaskRepository(session)

            stats_json = json.dumps(stats) if stats else None
            success = repo.update_progress(task_id, progress, stats_json)

            if success:
                logger.debug(f"Updated task {task_id} progress to {progress}%")

            return success

    async def mark_task_started(self, task_id: str) -> bool:
        """Mark task as started"""
        with get_db_session_context() as session:
            repo = TaskRepository(session)
            success = repo.mark_started(task_id)

            if success:
                logger.info(f"Marked task {task_id} as started")

            return success

    async def mark_task_completed(
        self,
        task_id: str,
        success: bool,
        error_message: Optional[str] = None
    ) -> bool:
        """Mark task as completed"""
        with get_db_session_context() as session:
            repo = TaskRepository(session)
            result = repo.mark_completed(task_id, success, error_message)

            if result:
                status = "success" if success else "failed"
                logger.info(f"Marked task {task_id} as {status}")

            return result

    async def add_task_log(
        self,
        task_id: str,
        level: str,
        message: str,
        details: Optional[dict[str, Any]] = None
    ) -> bool:
        """Add log entry to task"""
        with get_db_session_context() as session:
            log_repo = TaskLogRepository(session)

            details_json = json.dumps(details) if details else None
            log_repo.add_log(task_id, level, message, details_json)

            logger.debug(f"Added {level} log to task {task_id}: {message}")
            return True

    async def start_workers(self, num_workers: int = 2):
        """Start background task workers"""
        if self.running:
            logger.warning("Workers already running")
            return

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
                logger.error(f"Worker {worker_name} error: {e}")
                # Continue processing other tasks
                continue

        logger.info(f"Task worker {worker_name} stopped")

    async def _process_task(self, task_id: str):
        """Process a single task"""
        # Get task details
        with get_db_session_context() as session:
            repo = TaskRepository(session)
            task = repo.get_by_id(task_id)

            if not task:
                logger.error(f"Task {task_id} not found")
                return

            # Mark as started
            await self.mark_task_started(task_id)

            # Parse input parameters
            try:
                input_params = json.loads(task.input_params)
            except json.JSONDecodeError:
                input_params = {}

            # Route to appropriate handler
            assert task.collection_id
            if task.type == "ingest_files":
                await self._process_file_ingestion(task_id, task.collection_id, input_params)
            elif task.type == "ingest_urls":
                await self._process_url_ingestion(task_id, task.collection_id, input_params)
            else:
                error_msg = f"Unknown task type: {task.type}"
                logger.error(error_msg)
                await self.mark_task_completed(task_id, False, error_msg)

    async def _process_file_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process file ingestion task with full integration"""
        await self.add_task_log(task_id, "info", "Starting file ingestion")

        # Get file paths from input params
        file_paths = input_params.get("files", [])
        if not file_paths:
            raise ValueError("No files specified for ingestion")

        # Import necessary modules
        import hashlib
        import mimetypes
        from pathlib import Path

        from langchain_openai import OpenAIEmbeddings

        from data_processing.file_processor import create_file_processor
        from data_processing.text_splitter import create_document_processor
        from database.connection import get_db_session_context
        from models.database.document import Document, DocumentChunk
        from repository.document import DocumentChunkRepository, DocumentRepository
        from vector_store.chroma_client import create_chroma_manager

        # Initialize components
        file_processor = create_file_processor(self.config)
        document_processor = create_document_processor(self.config)
        chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Ensure collection exists in ChromaDB
        await chroma_manager.ensure_collection(collection_id)

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

        await self.update_task_progress(task_id, 0, {
            "files_processed": 0,
            "files_total": total_files,
            "chunks_created": 0,
            "chunks_indexed": 0,
            "files_skipped": 0
        })

        for file_path in all_files:
            try:
                file_path_obj = Path(file_path)
                await self.add_task_log(task_id, "info", f"Processing: {file_path_obj.name}")

                # Calculate file hash for deduplication
                with open(file_path, 'rb') as f:
                    file_hash = hashlib.md5(f.read()).hexdigest()

                # Check if file already exists
                with get_db_session_context() as session:
                    doc_repo = DocumentRepository(session)
                    existing_doc = doc_repo.find_by_hash(collection_id, file_hash)

                    if existing_doc:
                        await self.add_task_log(task_id, "info", f"Skipping duplicate file: {file_path_obj.name}")
                        skipped_files += 1
                        processed_files += 1
                        continue

                # Process file content
                result = file_processor.process_file(file_path)
                if not result.success:
                    await self.add_task_log(task_id, "warning", f"Failed to process {file_path_obj.name}: {result.error}")
                    processed_files += 1
                    continue

                # Get file metadata
                file_size = file_path_obj.stat().st_size
                mime_type, _ = mimetypes.guess_type(file_path)
                file_uri = f"file://{file_path_obj.absolute()}"

                # Create document record
                with get_db_session_context() as session:
                    doc_repo = DocumentRepository(session)

                    document = Document(
                        collection_id=collection_id,
                        name=file_path_obj.name,
                        uri=file_uri,
                        size_bytes=file_size,
                        mime_type=mime_type,
                        status="processing",
                        hash_md5=file_hash
                    )

                    created_doc = doc_repo.create_by_model(document)
                    doc_id = created_doc.id

                # Process text into chunks
                chunks = document_processor.process_file_content(
                    file_path=file_path,
                    content=result.content,
                    file_type=result.file_type
                )

                if not chunks:
                    # Mark document as failed
                    with get_db_session_context() as session:
                        doc_repo = DocumentRepository(session)
                        doc = doc_repo.get_by_id(doc_id)
                        if doc:
                            doc.status = "failed"
                            doc.error_message = "No content chunks extracted"
                            session.commit()

                    await self.add_task_log(task_id, "warning", f"No content extracted from {file_path_obj.name}")
                    processed_files += 1
                    continue

                # Generate embeddings
                texts = [chunk.content for chunk in chunks]
                try:
                    chunk_embeddings = await embeddings.aembed_documents(texts)
                except Exception as e:
                    # Mark document as failed
                    with get_db_session_context() as session:
                        doc_repo = DocumentRepository(session)
                        doc = doc_repo.get_by_id(doc_id)
                        if doc:
                            doc.status = "failed"
                            doc.error_message = f"Embedding generation failed: {str(e)}"
                            session.commit()

                    await self.add_task_log(task_id, "error", f"Embedding failed for {file_path_obj.name}: {str(e)}")
                    processed_files += 1
                    continue

                # Store chunks in database and ChromaDB
                with get_db_session_context() as session:
                    chunk_repo = DocumentChunkRepository(session)
                    doc_repo = DocumentRepository(session)

                    chunk_records = []
                    vector_data = []

                    for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
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
                        vector_data.append({
                            "id": vector_id,
                            "embedding": embedding,
                            "metadata": {
                                "document_id": doc_id,
                                "collection_id": collection_id,
                                "chunk_index": i,
                                "source": f"{file_path_obj.name}#chunk_{i}",
                                "content_preview": chunk.content[:200] if chunk.content else ""
                            },
                            "document": chunk.content
                        })

                    # Store chunks in database
                    for chunk_record in chunk_records:
                        chunk_repo.create_by_model(chunk_record)

                    # Store vectors in ChromaDB
                    try:
                        collection = await chroma_manager.get_collection(collection_id)
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

                            indexed_chunks += len(chunk_records)
                            await self.add_task_log(task_id, "info", f"Indexed {len(chunk_records)} chunks from {file_path_obj.name}")
                        else:
                            raise Exception("ChromaDB collection not found")

                    except Exception as e:
                        # Mark document as failed
                        doc = doc_repo.get_by_id(doc_id)
                        if doc:
                            doc.status = "failed"
                            doc.error_message = f"Vector storage failed: {str(e)}"
                            session.commit()

                        await self.add_task_log(task_id, "error", f"Vector storage failed for {file_path_obj.name}: {str(e)}")
                        processed_files += 1
                        continue

                    # Mark document as successfully indexed
                    doc = doc_repo.get_by_id(doc_id)
                    if doc:
                        doc.status = "indexed"
                        doc.chunk_count = len(chunk_records)
                        session.commit()

                total_chunks += len(chunks)
                processed_files += 1

                # Update progress
                progress = int((processed_files / total_files) * 100)
                await self.update_task_progress(task_id, progress, {
                    "files_processed": processed_files,
                    "files_total": total_files,
                    "chunks_created": total_chunks,
                    "chunks_indexed": indexed_chunks,
                    "files_skipped": skipped_files
                })

            except Exception as e:
                await self.add_task_log(task_id, "error", f"Error processing {file_path}: {str(e)}")
                processed_files += 1
                continue

        # Final status update
        success = indexed_chunks > 0
        await self.update_task_progress(task_id, 100, {
            "files_processed": processed_files,
            "files_total": total_files,
            "chunks_created": total_chunks,
            "chunks_indexed": indexed_chunks,
            "files_skipped": skipped_files
        })

        if success:
            await self.mark_task_completed(task_id, True)
            await self.add_task_log(task_id, "info", f"File ingestion completed: {indexed_chunks} chunks indexed from {processed_files} files")
        else:
            await self.mark_task_completed(task_id, False, "No files were successfully processed")
            await self.add_task_log(task_id, "error", "File ingestion failed: No files were successfully processed")

        # Cleanup
        chroma_manager.close()

    async def _process_url_ingestion(
        self,
        task_id: str,
        collection_id: str,
        input_params: dict[str, Any]
    ):
        """Process URL ingestion task with full web crawling integration"""
        await self.add_task_log(task_id, "info", "Starting URL ingestion")

        # Get parameters from input
        urls = input_params.get("urls", [])
        max_depth = input_params.get("max_depth", 2)
        override = input_params.get("override", True)

        if not urls:
            raise ValueError("No URLs specified for ingestion")

        # Import necessary modules
        import hashlib
        from urllib.parse import urlparse

        from langchain_openai import OpenAIEmbeddings

        from crawler.simple_web_crawler import create_simple_web_crawler
        from data_processing.text_splitter import create_document_processor
        from database.connection import get_db_session_context
        from models.database.document import Document, DocumentChunk
        from repository.document import DocumentChunkRepository, DocumentRepository
        from vector_store.chroma_client import create_chroma_manager

        # Initialize components
        document_processor = create_document_processor(self.config)
        chroma_manager = create_chroma_manager(self.config)

        # Initialize embeddings
        embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
        embeddings = OpenAIEmbeddings(**embeddings_kwargs)

        # Ensure collection exists in ChromaDB
        await chroma_manager.ensure_collection(collection_id)

        # Initialize web crawler with config
        crawler = create_simple_web_crawler(self.config)

        total_urls = len(urls)
        processed_urls = 0
        total_pages = 0
        indexed_pages = 0
        skipped_pages = 0

        await self.update_task_progress(task_id, 0, {
            "urls_processed": 0,
            "urls_total": total_urls,
            "pages_crawled": 0,
            "pages_indexed": 0,
            "pages_skipped": 0
        })

        for url in urls:
            try:
                await self.add_task_log(task_id, "info", f"Crawling URL: {url}")

                # Crawl the domain
                def progress_callback(current_url, completed, total):
                    # Update progress periodically
                    asyncio.create_task(self.add_task_log(
                        task_id, "debug", f"Crawling page {completed + 1}/{total}: {current_url}"
                    ))

                crawl_results = crawler.crawl_domain(url, progress_callback=progress_callback)
                successful_results = [r for r in crawl_results if r.success]

                await self.add_task_log(
                    task_id, "info",
                    f"Crawled {len(successful_results)}/{len(crawl_results)} pages successfully from {url}"
                )

                # Process each crawled page
                for crawl_result in successful_results:
                    try:
                        page_url = crawl_result.url
                        await self.add_task_log(task_id, "debug", f"Processing page: {page_url}")

                        # Generate document hash for deduplication
                        content_for_hash = f"{page_url}:{crawl_result.title}:{crawl_result.content}"
                        doc_hash = hashlib.md5(content_for_hash.encode()).hexdigest()

                        # Check if document already exists
                        with get_db_session_context() as session:
                            doc_repo = DocumentRepository(session)
                            existing_doc = doc_repo.find_by_hash(collection_id, doc_hash)

                            if existing_doc and not override:
                                await self.add_task_log(task_id, "info", f"Skipping duplicate page: {page_url}")
                                skipped_pages += 1
                                total_pages += 1
                                continue

                            # Delete existing document if override is True
                            if existing_doc and override:
                                await self.add_task_log(task_id, "info", f"Overriding existing page: {page_url}")
                                doc_repo.delete(existing_doc.id)

                        # Create document record
                        parsed_url = urlparse(page_url)
                        domain = parsed_url.netloc

                        with get_db_session_context() as session:
                            doc_repo = DocumentRepository(session)

                            document = Document(
                                collection_id=collection_id,
                                name=crawl_result.title or f"Page from {domain}",
                                uri=page_url,
                                size_bytes=len(crawl_result.content.encode()),
                                mime_type="text/html",
                                status="processing",
                                hash_md5=doc_hash
                            )

                            created_doc = doc_repo.create_by_model(document)
                            doc_id = created_doc.id

                        # Process content into chunks
                        if not crawl_result.content.strip():
                            # Mark document as failed
                            with get_db_session_context() as session:
                                doc_repo = DocumentRepository(session)
                                doc = doc_repo.get_by_id(doc_id)
                                if doc:
                                    doc.status = "failed"
                                    doc.error_message = "No content extracted from page"
                                    session.commit()

                            await self.add_task_log(task_id, "warning", f"No content extracted from {page_url}")
                            total_pages += 1
                            continue

                        # Create chunks from web content
                        chunks = document_processor.process_web_content(
                            url=page_url,
                            content=crawl_result.content,
                            page_title=crawl_result.title
                        )

                        if not chunks:
                            # Mark document as failed
                            with get_db_session_context() as session:
                                doc_repo = DocumentRepository(session)
                                doc = doc_repo.get_by_id(doc_id)
                                if doc:
                                    doc.status = "failed"
                                    doc.error_message = "No content chunks extracted"
                                    session.commit()

                            await self.add_task_log(task_id, "warning", f"No content chunks extracted from {page_url}")
                            total_pages += 1
                            continue

                        # Generate embeddings
                        texts = [chunk.content for chunk in chunks]
                        try:
                            chunk_embeddings = await embeddings.aembed_documents(texts)
                        except Exception as e:
                            # Mark document as failed
                            with get_db_session_context() as session:
                                doc_repo = DocumentRepository(session)
                                doc = doc_repo.get_by_id(doc_id)
                                if doc:
                                    doc.status = "failed"
                                    doc.error_message = f"Embedding generation failed: {str(e)}"
                                    session.commit()

                            await self.add_task_log(task_id, "error", f"Embedding failed for {page_url}: {str(e)}")
                            total_pages += 1
                            continue

                        # Store chunks in database and ChromaDB
                        with get_db_session_context() as session:
                            chunk_repo = DocumentChunkRepository(session)
                            doc_repo = DocumentRepository(session)

                            chunk_records = []
                            vector_data = []

                            for i, (chunk, embedding) in enumerate(zip(chunks, chunk_embeddings)):
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
                                vector_data.append({
                                    "id": vector_id,
                                    "embedding": embedding,
                                    "metadata": {
                                        "document_id": doc_id,
                                        "collection_id": collection_id,
                                        "chunk_index": i,
                                        "source": f"{page_url}#chunk_{i}",
                                        "content_preview": chunk.content[:200] if chunk.content else "",
                                        "url": page_url,
                                        "title": crawl_result.title or ""
                                    },
                                    "document": chunk.content
                                })

                            # Store chunks in database
                            for chunk_record in chunk_records:
                                chunk_repo.create_by_model(chunk_record)

                            # Store vectors in ChromaDB
                            try:
                                collection = await chroma_manager.get_collection(collection_id)
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

                                    indexed_pages += 1
                                    await self.add_task_log(task_id, "info", f"Indexed {len(chunk_records)} chunks from {page_url}")
                                else:
                                    raise Exception("ChromaDB collection not found")

                            except Exception as e:
                                # Mark document as failed
                                doc = doc_repo.get_by_id(doc_id)
                                if doc:
                                    doc.status = "failed"
                                    doc.error_message = f"Vector storage failed: {str(e)}"
                                    session.commit()

                                await self.add_task_log(task_id, "error", f"Vector storage failed for {page_url}: {str(e)}")
                                total_pages += 1
                                continue

                            # Mark document as successfully indexed
                            doc = doc_repo.get_by_id(doc_id)
                            if doc:
                                doc.status = "indexed"
                                doc.chunk_count = len(chunk_records)
                                session.commit()

                        total_pages += 1

                    except Exception as e:
                        await self.add_task_log(task_id, "error", f"Error processing page {crawl_result.url}: {str(e)}")
                        total_pages += 1
                        continue

                processed_urls += 1

                # Update progress
                progress = int((processed_urls / total_urls) * 100)
                await self.update_task_progress(task_id, progress, {
                    "urls_processed": processed_urls,
                    "urls_total": total_urls,
                    "pages_crawled": total_pages,
                    "pages_indexed": indexed_pages,
                    "pages_skipped": skipped_pages
                })

            except Exception as e:
                await self.add_task_log(task_id, "error", f"Error crawling {url}: {str(e)}")
                processed_urls += 1
                continue

        # Final status update
        success = indexed_pages > 0
        await self.update_task_progress(task_id, 100, {
            "urls_processed": processed_urls,
            "urls_total": total_urls,
            "pages_crawled": total_pages,
            "pages_indexed": indexed_pages,
            "pages_skipped": skipped_pages
        })

        if success:
            await self.mark_task_completed(task_id, True)
            await self.add_task_log(task_id, "info", f"URL ingestion completed: {indexed_pages} pages indexed from {processed_urls} URLs")
        else:
            await self.mark_task_completed(task_id, False, "No pages were successfully processed")
            await self.add_task_log(task_id, "error", "URL ingestion failed: No pages were successfully processed")

        # Cleanup
        chroma_manager.close()

    def close(self):
        """Close connections and cleanup resources"""
        if self.running:
            asyncio.create_task(self.stop_workers())
        logger.info("TaskService resources closed")
