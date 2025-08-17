"""
Utility functions for creating unified API responses.
"""

from typing import Any, TypeVar

from fastapi import HTTPException, status
from fastapi.responses import JSONResponse

from models.api_response import ApiResponse, ResponseCode

T = TypeVar('T')


def success_response(data: T = None, message: str = "") -> dict:
    """
    Create a successful response.

    Args:
        data: Response data
        message: Optional success message

    Returns:
        Dict representation of successful response
    """
    response = ApiResponse.success(data=data, message=message)
    return response.model_dump()


def error_response(
    code: ResponseCode,
    message: str,
    data: Any = None,
    status_code: int = None
) -> JSONResponse:
    """
    Create an error response with appropriate HTTP status code.

    Args:
        code: Business error code
        message: Error message
        data: Optional error data
        status_code: HTTP status code (auto-determined if not provided)

    Returns:
        JSONResponse with error details
    """
    if status_code is None:
        status_code = _get_http_status_from_code(code)

    response = ApiResponse.error(code, message, data)
    return JSONResponse(
        content=response.model_dump(),
        status_code=status_code
    )


def not_found_response(message: str = "Resource not found") -> JSONResponse:
    """Create a 404 not found response"""
    return error_response(
        ResponseCode.NOT_FOUND,
        message,
        status_code=status.HTTP_404_NOT_FOUND
    )


def validation_error_response(message: str) -> JSONResponse:
    """Create a 422 validation error response"""
    return error_response(
        ResponseCode.VALIDATION_ERROR,
        message,
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )


def internal_error_response(message: str = "Internal server error") -> JSONResponse:
    """Create a 500 internal error response"""
    return error_response(
        ResponseCode.INTERNAL_ERROR,
        message,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
    )


def service_unavailable_response(message: str = "Service unavailable") -> JSONResponse:
    """Create a 503 service unavailable response"""
    return error_response(
        ResponseCode.SERVICE_UNAVAILABLE,
        message,
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE
    )


def _get_http_status_from_code(code: ResponseCode) -> int:
    """Map response code to HTTP status code"""
    mapping = {
        ResponseCode.SUCCESS: status.HTTP_200_OK,
        ResponseCode.INVALID_REQUEST: status.HTTP_400_BAD_REQUEST,
        ResponseCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
        ResponseCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
        ResponseCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
        ResponseCode.CONFLICT: status.HTTP_409_CONFLICT,
        ResponseCode.VALIDATION_ERROR: status.HTTP_422_UNPROCESSABLE_ENTITY,
        ResponseCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ResponseCode.SERVICE_UNAVAILABLE: status.HTTP_503_SERVICE_UNAVAILABLE,
        ResponseCode.DATABASE_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
        ResponseCode.EXTERNAL_SERVICE_ERROR: status.HTTP_502_BAD_GATEWAY,
    }
    return mapping.get(code, status.HTTP_500_INTERNAL_SERVER_ERROR)


# Convenience functions for raising HTTP exceptions with unified format
def raise_not_found(message: str = "Resource not found"):
    """Raise HTTP 404 exception"""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=message)


def raise_validation_error(message: str):
    """Raise HTTP 422 exception"""
    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message
    )


def raise_internal_error(message: str = "Internal server error"):
    """Raise HTTP 500 exception"""
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=message
    )


def raise_service_unavailable(message: str = "Service unavailable"):
    """Raise HTTP 503 exception"""
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=message
    )
