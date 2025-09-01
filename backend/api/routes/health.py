"""
Health check routes.
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health_check(request: Request):
    return {
        "status": "ok",
        "version": "0.1.0",
    }
