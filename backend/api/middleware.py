"""
API middleware for unified response handling and error management.
"""

import json
import logging
import traceback
from typing import Any

from fastapi import HTTPException, Request, Response, status
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

        # Log incoming request
        logger.info(f"{request.method} {request.url.path}")

        try:
            # Process the request
            response = await call_next(request)

            # Skip middleware for SSE streams and file downloads
            if self._should_skip_processing(request, response):
                return response

            # Check if response is already in unified format
            if response.status_code < 400:
                content = await self._get_response_content(response)
                if content and not self._is_unified_format(content):
                    # Wrap successful response in unified format
                    unified_response = ApiResponse.success(data=content)
                    return JSONResponse(
                        content=unified_response.model_dump(),
                        status_code=response.status_code,
                        headers=dict(response.headers)
                    )

            return response

        except HTTPException as e:
            # Handle HTTP exceptions
            return self._create_error_response(e.status_code, e.detail)

        except ValidationError as e:
            # Handle Pydantic validation errors
            logger.warning(f"Validation error: {e}")
            error_msg = self._format_validation_error(e)
            return self._create_error_response(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                error_msg,
                ResponseCode.VALIDATION_ERROR
            )

        except Exception as e:
            # Handle unexpected exceptions
            logger.error(f"Unhandled exception: {e}")
            logger.error(traceback.format_exc())
            return self._create_error_response(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                "Internal server error",
                ResponseCode.INTERNAL_ERROR
            )

    def _should_skip_processing(self, request: Request, response: Response) -> bool:
        """Check if response processing should be skipped"""
        # Skip for SSE streams
        if response.headers.get("content-type", "").startswith("text/event-stream"):
            return True

        # Skip for file downloads
        if "attachment" in response.headers.get("content-disposition", ""):
            return True

        # Skip for non-JSON responses
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("application/json"):
            return True

        return False

    async def _get_response_content(self, response: Response) -> Any:
        """Extract content from response"""
        if hasattr(response, 'body'):
            try:
                body = response.body
                if body:
                    return json.loads(body.decode())
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass
        return None

    def _is_unified_format(self, content: Any) -> bool:
        """Check if content is already in unified format"""
        if isinstance(content, dict):
            return "code" in content and "message" in content
        return False

    def _create_error_response(
        self,
        status_code: int,
        detail: str,
        response_code: ResponseCode = None
    ) -> JSONResponse:
        """Create unified error response"""

        # Map HTTP status codes to response codes
        if response_code is None:
            if status_code == status.HTTP_404_NOT_FOUND:
                response_code = ResponseCode.NOT_FOUND
            elif status_code == status.HTTP_400_BAD_REQUEST:
                response_code = ResponseCode.INVALID_REQUEST
            elif status_code == status.HTTP_401_UNAUTHORIZED:
                response_code = ResponseCode.UNAUTHORIZED
            elif status_code == status.HTTP_403_FORBIDDEN:
                response_code = ResponseCode.FORBIDDEN
            elif status_code == status.HTTP_409_CONFLICT:
                response_code = ResponseCode.CONFLICT
            elif status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                response_code = ResponseCode.VALIDATION_ERROR
            elif status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
                response_code = ResponseCode.SERVICE_UNAVAILABLE
            else:
                response_code = ResponseCode.INTERNAL_ERROR

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


def setup_exception_handlers(app):
    """Setup global exception handlers for the FastAPI app"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions"""
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            response_code = ResponseCode.NOT_FOUND
        elif exc.status_code == status.HTTP_400_BAD_REQUEST:
            response_code = ResponseCode.INVALID_REQUEST
        elif exc.status_code == status.HTTP_401_UNAUTHORIZED:
            response_code = ResponseCode.UNAUTHORIZED
        elif exc.status_code == status.HTTP_403_FORBIDDEN:
            response_code = ResponseCode.FORBIDDEN
        elif exc.status_code == status.HTTP_409_CONFLICT:
            response_code = ResponseCode.CONFLICT
        elif exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            response_code = ResponseCode.SERVICE_UNAVAILABLE
        else:
            response_code = ResponseCode.INTERNAL_ERROR

        error_response = ApiResponse.error(response_code, exc.detail)
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=exc.status_code
        )

    @app.exception_handler(ValidationError)
    async def validation_exception_handler(request: Request, exc: ValidationError):
        """Handle Pydantic validation exceptions"""
        logger.warning(f"Validation error: {exc}")

        # Format validation errors
        errors = exc.errors()
        if len(errors) == 1:
            err = errors[0]
            field = " -> ".join(str(loc) for loc in err["loc"])
            message = f"Validation error in field '{field}': {err['msg']}"
        else:
            message = f"Validation failed with {len(errors)} errors"

        error_response = ApiResponse.validation_error(message)
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all other exceptions"""
        logger.error(f"Unhandled exception: {exc}")
        logger.error(traceback.format_exc())

        error_response = ApiResponse.internal_error("Internal server error")
        return JSONResponse(
            content=error_response.model_dump(),
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
