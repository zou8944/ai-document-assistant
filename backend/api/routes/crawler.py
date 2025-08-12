"""
Web crawler routes.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from models.requests import CrawlWebsiteRequest
from models.responses import CrawlWebsiteResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/crawler/crawl", response_model=CrawlWebsiteResponse)
async def crawl_website(
    request_data: CrawlWebsiteRequest,
    request: Request
):
    """Crawl website and index content"""
    try:
        document_service = request.app.state.document_service
        collection_service = request.app.state.collection_service

        logger.info(f"Crawling website: {request_data.url}")

        # Crawl website
        result = await document_service.crawl_website(
            url=request_data.url,
            collection_name=request_data.collection_name
        )

        if result.success:
            # Register the collection with collection service
            collection_service.register_collection(
                collection_name=result.collection_name,
                source_type="website"
            )

        return CrawlWebsiteResponse(
            success=result.success,
            collection_name=result.collection_name,
            crawled_pages=result.crawled_pages,
            failed_pages=result.failed_pages,
            total_chunks=result.total_chunks,
            indexed_count=result.indexed_count,
            stats=result.stats,
            message=result.message
        )

    except Exception as e:
        logger.error(f"Website crawling failed: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
