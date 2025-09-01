"""
Unified API response models and utilities.
"""

from enum import Enum
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

# Type variable for generic response data
T = TypeVar('T')


class ResponseCode(str, Enum):
    """Standardized response codes"""
    SUCCESS = "Success"

    # Client errors (4xx)
    INVALID_REQUEST = "InvalidRequest"
    NOT_FOUND = "NotFound"
    UNAUTHORIZED = "Unauthorized"
    FORBIDDEN = "Forbidden"
    CONFLICT = "Conflict"
    VALIDATION_ERROR = "ValidationError"

    # Server errors (5xx)
    INTERNAL_ERROR = "InternalError"
    SERVICE_UNAVAILABLE = "ServiceUnavailable"
    DATABASE_ERROR = "DatabaseError"
    EXTERNAL_SERVICE_ERROR = "ExternalServiceError"


class ApiResponse(BaseModel, Generic[T]):
    code: ResponseCode = Field(..., description="业务状态码")
    message: str = Field(..., description="响应消息，成功时为空字符串，失败时为详细错误信息")
    data: Optional[T] = Field(None, description="响应数据，仅在成功时返回")

    @classmethod
    def success(cls, data: T = None, message: str = "") -> "ApiResponse[T]":
        """Create a successful response"""
        return cls(
            code=ResponseCode.SUCCESS,
            message=message,
            data=data
        )

    @classmethod
    def error(cls, code: ResponseCode, message: str, data: T = None) -> "ApiResponse[T]":
        """Create an error response"""
        return cls(
            code=code,
            message=message,
            data=data
        )
