"""
Query routes for document Q&A.
"""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from models.requests import QueryRequest
from models.responses import QueryResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def query_documents(
    request_data: QueryRequest,
    request: Request
):
    """Synchronous document query"""
    try:
        query_service = request.app.state.query_service

        logger.info(f"Processing query: {request_data.question}")

        # Process query
        result = await query_service.query_documents(
            question=request_data.question,
            collection_name=request_data.collection_name
        )

        return QueryResponse(
            answer=result.answer,
            sources=result.sources,
            confidence=result.confidence,
            collection_name=request_data.collection_name,
            question=result.question
        )

    except Exception as e:
        logger.error(f"Query processing failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/query/stream")
async def query_documents_stream(
    request_data: QueryRequest,
    request: Request
):
    """Streaming document query with real-time response"""

    async def generate_response():
        try:
            query_service = request.app.state.query_service

            logger.info(f"Processing streaming query: {request_data.question}")

            async for chunk in query_service.query_documents_stream(
                question=request_data.question,
                collection_name=request_data.collection_name
            ):
                yield f"data: {chunk.model_dump_json()}\n\n"

        except Exception as e:
            logger.error(f"Streaming query failed: {e}")
            error_chunk = {"type": "error", "error": str(e)}
            yield f"data: {json.dumps(error_chunk)}\n\n"

    return StreamingResponse(
        generate_response(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        }
    )
