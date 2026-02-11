from fastapi import HTTPException, status


class DatabaseConnectionError(Exception):
    """Custom exception for database connection issues."""
    pass


class CredentialsException(HTTPException):
    """Custom exception for authentication credentials issues."""
    def __init__(self, detail: str = "Could not validate credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )