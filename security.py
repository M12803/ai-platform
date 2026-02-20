"""
Security layer: API key validation via FastAPI dependency injection.
"""
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_api_key_scheme = APIKeyHeader(name=settings.API_KEY_HEADER, auto_error=True)


async def require_api_key(api_key: str = Security(_api_key_scheme)) -> str:
    """
    FastAPI dependency that validates the incoming API key.

    Raises:
        HTTPException 403 if the key is absent or invalid.
    """
    if api_key not in settings.VALID_API_KEYS:
        logger.warning("Rejected request with invalid API key: %s…", api_key[:8])
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid or missing API key.",
        )
    return api_key
