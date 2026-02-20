"""
OperationService: thin application-layer facade over the orchestrator.
Exists to keep routes free of direct orchestrator imports and to allow
future middleware injection (auth context, audit, etc.) without touching routes.
"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.request_schema import ClassifyRequest, SummarizeRequest, TranslateRequest
from app.schemas.response_schema import ClassifyResponse, SummarizeResponse, TranslateResponse
from app.services.orchestration_service import OrchestrationService


class OperationService:

    @staticmethod
    async def summarize(request: SummarizeRequest, session: AsyncSession) -> SummarizeResponse:
        return await OrchestrationService.summarize(request, session)

    @staticmethod
    async def translate(request: TranslateRequest, session: AsyncSession) -> TranslateResponse:
        return await OrchestrationService.translate(request, session)

    @staticmethod
    async def classify(request: ClassifyRequest, session: AsyncSession) -> ClassifyResponse:
        return await OrchestrationService.classify(request, session)
