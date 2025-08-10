#!/usr/bin/env python3
"""
Main entry point for the AI Document Assistant backend.
Handles JSON communication via stdin/stdout with the Electron frontend.
Following 2024 best practices for subprocess communication and error handling.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Import configuration
from config import get_config, init_config

# Initialize configuration first
try:
    config = init_config()
except Exception as e:
    print(f"Failed to initialize configuration: {e}", file=sys.stderr)
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=getattr(logging, config.log_level.upper()),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('backend.log'),
        logging.StreamHandler(sys.stderr)  # Use stderr to avoid interfering with stdout communication
    ]
)

logger = logging.getLogger(__name__)

# Import our modules
try:
    from langchain_openai import OpenAIEmbeddings

    from crawler import create_simple_web_crawler
    from data_processing.file_processor import create_file_processor
    from data_processing.text_splitter import create_document_processor
    from rag.retrieval_chain import create_retrieval_chain
    from vector_store.qdrant_client import create_qdrant_manager
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    sys.exit(1)


class DocumentAssistantBackend:
    """
    Main backend service for document processing and RAG queries.
    Handles communication with Electron frontend via JSON messages.
    """

    def __init__(self):
        """Initialize backend components"""
        self.config = get_config()

        # Initialize components with configuration
        self.file_processor = create_file_processor(self.config)
        self.document_processor = create_document_processor(self.config)
        self.web_crawler = create_simple_web_crawler(self.config)
        self.qdrant_manager = create_qdrant_manager(self.config)

        # Initialize embeddings (will be used for all operations)
        try:
            embeddings_kwargs = self.config.get_openai_embeddings_kwargs()
            self.embeddings = OpenAIEmbeddings(**embeddings_kwargs)

            # Log configuration info
            config_info = self.config.get_config_info()
            logger.info(f"Chat model: {config_info['chat_config']['model']} @ {config_info['chat_config']['api_base']}")
            logger.info(f"Embedding model: {config_info['embedding_config']['model']} @ {config_info['embedding_config']['api_base']}")
            if config_info['embedding_config']['using_fallback']:
                logger.info("Embedding model using chat API configuration (fallback)")
        except Exception as e:
            logger.error(f"Failed to initialize embeddings: {e}")
            self.embeddings = None

        # 动态探测 embedding 维度
        self.embedding_dimension = self._detect_embedding_dimension()
        logger.info(f"Detected embedding dimension: {self.embedding_dimension}")

        self.active_collections: dict[str, str] = {}  # collection_name -> source_type
        # 批量嵌入最大条数（API 限制，默认 64，可由 config 覆盖）
        self.max_embedding_batch_size = int(getattr(self.config, "embedding_batch_size", 64))
        logger.info("DocumentAssistantBackend initialized successfully")
    def _send_response(self, response: dict[str, Any]) -> None:
        """
        Send JSON response to frontend via stdout.
        CRITICAL: Flush immediately to ensure message delivery.
        """
        try:
            # CRITICAL: python-shell expects JSON communication via stdout/stdin
            # Each message must be complete JSON on single line
            sys.stdout.write(json.dumps(response) + '\n')
            sys.stdout.flush()
        except Exception as e:
            logger.error(f"Failed to send response: {e}")

    def _send_error(self, message: str, command: str = "unknown") -> None:
        """Send error response to frontend"""
        error_response = {
            "status": "error",
            "message": message,
            "command": command
        }
        self._send_response(error_response)

    def _send_progress(self, command: str, progress: int, total: int, message: str = "") -> None:
        """Send progress update to frontend"""
        progress_response = {
            "status": "progress",
            "command": command,
            "progress": progress,
            "total": total,
            "message": message
        }
        self._send_response(progress_response)

    async def _embed_texts_in_batches(self, texts: list[str], command: str) -> list[list[float]]:
        """
        按批次生成 embeddings，避免超过服务端限制 (如 64)。
        失败即抛出异常，外层捕获。
        """
        if not self.embeddings:
            raise Exception("Embeddings not available. Please check OpenAI API configuration.")

        if not texts:
            return []
        max_batch = self.max_embedding_batch_size
        total = len(texts)
        embeddings: list[list[float]] = []
        for start in range(0, total, max_batch):
            end = min(start + max_batch, total)
            batch = texts[start:end]
            try:
                batch_embeddings = await self.embeddings.aembed_documents(batch)
            except Exception as e:
                logger.error(f"Embedding batch failed [{start}:{end}]: {e}")
                raise
            embeddings.extend(batch_embeddings)
            # 进度：当前已完成 end 条 / total 条
            self._send_progress(command, end, total, f"Embedding batches {end}/{total}")
        return embeddings

    def _detect_embedding_dimension(self) -> int:
        """
        探测当前 embedding 模型实际输出的向量维度。
        若失败返回常见默认值 1536（并记录警告）。
        """
        if not self.embeddings:
            return 1536
        try:
            # 使用最短文本避免超额 token
            vec = self.embeddings.embed_query("ping")
            dim = len(vec)
            if dim <= 0:
                raise ValueError("empty embedding vector")
            return dim
        except Exception as e:
            logger.warning(f"Failed to detect embedding dimension, fallback to 1536: {e}")
            return 1536

    async def _ensure_collection_with_dimension(self, collection_name: str) -> dict[str, Any] | None:
        """
        确保集合维度与当前 embedding 维度一致。
        如果已存在且维度不匹配，返回错误结果（调用方直接 return）。
        """
        try:
            info = await self.qdrant_manager.get_collection_info(collection_name)
            if info and info.get("vector_size") and info["vector_size"] != self.embedding_dimension:
                return {
                    "status": "error",
                    "message": (f"集合 '{collection_name}' 已存在, 向量维度为 {info['vector_size']} "
                                f"但当前模型输出维度为 {self.embedding_dimension}，请删除该集合或使用新的 collection_name。"),
                }
            # 创建 / 确保集合（若不存在则创建）
            await self.qdrant_manager.ensure_collection(
                collection_name,
                vector_size=self.embedding_dimension
            )
            return None
        except Exception as e:
            return {
                "status": "error",
                "message": f"创建/检查集合失败: {e}"
            }

    async def process_files(self, file_paths: list[str], collection_name: str = "documents") -> dict[str, Any]:
        """
        Process local files and index them in vector store.

        Args:
            file_paths: list of file or folder paths
            collection_name: Target collection name

        Returns:
            Processing result dictionary
        """
        try:
            logger.info(f"Processing {len(file_paths)} file paths for collection '{collection_name}'")

            # Ensure collection exists (使用动态维度 + 预检查)
            err = await self._ensure_collection_with_dimension(collection_name)
            if err:
                return {**err, "processed_files": 0, "total_chunks": 0}

            all_chunks = []
            processed_files = 0
            total_files = 0

            # Process each path
            for file_path in file_paths:
                path_obj = Path(file_path)

                if path_obj.is_file():
                    # Single file
                    total_files += 1
                    result = self.file_processor.process_file(str(path_obj))

                    if result.success:
                        chunks = self.document_processor.process_file_content(
                            file_path=str(path_obj),
                            content=result.content,
                            file_type=result.file_type
                        )
                        all_chunks.extend(chunks)
                        processed_files += 1

                        self._send_progress("process_files", processed_files, total_files,
                                          f"Processed: {path_obj.name}")
                    else:
                        logger.warning(f"Failed to process file {file_path}: {result.error}")

                elif path_obj.is_dir():
                    # Folder processing
                    folder_results = list(self.file_processor.process_folder(str(path_obj)))
                    total_files += len(folder_results)

                    for result in folder_results:
                        if result.success:
                            chunks = self.document_processor.process_file_content(
                                file_path=result.file_path,
                                content=result.content,
                                file_type=result.file_type
                            )
                            all_chunks.extend(chunks)
                            processed_files += 1

                            self._send_progress("process_files", processed_files, total_files,
                                              f"Processed: {Path(result.file_path).name}")

            if not all_chunks:
                return {
                    "status": "error",
                    "message": "No content extracted from provided files",
                    "processed_files": 0,
                    "total_chunks": 0
                }

            # Generate embeddings
            self._send_progress("process_files", processed_files, processed_files,
                              "Generating embeddings (batched)...")
            texts = [chunk.content for chunk in all_chunks]
            embeddings = await self._embed_texts_in_batches(texts, "process_files")
            # Index in vector store
            self._send_progress("process_files", processed_files, processed_files,
                              "Indexing documents...")

            index_result = await self.qdrant_manager.index_documents(
                collection_name=collection_name,
                chunks=all_chunks,
                embeddings=embeddings
            )

            if index_result["status"] == "success":
                self.active_collections[collection_name] = "files"

                return {
                    "status": "success",
                    "message": "Successfully processed and indexed documents",
                    "collection_name": collection_name,
                    "processed_files": processed_files,
                    "total_files": total_files,
                    "total_chunks": len(all_chunks),
                    "indexed_count": index_result["indexed_count"]
                }
            else:
                return {
                    "status": "error",
                    "message": f"Indexing failed: {index_result['message']}",
                    "processed_files": processed_files,
                    "total_chunks": len(all_chunks)
                }

        except Exception as e:
            logger.error(f"File processing failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "processed_files": 0,
                "total_chunks": 0
            }

    async def crawl_website(self, url: str, collection_name: str = "website") -> dict[str, Any]:
        """
        Crawl website and index content in vector store.

        Args:
            url: Starting URL
            collection_name: Target collection name

        Returns:
            Crawling result dictionary
        """
        try:
            logger.info(f"Starting website crawl for: {url}")

            # Ensure collection exists (使用动态维度 + 预检查)
            err = await self._ensure_collection_with_dimension(collection_name)
            if err:
                return {**err, "crawled_pages": 0, "total_chunks": 0}

            # Progress callback for crawling
            def progress_callback(current_url: str, current: int, total: int):
                self._send_progress("crawl_url", current, max(total, current),
                                  f"Crawling: {current_url}")

            # Crawl the website
            crawl_results = self.web_crawler.crawl_domain(url, progress_callback)

            successful_results = [r for r in crawl_results if r.success]

            if not successful_results:
                return {
                    "status": "error",
                    "message": "No pages were successfully crawled",
                    "crawled_pages": 0,
                    "total_chunks": 0
                }

            # Process crawled content
            self._send_progress("crawl_url", len(successful_results), len(successful_results),
                              "Processing crawled content...")

            all_chunks = []
            for result in successful_results:
                chunks = self.document_processor.process_web_content(
                    url=result.url,
                    content=result.content,
                    page_title=result.title
                )
                all_chunks.extend(chunks)

            if not all_chunks:
                return {
                    "status": "error",
                    "message": "No content extracted from crawled pages",
                    "crawled_pages": len(successful_results),
                    "total_chunks": 0
                }

            # Generate embeddings
            self._send_progress("crawl_url", len(successful_results), len(successful_results),
                              "Generating embeddings (batched)...")
            texts = [chunk.content for chunk in all_chunks]
            embeddings = await self._embed_texts_in_batches(texts, "crawl_url")
            # Index in vector store
            self._send_progress("crawl_url", len(successful_results), len(successful_results),
                              "Indexing documents...")

            index_result = await self.qdrant_manager.index_documents(
                collection_name=collection_name,
                chunks=all_chunks,
                embeddings=embeddings
            )

            if index_result["status"] == "success":
                self.active_collections[collection_name] = "website"

                # Get crawl stats
                stats = self.web_crawler.get_crawl_stats(crawl_results)

                return {
                    "status": "success",
                    "message": "Successfully crawled and indexed website",
                    "collection_name": collection_name,
                    "crawled_pages": len(successful_results),
                    "failed_pages": len(crawl_results) - len(successful_results),
                    "total_chunks": len(all_chunks),
                    "indexed_count": index_result["indexed_count"],
                    "stats": stats
                }
            else:
                return {
                    "status": "error",
                    "message": f"Indexing failed: {index_result['message']}",
                    "crawled_pages": len(successful_results),
                    "total_chunks": len(all_chunks)
                }

        except Exception as e:
            logger.error(f"Website crawling failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "crawled_pages": 0,
                "total_chunks": 0
            }

    async def query_documents(self, question: str, collection_name: str = "documents") -> dict[str, Any]:
        """
        Query documents using RAG.

        Args:
            question: User question
            collection_name: Collection to query

        Returns:
            Query result dictionary
        """
        try:
            if collection_name not in self.active_collections:
                return {
                    "status": "error",
                    "message": f"Collection '{collection_name}' not found. Please process documents first.",
                    "answer": "",
                    "sources": []
                }

            logger.info(f"Processing query for collection '{collection_name}': {question}")

            # Create retrieval chain
            retrieval_chain = create_retrieval_chain(collection_name, config=self.config)

            # Process query
            response = await retrieval_chain.query(question)

            # Close chain resources
            retrieval_chain.close()

            return {
                "status": "success",
                "answer": response.answer,
                "sources": response.sources,
                "confidence": response.confidence,
                "question": question,
                "collection_name": collection_name
            }

        except Exception as e:
            logger.error(f"Query processing failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "answer": "",
                "sources": []
            }

    async def list_collections(self) -> dict[str, Any]:
        """list active collections"""
        try:
            collections_info = []
            for name, source_type in self.active_collections.items():
                info = await self.qdrant_manager.get_collection_info(name)
                if info:
                    info["source_type"] = source_type
                    collections_info.append(info)

            return {
                "status": "success",
                "collections": collections_info
            }

        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return {
                "status": "error",
                "message": str(e),
                "collections": []
            }

    async def process_command(self, command_data: dict[str, Any]) -> None:
        """
        Process a command from frontend.

        Args:
            command_data: Command data with 'command' field and parameters
        """
        command = command_data.get('command')

        try:
            if command == 'process_files':
                file_paths = command_data.get('file_paths', [])
                collection_name = command_data.get('collection_name', 'documents')
                result = await self.process_files(file_paths, collection_name)

            elif command == 'crawl_url':
                url = command_data.get('url')
                collection_name = command_data.get('collection_name', 'website')
                if not url:
                    raise ValueError("URL is required for crawl_url command")
                result = await self.crawl_website(url, collection_name)

            elif command == 'query':
                question = command_data.get('question')
                collection_name = command_data.get('collection_name', 'documents')
                if not question:
                    raise ValueError("Question is required for query command")
                result = await self.query_documents(question, collection_name)

            elif command == 'list_collections':
                result = await self.list_collections()

            else:
                result = {
                    "status": "error",
                    "message": f"Unknown command: {command}"
                }

            # Add command to response for frontend routing
            result["command"] = command or "unknown"
            self._send_response(result)

        except Exception as e:
            logger.error(f"Command processing failed for '{command}': {e}")
            self._send_error(str(e), command or "unknown")


async def main():
    """
    Main event loop for backend communication.
    Reads JSON commands from stdin and processes them.
    """
    backend = DocumentAssistantBackend()

    logger.info("AI Document Assistant Backend started")
    logger.info("Ready to receive commands from frontend...")

    try:
        while True:
            # PATTERN: Read JSON from stdin
            line = sys.stdin.readline().strip()

            if not line:
                # EOF reached, exit gracefully
                break

            try:
                request = json.loads(line)
                await backend.process_command(request)

            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON received: {e}")
                backend._send_error(f"Invalid JSON: {str(e)}")

            except Exception as e:
                logger.error(f"Unexpected error processing command: {e}")
                backend._send_error(f"Processing error: {str(e)}")

    except KeyboardInterrupt:
        logger.info("Backend shutting down...")

    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}")
        sys.exit(1)

    finally:
        # Cleanup resources
        try:
            backend.qdrant_manager.close()
        except Exception:
            pass

        logger.info("Backend shutdown complete")


if __name__ == "__main__":
    # Validate configuration
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"Configuration validation failed: {e}")
        logger.warning("Please check your environment variables and try again.")
        sys.exit(1)

    try:
        asyncio.run(main())
    except Exception as e:
        logger.error(f"Failed to start backend: {e}")
        sys.exit(1)
