"""
Unified API response models and utilities.
"""

from enum import Enum
from typing import Any, Generic, Optional, TypeVar

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
    """
    Unified API response model.
    
    All API endpoints should return this format for consistency.
    """
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
    def error(
        cls,
        code: ResponseCode,
        message: str,
        data: T = None
    ) -> "ApiResponse[T]":
        """Create an error response"""
        return cls(
            code=code,
            message=message,
            data=data
        )

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "ApiResponse[None]":
        """Create a not found error response"""
        return cls.error(ResponseCode.NOT_FOUND, message)

    @classmethod
    def validation_error(cls, message: str) -> "ApiResponse[None]":
        """Create a validation error response"""
        return cls.error(ResponseCode.VALIDATION_ERROR, message)

    @classmethod
    def internal_error(cls, message: str = "Internal server error") -> "ApiResponse[None]":
        """Create an internal error response"""
        return cls.error(ResponseCode.INTERNAL_ERROR, message)

    @classmethod
    def service_unavailable(cls, message: str = "Service unavailable") -> "ApiResponse[None]":
        """Create a service unavailable error response"""
        return cls.error(ResponseCode.SERVICE_UNAVAILABLE, message)


# Type aliases for common response types
ApiResponseModel = ApiResponse[Any]
SuccessResponse = ApiResponse[Any]
ErrorResponse = ApiResponse[None]


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated data wrapper"""
    items: list[T] = Field(..., description="数据项列表")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    total: int = Field(..., description="总记录数")

    @property
    def total_pages(self) -> int:
        """Calculate total pages"""
        return (self.total + self.page_size - 1) // self.page_size


class StreamEvent(BaseModel):
    """Server-Sent Events 流式响应事件"""
    event: str = Field(..., description="事件类型")
    data: dict[str, Any] = Field(..., description="事件数据")


# Common event types for streaming
class EventType:
    """Standard event types for streaming responses"""
    METADATA = "metadata"
    PROGRESS = "progress"
    CONTENT = "content"
    SOURCES = "sources"
    LOG = "log"
    ERROR = "error"
    DONE = "done"
