"""
Health check routes.
"""

from fastapi import APIRouter, Request

from api.response_utils import success_response

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    return success_response(data={
        "status": "ok",
        "version": "0.1.0",
    })
