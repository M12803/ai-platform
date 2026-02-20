"""
Operations API routes.
All routes delegate entirely to OperationService / OrchestrationService.
No business logic lives here.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.logging import get_logger
from app.core.security import require_api_key
from app.schemas.request_schema import ClassifyRequest, SummarizeRequest, TranslateRequest
from app.schemas.response_schema import (
    ClassifyResponse,
    ErrorResponse,
    SummarizeResponse,
    TranslateResponse,
)
from app.services.limit_service import LimitExceededError
from app.services.operation_service import OperationService
from app.services.orchestration_service import OrchestrationError

logger = get_logger(__name__)

router = APIRouter(prefix="/operations", tags=["Operations"])


def _handle_operation_errors(exc: Exception) -> None:
    """Translate service-layer exceptions to HTTP responses."""
    if isinstance(exc, LimitExceededError):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(exc),
        )
    if isinstance(exc, OrchestrationError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        )
    logger.exception("Unexpected error during operation.")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An unexpected internal error occurred.",
    )


@router.post(
    "/summarize",
    response_model=SummarizeResponse,
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Summarize text",
    description=(
        "Generates a concise summary of the provided text. "
        "Input length is hard-capped at 8000 characters."
    ),
)
async def summarize(
    body: SummarizeRequest,
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> SummarizeResponse:
    try:
        return await OperationService.summarize(body, session)
    except (LimitExceededError, OrchestrationError) as exc:
        _handle_operation_errors(exc)
    except Exception as exc:
        _handle_operation_errors(exc)


@router.post(
    "/translate",
    response_model=TranslateResponse,
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Translate text",
    description=(
        "Translates text between supported languages. "
        "Supported: en, ar, fr, de, es, zh, ja, ko, ru, pt. "
        "Input length is hard-capped at 4000 characters."
    ),
)
async def translate(
    body: TranslateRequest,
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> TranslateResponse:
    try:
        return await OperationService.translate(body, session)
    except (LimitExceededError, OrchestrationError) as exc:
        _handle_operation_errors(exc)
    except Exception as exc:
        _handle_operation_errors(exc)


@router.post(
    "/classify",
    response_model=ClassifyResponse,
    responses={
        422: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
    summary="Classify text",
    description=(
        "Classifies text into one of the provided category labels. "
        "Requires at least 2 unique category labels. "
        "Input length is hard-capped at 2000 characters."
    ),
)
async def classify(
    body: ClassifyRequest,
    session: AsyncSession = Depends(get_session),
    _api_key: str = Depends(require_api_key),
) -> ClassifyResponse:
    try:
        return await OperationService.classify(body, session)
    except (LimitExceededError, OrchestrationError) as exc:
        _handle_operation_errors(exc)
    except Exception as exc:
        _handle_operation_errors(exc)
