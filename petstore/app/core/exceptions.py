from fastapi import status

class AppException(Exception):
    """Base exception class for application-specific errors."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(self.detail)

class NotFoundException(AppException):
    """Raised when a resource is not found."""
    def __init__(self, detail: str = "Resource not found."):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)

class ConflictException(AppException):
    """Raised when there's a conflict with the current state of the resource."""
    def __init__(self, detail: str = "Resource conflict."):
        super().__init__(status.HTTP_409_CONFLICT, detail)

class ValidationException(AppException):
    """Raised for business logic validation errors."""
    def __init__(self, detail: str = "Validation failed."):
        super().__init__(status.HTTP_422_UNPROCESSABLE_ENTITY, detail)

class UnauthorizedException(AppException):
    """Raised when authentication credentials are missing or invalid."""
    def __init__(self, detail: str = "Could not validate credentials."):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)

class ForbiddenException(AppException):
    """Raised when authenticated user does not have permission to access a resource."""
    def __init__(self, detail: str = "Not enough permissions."):
        super().__init__(status.HTTP_403_FORBIDDEN, detail)

class InternalServerError(AppException):
    """Raised for unexpected internal server errors."""
    def __init__(self, detail: str = "Internal server error."):
        super().__init__(status.HTTP_500_INTERNAL_SERVER_ERROR, detail)