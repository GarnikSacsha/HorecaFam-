from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictAssessmentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class GenerationScope(StrictAssessmentSchema):
    organization_id: UUID
    location_id: UUID
    menu_version_id: UUID
    training_version_id: UUID
    lesson_version_id: UUID


class CategoryGenerationRule(StrictAssessmentSchema):
    code: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanic: Literal["single_choice"] = "single_choice"


class CategoryFact(StrictAssessmentSchema):
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    menu_version_category_id: UUID
    category_name: str
    price_minor: int | None = Field(default=None, ge=0)
    verified: bool


class CandidateOption(StrictAssessmentSchema):
    stable_key: str = Field(min_length=1, max_length=100)
    text: str = Field(min_length=1, max_length=200)


class CandidatePromptPayload(StrictAssessmentSchema):
    locale: Literal["uk"] = "uk"
    stem: str = Field(min_length=1, max_length=500)
    options: list[CandidateOption] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def options_are_unambiguous(self) -> "CandidatePromptPayload":
        keys = [option.stable_key for option in self.options]
        labels = [option.text.casefold() for option in self.options]
        if len(keys) != len(set(keys)) or len(labels) != len(set(labels)):
            raise ValueError("Candidate options must be unique and unambiguous")
        return self


class CandidateAnswerPayload(StrictAssessmentSchema):
    correct_option_keys: list[str] = Field(min_length=1, max_length=20)


class CandidateExplanationPayload(StrictAssessmentSchema):
    locale: Literal["uk"] = "uk"
    text: str = Field(min_length=1, max_length=1000)


class CandidateSource(StrictAssessmentSchema):
    source_role: Literal["correct_fact", "distractor_basis", "explanation_source"]
    menu_item_version_id: UUID


class GeneratedCandidate(StrictAssessmentSchema):
    mechanic: Literal["single_choice"]
    prompt_payload: CandidatePromptPayload
    answer_payload: CandidateAnswerPayload
    explanation_payload: CandidateExplanationPayload
    source_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    sources: list[CandidateSource] = Field(min_length=2)


class QuestionCandidateGenerateRequest(StrictAssessmentSchema):
    menu_version_id: UUID
    training_version_id: UUID


class QuestionCandidateGenerateResponse(StrictAssessmentSchema):
    created_count: int = Field(ge=0)
    existing_count: int = Field(ge=0)
    stale_candidate_count: int = Field(ge=0)
    stale_question_count: int = Field(ge=0)
    replayed: bool = False


class CandidateEditedPayload(StrictAssessmentSchema):
    prompt_payload: CandidatePromptPayload
    answer_payload: CandidateAnswerPayload
    explanation_payload: CandidateExplanationPayload


class QuestionCandidateApproveRequest(StrictAssessmentSchema):
    expected_revision: int = Field(ge=0)
    edited_payload: CandidateEditedPayload | None = None


class QuestionCandidateRejectRequest(StrictAssessmentSchema):
    expected_revision: int = Field(ge=0)
    reason_code: str = Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_]+$")


class QuestionCandidateBatchItem(StrictAssessmentSchema):
    candidate_id: UUID
    expected_revision: int = Field(ge=0)


class QuestionCandidateBatchApproveRequest(StrictAssessmentSchema):
    items: list[QuestionCandidateBatchItem] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def candidate_ids_are_unique(self) -> "QuestionCandidateBatchApproveRequest":
        ids = [item.candidate_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Candidate IDs must be unique")
        return self


class CandidateSourceResponse(StrictAssessmentSchema):
    source_role: str
    menu_item_version_id: UUID | None
    menu_item_version_component_id: UUID | None
    menu_item_version_allergen_id: UUID | None


class QuestionCandidateResponse(StrictAssessmentSchema):
    id: UUID
    training_version_id: UUID
    lesson_version_id: UUID
    mechanic: str
    prompt_payload: dict[str, object]
    answer_payload: dict[str, object]
    explanation_payload: dict[str, object]
    source_fingerprint: str
    status: str
    revision: int
    reviewed_at: datetime | None
    rejection_reason_code: str | None
    sources: list[CandidateSourceResponse]


class QuestionCandidateCollection(StrictAssessmentSchema):
    items: list[QuestionCandidateResponse]
    total: int = Field(ge=0)


class LessonAssessmentReadinessResponse(StrictAssessmentSchema):
    assessment_version_id: UUID
    lesson_id: UUID
    lesson_version_id: UUID
    status: Literal["processing", "ready", "warning", "blocked"]
    eligible_count: int = Field(ge=0)
    required_count: Literal[5] = 5
    coverage_evidence: dict[str, object]
    rotation_supported: bool
    basis_fingerprint: str
    blocking_codes: list[str]
    warning_codes: list[str]
    computed_at: datetime
    can_start: bool


class InteractiveTrainingReadinessResponse(StrictAssessmentSchema):
    training_version_id: UUID
    lessons: list[LessonAssessmentReadinessResponse]


class QuestionCandidateApprovalResponse(StrictAssessmentSchema):
    candidate: QuestionCandidateResponse
    question_version_id: UUID
    readiness: LessonAssessmentReadinessResponse


class QuestionCandidateBatchApprovalResponse(StrictAssessmentSchema):
    items: list[QuestionCandidateApprovalResponse]
