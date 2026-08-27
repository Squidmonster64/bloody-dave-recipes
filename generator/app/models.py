"""Pydantic schemas for Recipe Studio drafts and published records."""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class JobStatus(str, Enum):
    QUEUED = "QUEUED"
    FETCHING_SOURCE = "FETCHING_SOURCE"
    EXTRACTING = "EXTRACTING"
    NORMALISING = "NORMALISING"
    GENERATING_IMAGE = "GENERATING_IMAGE"
    RENDERING_CARD = "RENDERING_CARD"
    QA = "QA"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    PUBLISHING = "PUBLISHING"
    PUBLISHED = "PUBLISHED"
    FAILED = "FAILED"
    NEEDS_PASTED_SOURCE = "NEEDS_PASTED_SOURCE"


class MethodStage(BaseModel):
    heading: str = Field(min_length=1, max_length=80)
    directions: str = Field(min_length=1, max_length=1200)


class RecipeDraft(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    subtitle: str = Field(default="", max_length=220)
    hook: str = Field(default="", max_length=400)
    source: str = Field(min_length=1, max_length=120)
    source_url: str = Field(min_length=1, max_length=1000)
    serves: str = Field(default="2", max_length=40)
    prep_time: str = Field(default="", max_length=40)
    cook_time: str = Field(default="", max_length=40)
    total_time: str = Field(default="", max_length=40)
    cuisine: str = Field(default="Modern Australian", max_length=80)
    protein: str = Field(default="", max_length=80)
    difficulty: str = Field(default="Easy", max_length=40)
    tags: list[str] = Field(default_factory=list)
    buy: list[str] = Field(default_factory=list)
    pantry: list[str] = Field(default_factory=list)
    method: list[MethodStage] = Field(min_length=6, max_length=6)
    allergens: str = Field(default="Check current product labels.", max_length=400)
    nutrition: str = Field(default="Nutrition not supplied for this adapted version", max_length=400)
    nutrition_display: str = Field(default="Nutrition not supplied for this adapted version", max_length=400)
    nutrition_table: dict[str, Any] | None = None
    hero_image_subject: str = Field(default="", max_length=220)
    bloody_dave_quote: str = Field(default="", max_length=180)
    source_credit: str = Field(default="", max_length=160)
    nutrition_basis: str = Field(default="not_supplied_after_adaptation", max_length=80)
    requested_adaptations: list[str] = Field(default_factory=list)
    variant_of: str | None = None

    @field_validator("method")
    @classmethod
    def six_stages(cls, value: list[MethodStage]) -> list[MethodStage]:
        if len(value) != 6:
            raise ValueError("Exactly six method stages are required")
        return value

    def method_texts(self) -> list[str]:
        return [f"{stage.heading}. {stage.directions}".strip() for stage in self.method]


class SourceFacts(BaseModel):
    submitted_url: str
    resolved_url: str = ""
    publisher: str = ""
    title: str = ""
    serves: str = ""
    prep_time: str = ""
    cook_time: str = ""
    total_time: str = ""
    cuisine: str = ""
    category: str = ""
    ingredients: list[str] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    nutrition_text: str = ""
    allergens_text: str = ""
    image_url: str = ""
    extraction_method: str = "none"
    source_hash: str = ""
    fetched_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw_excerpt: str = ""


class CreateJobRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    instructions: str = Field(default="", max_length=4000)
    create_variant: bool = False
    pasted_source: str = Field(default="", max_length=100_000)


class PatchRecipeRequest(BaseModel):
    title: str | None = None
    subtitle: str | None = None
    hook: str | None = None
    serves: str | None = None
    prep_time: str | None = None
    cook_time: str | None = None
    total_time: str | None = None
    cuisine: str | None = None
    protein: str | None = None
    tags: list[str] | None = None
    buy: list[str] | None = None
    pantry: list[str] | None = None
    method: list[MethodStage] | None = None
    allergens: str | None = None
    nutrition: str | None = None
    nutrition_display: str | None = None
    bloody_dave_quote: str | None = None
    source_credit: str | None = None
    hero_image_subject: str | None = None


class QAResult(BaseModel):
    passed: bool
    checks: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    url: str = ""
    instructions: str = ""
    create_variant: bool = False
    candidate_id: str | None = None
    published_id: str | None = None
    commit_sha: str | None = None
    error: str | None = None
    progress: str = ""
    source: SourceFacts | None = None
    recipe: RecipeDraft | None = None
    qa: QAResult | None = None
    duplicate_of: str | None = None
    recipe_url: str | None = None
    card_url: str | None = None

    def touch(self, status: JobStatus | None = None, progress: str | None = None) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if status is not None:
            self.status = status
        if progress is not None:
            self.progress = progress


class NormalisedAIRecipe(BaseModel):
    """Strict schema the text model must return."""

    title: str
    subtitle: str = ""
    hook: str = ""
    source: str
    serves: str = "2"
    prep_time: str = ""
    cook_time: str = ""
    total_time: str = ""
    cuisine: str = "Modern Australian"
    protein: str = ""
    difficulty: str = "Easy"
    tags: list[str] = Field(default_factory=list)
    buy: list[str] = Field(default_factory=list)
    pantry: list[str] = Field(default_factory=list)
    method: list[MethodStage]
    allergens: str = "Check current product labels."
    nutrition: str = "Nutrition not supplied for this adapted version"
    nutrition_display: str = "Nutrition not supplied for this adapted version"
    retain_source_nutrition: bool = False
    hero_image_subject: str = ""
    bloody_dave_quote: str = ""
    source_credit: str = ""
    adaptation_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_six(self) -> "NormalisedAIRecipe":
        if len(self.method) != 6:
            raise ValueError("Model output must contain exactly 6 method stages")
        return self
