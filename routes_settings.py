"""
Settings & platform info routes.
Exposes read-only platform metadata (version, operation map, etc.).
"""
from typing import Any, Dict

from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import require_api_key
from app.health.health_check import HealthCheck
from app.schemas.response_schema import HealthResponse

router = APIRouter(tags=["Platform"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Platform health check",
    description="Returns system status, memory usage, CPU, uptime, and loaded model status.",
)
async def health() -> HealthResponse:
    # Health check is intentionally unauthenticated so load balancers can poll it.
    return HealthCheck.get_health()


@router.get(
    "/settings",
    summary="Platform settings",
    description="Returns non-sensitive platform configuration.",
    dependencies=[Depends(require_api_key)],
)
async def get_settings() -> Dict[str, Any]:
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "supported_operations": list(settings.OPERATION_MODEL_MAP.keys()),
        "max_input_chars": settings.MAX_INPUT_CHARS,
        "max_output_tokens": settings.MAX_OUTPUT_TOKENS,
        "default_daily_limit": settings.DEFAULT_DAILY_LIMIT,
    }
