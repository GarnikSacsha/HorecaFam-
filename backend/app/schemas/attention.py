from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

RetakeReason = Literal[
    "failed_exam",
    "critical_error",
    "management_follow_up",
    "material_content_change",
]
RetakeState = Literal["proposed", "active", "completed", "cancelled"]
RetakeTimingState = Literal["scheduled", "approaching", "overdue", "frozen"]
AttentionType = Literal["critical_allergen", "retake_overdue"]
AttentionState = Literal["open", "acknowledged", "resolved"]


class StrictFollowUpSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class RetakeRequirementResponse(StrictFollowUpSchema):
    id: UUID
    organization_id: UUID
    location_id: UUID
    training_id: UUID
    employee_profile_id: UUID
    assignment_id: UUID
    target_assessment_id: UUID | None = None
    reason: RetakeReason
    state: RetakeState
    timing_state: RetakeTimingState | None
    source_result_id: UUID | None
    source_attempt_id: UUID | None
    source_attention_case_id: UUID | None
    management_source_key: str | None
    target_policy: dict[str, object]
    proposed_at: datetime | None
    confirmed_at: datetime | None
    due_at: datetime
    clock_frozen_at: datetime | None
    completed_at: datetime | None
    completion_attempt_id: UUID | None
    cancelled_at: datetime | None
    cancellation_comment: str | None
    revision: int


class RetakeRequirementCollection(StrictFollowUpSchema):
    items: list[RetakeRequirementResponse]
    next_cursor: str | None


class AttentionCaseResponse(StrictFollowUpSchema):
    id: UUID
    organization_id: UUID
    location_id: UUID
    training_id: UUID
    employee_profile_id: UUID
    case_type: AttentionType
    severity: Literal["critical", "overdue"]
    subject_key: str | None
    state: AttentionState
    revision: int
    acknowledged_at: datetime | None
    resolution_type: (
        Literal[
            "clean_retake",
            "admin_follow_up",
            "requirement_completed",
            "requirement_cancelled",
        ]
        | None
    )
    resolved_at: datetime | None
    resolution_comment: str | None
    critical_error_ids: list[UUID]
    retake_requirement_id: UUID | None
    created_at: datetime
    updated_at: datetime


class AttentionCaseCollection(StrictFollowUpSchema):
    items: list[AttentionCaseResponse]
    next_cursor: str | None


class EmployeeRetakeRequirementResponse(StrictFollowUpSchema):
    id: UUID
    training_id: UUID
    target_assessment_id: UUID
    reason: RetakeReason
    state: Literal["active", "completed", "cancelled"]
    timing_state: RetakeTimingState | None
    due_at: datetime
    permitted_action: Literal["start_retake", "resume_retake", "review_history", "wait"]
    source_attempt_id: UUID | None
    completion_attempt_id: UUID | None
    completed_at: datetime | None
    cancelled_at: datetime | None


class EmployeeRetakeRequirementCollection(StrictFollowUpSchema):
    items: list[EmployeeRetakeRequirementResponse]
    next_cursor: str | None


class EmployeeAttentionSummary(StrictFollowUpSchema):
    open_count: int = Field(ge=0)
    has_critical_follow_up: bool
    has_overdue_follow_up: bool


class RetakeRequirementCreateRequest(StrictFollowUpSchema):
    reason: Literal["critical_error", "management_follow_up"]
    target_assessment_id: UUID | None = None
    source_attention_case_id: UUID | None = None
    management_source_key: str | None = Field(default=None, min_length=1, max_length=200)
    target_policy: dict[str, object]
    due_at: datetime | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "RetakeRequirementCreateRequest":
        if self.reason == "critical_error":
            if self.source_attention_case_id is None or self.management_source_key is not None:
                raise ValueError("Critical Requirement must name one Attention source")
        elif self.management_source_key is None or self.source_attention_case_id is not None:
            raise ValueError("Management Requirement must name one management source key")
        return self


class RetakeRequirementUpdateRequest(StrictFollowUpSchema):
    due_at: datetime
    expected_revision: int = Field(ge=0)


class RetakeRequirementConfirmRequest(StrictFollowUpSchema):
    expected_revision: int = Field(ge=0)


class RetakeRequirementCancelRequest(StrictFollowUpSchema):
    expected_revision: int = Field(ge=0)
    comment: str = Field(min_length=1, max_length=500)


class AttentionAcknowledgeRequest(StrictFollowUpSchema):
    expected_revision: int = Field(ge=0)


class AttentionResolveRequest(StrictFollowUpSchema):
    expected_revision: int = Field(ge=0)
    resolution_type: Literal["clean_retake", "admin_follow_up"]
    comment: str | None = Field(default=None, max_length=500)
    evidence_attempt_id: UUID | None = None
