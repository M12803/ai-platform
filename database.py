"""
Database layer: SQLite via SQLAlchemy async.
Tables:
  - operation_limits  : per-operation daily limits (admin-configurable)
  - usage_log         : per-request log with token counts
"""
from datetime import date, datetime
from typing import AsyncGenerator

from sqlalchemy import (
    Column, Date, DateTime, Float, Integer, String, select, update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionFactory = async_sessionmaker(
    bind=_engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


class Base(DeclarativeBase):
    pass


class OperationLimit(Base):
    __tablename__ = "operation_limits"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    operation: str = Column(String(64), unique=True, nullable=False, index=True)
    daily_limit: int = Column(Integer, nullable=False, default=1000)
    updated_at: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_log"

    id: int = Column(Integer, primary_key=True, autoincrement=True)
    operation: str = Column(String(64), nullable=False, index=True)
    log_date: date = Column(Date, nullable=False, index=True)
    request_count: int = Column(Integer, nullable=False, default=0)
    total_tokens: int = Column(Integer, nullable=False, default=0)
    last_updated: datetime = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


async def init_db() -> None:
    """Create tables and seed default limits."""
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionFactory() as session:
        for operation in settings.OPERATION_MODEL_MAP:
            result = await session.execute(
                select(OperationLimit).where(OperationLimit.operation == operation)
            )
            existing = result.scalar_one_or_none()
            if not existing:
                session.add(
                    OperationLimit(
                        operation=operation,
                        daily_limit=settings.DEFAULT_DAILY_LIMIT,
                    )
                )
        await session.commit()
    logger.info("Database initialised at: %s", settings.DB_PATH)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionFactory() as session:
        yield session
