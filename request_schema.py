"""
Strict Pydantic request schemas for all operations.
Every field is explicitly typed and validated.
"""
from typing import Annotated, Literal, Optional
from pydantic import BaseModel, Field, field_validator


# ── Shared base ───────────────────────────────────────────────────────────────

class BaseOperationRequest(BaseModel):
    """Common fields shared by all operation requests."""

    model_config = {"strict": True}

    request_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Optional caller-supplied idempotency / tracing ID.",
    )


# ── Summarize ─────────────────────────────────────────────────────────────────

class SummarizeRequest(BaseOperationRequest):
    text: Annotated[
        str,
        Field(
            min_length=50,
            max_length=8000,
            description="The text to summarize (50–8000 characters).",
        ),
    ]
    max_sentences: Annotated[
        int,
        Field(
            default=5,
            ge=1,
            le=20,
            description="Target number of sentences in the summary.",
        ),
    ]
    language: Annotated[
        str,
        Field(
            default="en",
            pattern=r"^[a-z]{2}$",
            description="ISO 639-1 language code of the source text.",
        ),
    ]

    @field_validator("text")
    @classmethod
    def text_must_not_be_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not consist solely of whitespace.")
        return value.strip()


# ── Translate ─────────────────────────────────────────────────────────────────

SUPPORTED_LANGUAGES: set[str] = {
    "en", "ar", "fr", "de", "es", "zh", "ja", "ko", "ru", "pt",
}


class TranslateRequest(BaseOperationRequest):
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=4000,
            description="The text to translate (1–4000 characters).",
        ),
    ]
    source_language: Annotated[
        str,
        Field(
            pattern=r"^[a-z]{2}$",
            description="ISO 639-1 code of the source language.",
        ),
    ]
    target_language: Annotated[
        str,
        Field(
            pattern=r"^[a-z]{2}$",
            description="ISO 639-1 code of the target language.",
        ),
    ]

    @field_validator("source_language", "target_language")
    @classmethod
    def language_must_be_supported(cls, value: str) -> str:
        if value not in SUPPORTED_LANGUAGES:
            raise ValueError(
                f"Language '{value}' is not supported. "
                f"Supported languages: {sorted(SUPPORTED_LANGUAGES)}"
            )
        return value

    @field_validator("target_language")
    @classmethod
    def languages_must_differ(cls, target: str, info) -> str:
        source = info.data.get("source_language")
        if source and source == target:
            raise ValueError("source_language and target_language must differ.")
        return target

    @field_validator("text")
    @classmethod
    def text_must_not_be_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not consist solely of whitespace.")
        return value.strip()


# ── Classify ──────────────────────────────────────────────────────────────────

class ClassifyRequest(BaseOperationRequest):
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=2000,
            description="The text to classify (1–2000 characters).",
        ),
    ]
    categories: Annotated[
        list[str],
        Field(
            min_length=2,
            max_length=20,
            description="List of candidate category labels (2–20 items).",
        ),
    ]

    @field_validator("categories")
    @classmethod
    def categories_must_be_unique_and_non_empty(cls, values: list[str]) -> list[str]:
        cleaned = [c.strip() for c in values if c.strip()]
        if len(cleaned) < 2:
            raise ValueError("At least 2 non-empty category labels are required.")
        if len(cleaned) != len(set(c.lower() for c in cleaned)):
            raise ValueError("Category labels must be unique (case-insensitive).")
        return cleaned

    @field_validator("text")
    @classmethod
    def text_must_not_be_whitespace_only(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text must not consist solely of whitespace.")
        return value.strip()


# ── Limit update ──────────────────────────────────────────────────────────────

class UpdateLimitRequest(BaseModel):
    operation: Annotated[
        Literal["summarize", "translate", "classify"],
        Field(description="Operation name to update limit for."),
    ]
    daily_limit: Annotated[
        int,
        Field(ge=0, le=100_000, description="New daily request limit (0 = disabled)."),
    ]
