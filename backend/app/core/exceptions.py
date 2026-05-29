from fastapi import HTTPException, status


class PoetryException(Exception):
    """Base platform exception."""
    def __init__(self, message: str, code: str = "PLATFORM_ERROR"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundException(PoetryException):
    def __init__(self, resource: str, identifier: str):
        super().__init__(f"{resource} not found: {identifier}", "NOT_FOUND")
        self.resource = resource
        self.identifier = identifier


class SearchException(PoetryException):
    def __init__(self, message: str):
        super().__init__(message, "SEARCH_ERROR")


class AIException(PoetryException):
    def __init__(self, message: str):
        super().__init__(message, "AI_ERROR")


class ValidationException(PoetryException):
    def __init__(self, message: str):
        super().__init__(message, "VALIDATION_ERROR")


# ── HTTP Exception factories ───────────────────────────

def not_found(resource: str, identifier: str = "") -> HTTPException:
    detail = f"{resource} غير موجود"
    if identifier:
        detail += f": {identifier}"
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def bad_request(message: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=message)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="غير مصرح",
        headers={"WWW-Authenticate": "Bearer"},
    )


def forbidden() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="ممنوع")


def rate_limited() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="تجاوزت الحد المسموح به من الطلبات",
    )
