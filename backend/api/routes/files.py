"""
File processing routes.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import StreamingResponse

from models.requests import ProcessFilesRequest
from models.responses import ProcessFilesResponse
from models.streaming import ProgressChunk

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/files/process", response_model=ProcessFilesResponse)
async def process_files(
    request_data: ProcessFilesRequest,
    request: Request,
    background_tasks: BackgroundTasks
):
    """Process files and index them in vector store"""
    try:
        document_service = request.app.state.document_service
        collection_service = request.app.state.collection_service

        logger.info(f"Processing files: {request_data.file_paths}")

        # Process files
        result = await document_service.process_files(
            file_paths=request_data.file_paths,
            collection_name=request_data.collection_name
        )

        if result.success:
            # Register the collection with collection service
            collection_service.register_collection(
                collection_name=result.collection_name,
                source_type="files"
            )

        return ProcessFilesResponse(
            success=result.success,
            collection_name=result.collection_name,
            processed_files=result.processed_count,
            total_files=result.total_count,
            total_chunks=result.total_chunks,
            indexed_count=result.indexed_count,
            message=result.message
        )

    except Exception as e:
        logger.error(f"File processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/files/process/stream")
async def process_files_stream(
    request_data: ProcessFilesRequest,
    request: Request
):
    """Process files with streaming progress updates"""

    async def generate_progress():
        try:
            document_service = request.app.state.document_service
            collection_service = request.app.state.collection_service

            # Progress callback
            def progress_callback(message: str, current: int, total: int):
                progress_chunk = ProgressChunk(
                    message=message,
                    current=current,
                    total=total
                )
                return f"data: {progress_chunk.model_dump_json()}\n\n"

            # Yield initial progress
            yield progress_callback("开始处理文件...", 0, len(request_data.file_paths))

            # Process files with progress updates
            result = await document_service.process_files(
                file_paths=request_data.file_paths,
                collection_name=request_data.collection_name,
                progress_callback=lambda msg, cur, tot: None  # We'll handle progress differently
            )

            if result.success:
                # Register the collection
                collection_service.register_collection(
                    collection_name=result.collection_name,
                    source_type="files"
                )

                # Send final result
                final_result = ProcessFilesResponse(
                    success=result.success,
                    collection_name=result.collection_name,
                    processed_files=result.processed_count,
                    total_files=result.total_count,
                    total_chunks=result.total_chunks,
                    indexed_count=result.indexed_count,
                    message=result.message
                )
                yield f"data: {final_result.model_dump_json()}\n\n"
            else:
                # Send error result
                error_result = ProcessFilesResponse(
                    success=False,
                    collection_name=request_data.collection_name,
                    processed_files=0,
                    total_files=0,
                    total_chunks=0,
                    indexed_count=0,
                    message=result.message
                )
                yield f"data: {error_result.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"Streaming file processing failed: {e}")
            error_chunk = {"type": "error", "error": str(e)}
            yield f"data: {error_chunk}\n\n"

    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
