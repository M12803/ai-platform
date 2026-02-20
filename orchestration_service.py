"""
OrchestrationService: the central brain of the platform.

Responsibilities:
  - Select correct model per operation
  - Enforce hard limits from config
  - Check daily usage limits (via LimitService)
  - Load model lazily (via ModelRegistry)
  - Execute inference (via InferenceEngine)
  - Log every execution
  - Handle and wrap all exceptions uniformly
"""
import json
import time
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.models.inference_engine import (
    InferenceEngine,
    build_classify_prompt,
    build_summarize_prompt,
    build_translate_prompt,
)
from app.models.model_registry import model_registry
from app.schemas.request_schema import ClassifyRequest, SummarizeRequest, TranslateRequest
from app.schemas.response_schema import (
    ClassifyResponse,
    OperationMeta,
    SummarizeResponse,
    TranslateResponse,
)
from app.services.limit_service import LimitExceededError, LimitService

logger = get_logger(__name__)


class OrchestrationError(Exception):
    """Raised when orchestration cannot complete the request."""


class OrchestrationService:
    """
    Stateless orchestrator.  Each method corresponds to one operation.
    No business logic lives in API routes.
    """

    @staticmethod
    def _get_model_folder(operation: str) -> str:
        folder = settings.OPERATION_MODEL_MAP.get(operation)
        if not folder:
            raise OrchestrationError(
                f"No model configured for operation '{operation}'."
            )
        return folder

    @staticmethod
    def _validate_input_length(operation: str, text: str) -> None:
        max_chars = settings.MAX_INPUT_CHARS.get(operation, 0)
        if max_chars and len(text) > max_chars:
            raise OrchestrationError(
                f"Input exceeds hard limit for '{operation}': "
                f"{len(text)} > {max_chars} characters."
            )

    # ── Summarize ─────────────────────────────────────────────────────────────

    @classmethod
    async def summarize(
        cls,
        request: SummarizeRequest,
        session: AsyncSession,
    ) -> SummarizeResponse:
        operation = "summarize"
        start = time.perf_counter()

        cls._validate_input_length(operation, request.text)

        try:
            await LimitService.check_and_increment(session, operation)
        except LimitExceededError as exc:
            logger.warning("Limit exceeded | op=%s", operation)
            raise

        model_folder = cls._get_model_folder(operation)
        loaded = await model_registry.get_or_load(model_folder)

        max_tokens = settings.MAX_OUTPUT_TOKENS[operation]
        prompt = build_summarize_prompt(request.text, request.max_sentences, request.language)

        try:
            generated_text, token_count = await InferenceEngine.generate(
                loaded=loaded,
                prompt=prompt,
                max_new_tokens=max_tokens,
            )
        except Exception as exc:
            logger.exception("Inference failed | op=%s", operation)
            raise OrchestrationError(f"Inference error: {exc}") from exc

        await LimitService.record_tokens(session, operation, token_count)

        elapsed_ms = (time.perf_counter() - start) * 1000
        sentence_count = len([s for s in generated_text.split(".") if s.strip()])

        logger.info(
            "op=summarize | chars=%d | tokens=%d | time=%.1fms | request_id=%s",
            len(request.text), token_count, elapsed_ms, request.request_id,
        )

        return SummarizeResponse(
            summary=generated_text,
            sentence_count=sentence_count,
            meta=OperationMeta(
                operation=operation,
                model_used=model_folder,
                input_chars=len(request.text),
                output_tokens=token_count,
                execution_time_ms=round(elapsed_ms, 2),
                request_id=request.request_id,
            ),
        )

    # ── Translate ─────────────────────────────────────────────────────────────

    @classmethod
    async def translate(
        cls,
        request: TranslateRequest,
        session: AsyncSession,
    ) -> TranslateResponse:
        operation = "translate"
        start = time.perf_counter()

        cls._validate_input_length(operation, request.text)

        try:
            await LimitService.check_and_increment(session, operation)
        except LimitExceededError:
            logger.warning("Limit exceeded | op=%s", operation)
            raise

        model_folder = cls._get_model_folder(operation)
        loaded = await model_registry.get_or_load(model_folder)

        max_tokens = settings.MAX_OUTPUT_TOKENS[operation]
        prompt = build_translate_prompt(
            request.text, request.source_language, request.target_language
        )

        try:
            generated_text, token_count = await InferenceEngine.generate(
                loaded=loaded,
                prompt=prompt,
                max_new_tokens=max_tokens,
            )
        except Exception as exc:
            logger.exception("Inference failed | op=%s", operation)
            raise OrchestrationError(f"Inference error: {exc}") from exc

        await LimitService.record_tokens(session, operation, token_count)

        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "op=translate | src=%s | tgt=%s | chars=%d | tokens=%d | time=%.1fms",
            request.source_language, request.target_language,
            len(request.text), token_count, elapsed_ms,
        )

        return TranslateResponse(
            translated_text=generated_text,
            source_language=request.source_language,
            target_language=request.target_language,
            meta=OperationMeta(
                operation=operation,
                model_used=model_folder,
                input_chars=len(request.text),
                output_tokens=token_count,
                execution_time_ms=round(elapsed_ms, 2),
                request_id=request.request_id,
            ),
        )

    # ── Classify ──────────────────────────────────────────────────────────────

    @classmethod
    async def classify(
        cls,
        request: ClassifyRequest,
        session: AsyncSession,
    ) -> ClassifyResponse:
        operation = "classify"
        start = time.perf_counter()

        cls._validate_input_length(operation, request.text)

        try:
            await LimitService.check_and_increment(session, operation)
        except LimitExceededError:
            logger.warning("Limit exceeded | op=%s", operation)
            raise

        model_folder = cls._get_model_folder(operation)
        loaded = await model_registry.get_or_load(model_folder)

        max_tokens = settings.MAX_OUTPUT_TOKENS[operation]
        prompt = build_classify_prompt(request.text, request.categories)

        try:
            generated_text, token_count = await InferenceEngine.generate(
                loaded=loaded,
                prompt=prompt,
                max_new_tokens=max_tokens,
            )
        except Exception as exc:
            logger.exception("Inference failed | op=%s", operation)
            raise OrchestrationError(f"Inference error: {exc}") from exc

        await LimitService.record_tokens(session, operation, token_count)

        # Parse JSON response from model.
        label, confidence, scores = cls._parse_classify_output(
            generated_text, request.categories
        )

        elapsed_ms = (time.perf_counter() - start) * 1000

        logger.info(
            "op=classify | categories=%d | label=%s | conf=%.2f | tokens=%d | time=%.1fms",
            len(request.categories), label, confidence, token_count, elapsed_ms,
        )

        return ClassifyResponse(
            label=label,
            confidence=confidence,
            scores=scores,
            meta=OperationMeta(
                operation=operation,
                model_used=model_folder,
                input_chars=len(request.text),
                output_tokens=token_count,
                execution_time_ms=round(elapsed_ms, 2),
                request_id=request.request_id,
            ),
        )

    @staticmethod
    def _parse_classify_output(
        raw: str, categories: list[str]
    ) -> tuple[str, float, dict[str, float]]:
        """
        Attempt to parse model JSON output.  Falls back gracefully if the
        model returns malformed JSON.
        """
        try:
            # Strip markdown fences if present.
            cleaned = raw.strip().strip("```json").strip("```").strip()
            data = json.loads(cleaned)
            label = str(data.get("label", categories[0]))
            confidence = float(data.get("confidence", 0.5))
            confidence = max(0.0, min(1.0, confidence))

            # Ensure label is one of the provided categories (case-insensitive).
            lower_map = {c.lower(): c for c in categories}
            canonical = lower_map.get(label.lower())
            if canonical is None:
                label = categories[0]
                confidence = 0.5
            else:
                label = canonical

        except (json.JSONDecodeError, KeyError, TypeError):
            logger.warning("Could not parse classify output as JSON: %s", raw[:200])
            label = categories[0]
            confidence = 0.5

        # Build a simple scores dict: assigned label gets confidence, rest share remainder.
        remaining = (1.0 - confidence) / max(len(categories) - 1, 1)
        scores = {c: remaining for c in categories}
        scores[label] = confidence

        return label, confidence, scores
