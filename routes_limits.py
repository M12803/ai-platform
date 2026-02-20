"""
Limits & Usage management routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security import require_api_key
from app.schemas.request_schema import UpdateLimitRequest
from app.schemas.response_schema import LimitsResponse, UsageResponse
from app.services.limit_service import LimitService

router = APIRouter(prefix="/limits", tags=["Limits & Usage"])


@router.get(
    "",
    response_model=LimitsResponse,
    summary="Get all operation limits",
    description="Returns per-operation daily request limits and hard token/char caps.",
)
async def get_limits(
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> LimitsResponse:
    return await LimitService.get_limits_response(session)


@router.put(
    "",
    response_model=LimitsResponse,
    summary="Update an operation's daily limit",
    description="Update the daily request limit for a specific operation. Set to 0 to disable.",
)
async def update_limit(
    body: UpdateLimitRequest,
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> LimitsResponse:
    await LimitService.update_limit(session, body.operation, body.daily_limit)
    return await LimitService.get_limits_response(session)


@router.get(
    "/usage",
    response_model=UsageResponse,
    summary="Get today's usage statistics",
    description="Returns today's request count and token usage per operation.",
)
async def get_usage(
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> UsageResponse:
    return await LimitService.get_usage_response(session)
