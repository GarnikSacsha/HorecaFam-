from datetime import datetime
from typing import Annotated, Literal
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


class ComponentGenerationRule(StrictAssessmentSchema):
    code: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanic: Literal["multiple_choice"] = "multiple_choice"


class AllergenGenerationRule(StrictAssessmentSchema):
    code: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanic: Literal["recognition"] = "recognition"


class DescriptionGenerationRule(StrictAssessmentSchema):
    code: str = Field(min_length=1, max_length=100)
    version: int = Field(ge=1)
    mechanic: Literal["recognition"] = "recognition"


class CategoryFact(StrictAssessmentSchema):
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    menu_version_category_id: UUID
    category_name: str
    price_minor: int | None = Field(default=None, ge=0)
    verified: bool


class ComponentFact(StrictAssessmentSchema):
    menu_item_version_component_id: UUID
    menu_component_version_id: UUID
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    component_name: str
    position: int = Field(ge=0)
    verified: bool


class AllergenFact(StrictAssessmentSchema):
    menu_item_version_allergen_id: UUID
    allergen_id: UUID
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    allergen_name: str
    verified: bool


class DescriptionFact(StrictAssessmentSchema):
    menu_item_version_id: UUID
    menu_item_id: UUID
    item_name: str
    description: str
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
    menu_item_version_id: UUID | None = None
    menu_item_version_component_id: UUID | None = None
    menu_item_version_allergen_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one_source(self) -> "CandidateSource":
        values = (
            self.menu_item_version_id,
            self.menu_item_version_component_id,
            self.menu_item_version_allergen_id,
        )
        if sum(value is not None for value in values) != 1:
            raise ValueError("Candidate source must identify exactly one verified fact")
        return self


class GeneratedCandidate(StrictAssessmentSchema):
    mechanic: Literal["single_choice", "multiple_choice", "recognition"]
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


class PracticeReadinessResponse(StrictAssessmentSchema):
    training_version_id: UUID
    assessment_version_id: UUID | None
    status: Literal["processing", "ready", "warning", "blocked"]
    eligible_count: int = Field(ge=0)
    required_count: Literal[10] = 10
    coverage_evidence: dict[str, object]
    rotation_supported: bool
    rotation_target_count: Literal[20] = 20
    basis_fingerprint: str | None
    blocking_codes: list[str]
    warning_codes: list[str]
    computed_at: datetime | None
    can_start: bool


class QuestionCandidateApprovalResponse(StrictAssessmentSchema):
    candidate: QuestionCandidateResponse
    question_version_id: UUID
    readiness: LessonAssessmentReadinessResponse


class QuestionCandidateBatchApprovalResponse(StrictAssessmentSchema):
    items: list[QuestionCandidateApprovalResponse]


class InteractiveAttemptOptionResponse(StrictAssessmentSchema):
    id: UUID
    position: int = Field(ge=0)
    payload: dict[str, object]


class SingleChoiceSubmission(StrictAssessmentSchema):
    mechanic: Literal["single_choice"]
    option_id: UUID


class MultipleChoiceSubmission(StrictAssessmentSchema):
    mechanic: Literal["multiple_choice", "recognition"]
    option_ids: list[UUID] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def options_are_unique(self) -> "MultipleChoiceSubmission":
        if len(self.option_ids) != len(set(self.option_ids)):
            raise ValueError("Option IDs must be unique")
        return self


class OrderingSubmission(StrictAssessmentSchema):
    mechanic: Literal["ordering", "assembly"]
    option_ids: list[UUID] = Field(min_length=2, max_length=20)

    @model_validator(mode="after")
    def options_are_unique(self) -> "OrderingSubmission":
        if len(self.option_ids) != len(set(self.option_ids)):
            raise ValueError("Option IDs must be unique")
        return self


class MatchingPairSubmission(StrictAssessmentSchema):
    left_option_id: UUID
    right_option_id: UUID


class MatchingSubmission(StrictAssessmentSchema):
    mechanic: Literal["matching"]
    pairs: list[MatchingPairSubmission] = Field(min_length=1, max_length=20)


InteractiveAnswerPayload = Annotated[
    SingleChoiceSubmission | MultipleChoiceSubmission | OrderingSubmission | MatchingSubmission,
    Field(discriminator="mechanic"),
]


class InteractiveConfirmedAnswerResponse(StrictAssessmentSchema):
    id: UUID
    answer_payload: dict[str, object]
    is_correct: bool
    submitted_at: datetime


class InteractiveFeedbackResponse(StrictAssessmentSchema):
    is_correct: bool
    correct_option_ids: list[UUID]
    explanation_payload: dict[str, object]


class InteractiveAttemptQuestionResponse(StrictAssessmentSchema):
    id: UUID
    position: int = Field(ge=0, le=4)
    mechanic: str
    prompt_payload: dict[str, object]
    options: list[InteractiveAttemptOptionResponse]
    answered: bool = False
    confirmed_answer: InteractiveConfirmedAnswerResponse | None = None
    feedback: InteractiveFeedbackResponse | None = None


class InteractiveAttemptResponse(StrictAssessmentSchema):
    id: UUID
    lesson_id: UUID
    lesson_version_id: UUID
    assessment_version_id: UUID
    status: str
    presentation_locale: Literal["uk", "en"]
    started_at: datetime
    expires_at: datetime
    lease_generation: int = Field(ge=1)
    writable: bool
    questions: list[InteractiveAttemptQuestionResponse]


class InteractiveAttemptStartResponse(StrictAssessmentSchema):
    attempt: InteractiveAttemptResponse
    created: bool
    replayed: bool


class InteractiveAttemptTakeoverResponse(StrictAssessmentSchema):
    attempt_id: UUID
    lease_generation: int = Field(ge=1)
    replayed: bool


class PracticeAttemptOptionResponse(StrictAssessmentSchema):
    id: UUID
    position: int = Field(ge=0)
    payload: dict[str, object]


class PracticeSavedAnswerResponse(StrictAssessmentSchema):
    id: UUID
    answer_payload: dict[str, object]
    submitted_at: datetime


class PracticeAttemptQuestionResponse(StrictAssessmentSchema):
    id: UUID
    position: int = Field(ge=0, le=9)
    mechanic: str
    prompt_payload: dict[str, object]
    coverage_key: str
    options: list[PracticeAttemptOptionResponse]
    saved_answer: PracticeSavedAnswerResponse | None = None


class PracticeAttemptResponse(StrictAssessmentSchema):
    id: UUID
    assignment_id: UUID
    assessment_version_id: UUID
    status: Literal["in_progress", "completed", "expired", "invalidated"]
    presentation_locale: Literal["uk", "en"]
    started_at: datetime
    last_activity_at: datetime
    expires_at: datetime
    lease_generation: int = Field(ge=1)
    writable: bool
    answered_count: int = Field(ge=0, le=10)
    questions: list[PracticeAttemptQuestionResponse]


class PracticeAttemptStartResponse(StrictAssessmentSchema):
    attempt: PracticeAttemptResponse
    created: bool
    replayed: bool


class PracticeAttemptTakeoverResponse(StrictAssessmentSchema):
    attempt_id: UUID
    lease_generation: int = Field(ge=1)
    replayed: bool


class PracticeResultSummaryResponse(StrictAssessmentSchema):
    result_id: UUID
    attempt_id: UUID
    assessment_version_id: UUID
    completed_at: datetime
    correct_count: int = Field(ge=0, le=10)
    total_count: Literal[10] = 10
    score_basis_points: int = Field(ge=0, le=10000)
    knowledge_level: Literal["very_weak", "weak", "good", "strong"]
    critical_error_count: int = Field(ge=0, le=10)


class PracticeHistoryResponse(StrictAssessmentSchema):
    qualified: bool
    latest: PracticeResultSummaryResponse | None
    best: PracticeResultSummaryResponse | None
    history: list[PracticeResultSummaryResponse]


class PracticeSummaryResponse(StrictAssessmentSchema):
    availability: Literal["ready", "preparing", "unavailable", "paused"]
    can_start: bool
    reason_codes: list[str]
    readiness_status: Literal["processing", "ready", "warning", "blocked"] | None
    active_attempt: PracticeAttemptResponse | None
    qualified: bool
    latest: PracticeResultSummaryResponse | None
    best: PracticeResultSummaryResponse | None


class PracticeAnswerRequest(StrictAssessmentSchema):
    attempt_question_id: UUID
    answer_payload: InteractiveAnswerPayload
    lease_generation: int = Field(ge=1)


class PracticeAnswerResponse(StrictAssessmentSchema):
    answer: PracticeSavedAnswerResponse
    answered_count: int = Field(ge=0, le=10)
    next_question_id: UUID | None
    attempt_status: Literal["in_progress"] = "in_progress"
    replayed: bool


class PracticeFinishRequest(StrictAssessmentSchema):
    lease_generation: int = Field(ge=1)


class PracticeResultResponse(StrictAssessmentSchema):
    id: UUID
    correct_count: int = Field(ge=0, le=10)
    total_count: Literal[10] = 10
    score_basis_points: int = Field(ge=0, le=10000)
    knowledge_level: Literal["very_weak", "weak", "good", "strong"]
    pass_status: None = None
    critical_error_count: int = Field(ge=0, le=10)
    completed_at: datetime


class PracticeQuestionReviewResponse(StrictAssessmentSchema):
    attempt_question_id: UUID
    position: int = Field(ge=0, le=9)
    mechanic: str
    prompt_payload: dict[str, object]
    options: list[PracticeAttemptOptionResponse]
    answer: PracticeSavedAnswerResponse
    is_correct: bool
    correct_option_ids: list[UUID]
    explanation_payload: dict[str, object]
    is_critical: bool
    is_critical_error: bool


class PracticeFinishResponse(StrictAssessmentSchema):
    result: PracticeResultResponse
    qualified: bool
    eligibility_earned: bool
    review: list[PracticeQuestionReviewResponse]
    replayed: bool


class InteractiveAnswerRequest(StrictAssessmentSchema):
    attempt_question_id: UUID
    answer_payload: InteractiveAnswerPayload
    lease_generation: int = Field(ge=1)


class InteractiveResultResponse(StrictAssessmentSchema):
    id: UUID
    correct_count: int = Field(ge=0, le=5)
    total_count: Literal[5] = 5
    score_basis_points: int = Field(ge=0, le=10000)
    knowledge_level: Literal["very_weak", "weak", "good", "strong"]
    pass_status: None = None
    completed_at: datetime


class InteractiveAnswerResponse(StrictAssessmentSchema):
    answer: InteractiveConfirmedAnswerResponse
    feedback: InteractiveFeedbackResponse
    next_question_id: UUID | None
    attempt_status: Literal["in_progress", "completed"]
    result: InteractiveResultResponse | None
    replayed: bool


class InteractiveResultSummaryResponse(StrictAssessmentSchema):
    result_id: UUID
    attempt_id: UUID
    assessment_version_id: UUID
    completed_at: datetime
    correct_count: int = Field(ge=0, le=5)
    total_count: Literal[5] = 5
    score_basis_points: int = Field(ge=0, le=10000)
    knowledge_level: Literal["very_weak", "weak", "good", "strong"]
    is_current: bool


class LessonInteractiveTrainingSummaryResponse(StrictAssessmentSchema):
    lesson_id: UUID
    lesson_version_id: UUID
    assessment_version_id: UUID | None
    availability: Literal["ready", "preparing", "unavailable", "paused"]
    can_start: bool
    reason_codes: list[str]
    readiness_status: Literal["processing", "ready", "warning", "blocked"] | None
    active_attempt: InteractiveAttemptResponse | None
    latest: InteractiveResultSummaryResponse | None
    best: InteractiveResultSummaryResponse | None
    history: list[InteractiveResultSummaryResponse]
