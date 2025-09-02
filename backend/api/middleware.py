"""
API middleware for unified response handling and error management.
"""

import json
import logging

from fastapi import HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from models.api_response import ApiResponse, ResponseCode

logger = logging.getLogger(__name__)


class UnifiedResponseMiddleware(BaseHTTPMiddleware):
    """
    Middleware to ensure all responses follow the unified format.

    This middleware:
    1. Wraps successful responses in the unified format if not already wrapped
    2. Handles exceptions and converts them to unified error responses
    3. Adds request/response logging
    """

    async def dispatch(self, request: Request, call_next):
        """Process request and response"""
        try:
            # Process the request
            response = await call_next(request)
            # skip /openapi.json
            if "/openapi.json" in request.url.path:
                return response

            # Skip SSE
            if getattr(response, "media_type", "") == "text/event-stream":
                return response

            # Skip file download
            if "attachment" in response.headers.get("content-disposition", ""):
                return response

            # Skip non json
            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("application/json"):
                return response

            if hasattr(response, "body_iterator"):
                chunks = []
                async for chunk in response.body_iterator:
                    if isinstance(chunk, bytes):
                        chunks.append(chunk)
                raw_data = b"".join(chunks).decode("utf-8")
            else:
                body = response.body
                if isinstance(body, memoryview):
                    body = body.tobytes()
                raw_data = body.decode("utf-8")

            return JSONResponse(
                content=ApiResponse.success(data=json.loads(raw_data)).model_dump(),
                status_code=response.status_code
            )

        except HTTPException as e:
            # Handle HTTP exceptions
            return self._create_error_response(e.status_code, e.detail)

        except ValidationError as e:
            # Handle Pydantic validation errors
            logger.warning(f"Validation error: {e}")
            return self._create_error_response(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=self._format_validation_error(e),
                response_code=ResponseCode.VALIDATION_ERROR
            )

        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unhandled exception: {e}", exc_info=True)
            return self._create_error_response(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error",

                response_code=ResponseCode.INTERNAL_ERROR
            )

    def _create_error_response(
        self,
        status_code: int,
        detail: str,
        response_code: ResponseCode | None = None
    ) -> JSONResponse:
        """Create unified error response"""

        # Map HTTP status codes to response codes
        if response_code is None:
            mapping = {
                status.HTTP_404_NOT_FOUND: ResponseCode.NOT_FOUND,
                status.HTTP_400_BAD_REQUEST: ResponseCode.INVALID_REQUEST,
                status.HTTP_401_UNAUTHORIZED: ResponseCode.UNAUTHORIZED,
                status.HTTP_403_FORBIDDEN: ResponseCode.FORBIDDEN,
                status.HTTP_409_CONFLICT: ResponseCode.CONFLICT,
                status.HTTP_422_UNPROCESSABLE_ENTITY: ResponseCode.VALIDATION_ERROR,
                status.HTTP_503_SERVICE_UNAVAILABLE: ResponseCode.SERVICE_UNAVAILABLE,
            }
            response_code = mapping.get(status_code, ResponseCode.INTERNAL_ERROR)

        error_response = ApiResponse.error(response_code, detail)

        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status_code
        )

    def _format_validation_error(self, error: ValidationError) -> str:
        """Format Pydantic validation error for user-friendly message"""
        errors = error.errors()
        if len(errors) == 1:
            err = errors[0]
            field = " -> ".join(str(loc) for loc in err["loc"])
            return f"Validation error in field '{field}': {err['msg']}"
        else:
            return f"Validation failed with {len(errors)} errors"


