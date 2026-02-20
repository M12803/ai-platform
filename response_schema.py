"""
Strict Pydantic response schemas for all operations and management endpoints.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ── Operation responses ───────────────────────────────────────────────────────

class OperationMeta(BaseModel):
    operation: str
    model_used: str
    input_chars: int
    output_tokens: int
    execution_time_ms: float
    request_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class SummarizeResponse(BaseModel):
    summary: str
    sentence_count: int
    meta: OperationMeta


class TranslateResponse(BaseModel):
    translated_text: str
    source_language: str
    target_language: str
    meta: OperationMeta


class ClassifyResponse(BaseModel):
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    scores: Dict[str, float]
    meta: OperationMeta


# ── Health check ──────────────────────────────────────────────────────────────

class ModelStatus(BaseModel):
    name: str
    loaded: bool
    path: str


class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    memory_used_mb: float
    memory_total_mb: float
    cpu_percent: float
    models: List[ModelStatus]
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Limits & usage ────────────────────────────────────────────────────────────

class OperationLimit(BaseModel):
    operation: str
    daily_limit: int
    max_input_chars: int
    max_output_tokens: int


class LimitsResponse(BaseModel):
    limits: List[OperationLimit]


class OperationUsage(BaseModel):
    operation: str
    date: str
    request_count: int
    total_tokens: int
    daily_limit: int
    remaining: int


class UsageResponse(BaseModel):
    usage: List[OperationUsage]
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Generic error ─────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[Any] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
