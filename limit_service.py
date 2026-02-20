"""
LimitService: manages per-operation daily request limits and usage tracking.
All reads/writes go through SQLite.
"""
from datetime import date
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import OperationLimit, UsageLog
from app.core.logging import get_logger
from app.schemas.response_schema import LimitsResponse, OperationLimit as OpLimitSchema
from app.schemas.response_schema import OperationUsage, UsageResponse

logger = get_logger(__name__)


class LimitExceededError(Exception):
    def __init__(self, operation: str, used: int, limit: int) -> None:
        self.operation = operation
        self.used = used
        self.limit = limit
        super().__init__(
            f"Daily limit exceeded for operation '{operation}': "
            f"{used}/{limit} requests used today."
        )


class LimitService:

    @staticmethod
    async def get_daily_limit(session: AsyncSession, operation: str) -> int:
        result = await session.execute(
            select(OperationLimit.daily_limit).where(
                OperationLimit.operation == operation
            )
        )
        row = result.scalar_one_or_none()
        return row if row is not None else settings.DEFAULT_DAILY_LIMIT

    @staticmethod
    async def _get_or_create_usage(
        session: AsyncSession, operation: str, today: date
    ) -> UsageLog:
        result = await session.execute(
            select(UsageLog).where(
                UsageLog.operation == operation,
                UsageLog.log_date == today,
            )
        )
        usage = result.scalar_one_or_none()
        if usage is None:
            usage = UsageLog(operation=operation, log_date=today, request_count=0, total_tokens=0)
            session.add(usage)
            await session.flush()
        return usage

    @classmethod
    async def check_and_increment(
        cls,
        session: AsyncSession,
        operation: str,
        tokens_used: int = 0,
    ) -> None:
        """
        Verify the daily limit is not exceeded, then record the request.
        Must be called BEFORE running inference so we fail fast.

        Raises:
            LimitExceededError if daily limit is reached.
        """
        today = date.today()
        daily_limit = await cls.get_daily_limit(session, operation)

        if daily_limit == 0:
            # 0 means disabled / no limit.
            return

        usage = await cls._get_or_create_usage(session, operation, today)

        if usage.request_count >= daily_limit:
            raise LimitExceededError(operation, usage.request_count, daily_limit)

        usage.request_count += 1
        usage.total_tokens += tokens_used
        await session.commit()
        logger.debug(
            "Usage recorded | op=%s | req=%d/%d | tokens=%d",
            operation,
            usage.request_count,
            daily_limit,
            usage.total_tokens,
        )

    @classmethod
    async def record_tokens(
        cls, session: AsyncSession, operation: str, tokens: int
    ) -> None:
        """Update token count after inference completes."""
        today = date.today()
        usage = await cls._get_or_create_usage(session, operation, today)
        usage.total_tokens += tokens
        await session.commit()

    @classmethod
    async def update_limit(
        cls, session: AsyncSession, operation: str, daily_limit: int
    ) -> None:
        await session.execute(
            update(OperationLimit)
            .where(OperationLimit.operation == operation)
            .values(daily_limit=daily_limit)
        )
        await session.commit()
        logger.info("Daily limit for '%s' updated to %d.", operation, daily_limit)

    @classmethod
    async def get_limits_response(cls, session: AsyncSession) -> LimitsResponse:
        results = await session.execute(select(OperationLimit))
        rows = results.scalars().all()
        limits = [
            OpLimitSchema(
                operation=row.operation,
                daily_limit=row.daily_limit,
                max_input_chars=settings.MAX_INPUT_CHARS.get(row.operation, 0),
                max_output_tokens=settings.MAX_OUTPUT_TOKENS.get(row.operation, 0),
            )
            for row in rows
        ]
        return LimitsResponse(limits=limits)

    @classmethod
    async def get_usage_response(cls, session: AsyncSession) -> UsageResponse:
        today = date.today()
        results = await session.execute(
            select(UsageLog).where(UsageLog.log_date == today)
        )
        rows = results.scalars().all()

        usage_list: List[OperationUsage] = []
        for row in rows:
            daily_limit = await cls.get_daily_limit(session, row.operation)
            remaining = max(0, daily_limit - row.request_count) if daily_limit > 0 else -1
            usage_list.append(
                OperationUsage(
                    operation=row.operation,
                    date=str(today),
                    request_count=row.request_count,
                    total_tokens=row.total_tokens,
                    daily_limit=daily_limit,
                    remaining=remaining,
                )
            )
        return UsageResponse(usage=usage_list)
