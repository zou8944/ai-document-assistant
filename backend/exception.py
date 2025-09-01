
from fastapi import HTTPException


class HTTPBadRequestException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=400, detail=detail)

class HTTPNotFoundException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=404, detail=detail)

class HTTPValidationException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=422, detail=detail)

class HTTPConflictException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=409, detail=detail)

class HTTPInternalServerErrorException(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=500, detail=detail)
