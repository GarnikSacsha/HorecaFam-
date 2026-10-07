from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.schemas.assessment import PracticeAttemptOptionResponse, StrictAssessmentSchema


class CourseReview(StrictAssessmentSchema):
    is_correct: bool
    correct_option_ids: list[UUID]
    explanation_payload: dict[str, object]


class CourseQuestion(StrictAssessmentSchema):
    id: UUID
    position: int = Field(ge=0, le=19)
    mechanic: str
    prompt_payload: dict[str, object]
    options: list[PracticeAttemptOptionResponse]
    answer_payload: dict[str, object] | None
    review: CourseReview | None


class CourseResult(StrictAssessmentSchema):
    id: UUID
    correct_count: int = Field(ge=0, le=20)
    total_count: int = Field(ge=1, le=20)
    score_basis_points: int = Field(ge=0, le=10000)
    knowledge_level: Literal["very_weak", "weak", "good", "strong"]
    pass_status: None = None
    completed_at: datetime


class CourseAttemptResponse(StrictAssessmentSchema):
    id: UUID
    assessment_version_id: UUID
    assignment_id: UUID
    status: Literal["in_progress", "completed", "expired", "invalidated"]
    presentation_locale: Literal["uk", "en"]
    lease_generation: int = Field(ge=1)
    writable: bool
    expires_at: datetime
    questions: list[CourseQuestion]
    result: CourseResult | None


class CourseHistoryItem(StrictAssessmentSchema):
    attempt_id: UUID
    result: CourseResult


class CourseModuleSummary(StrictAssessmentSchema):
    module_version_id: UUID
    question_count: int = Field(ge=1, le=20)
    can_start: bool
    ready: bool
    active_attempt_id: UUID | None
    history: list[CourseHistoryItem]
