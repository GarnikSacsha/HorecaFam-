from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

JobStatus = Literal["pending", "processing", "completed", "failed"]
JobType = Literal[
    "invitation_email",
    "training_assignment_notification",
    "training_rollout_notification",
    "password_reset_email",
    "attempt_expiry",
    "retake_deadline_projection",
    "security_record_cleanup",
    "audit_retention",
]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuditEventResponse(StrictSchema):
    id: UUID
    organization_id: UUID | None
    actor_user_id: UUID | None
    actor_type: Literal["user", "system", "worker", "cron"]
    action: str
    target_type: str
    target_id: UUID | None
    old_values: dict[str, Any] | None
    new_values: dict[str, Any] | None
    request_id: UUID | None
    outcome: Literal["success", "failed"]
    error_code: str | None
    created_at: datetime


class AuditEventListResponse(StrictSchema):
    items: list[AuditEventResponse]
    next_cursor: str | None


class OperatorJobSummary(StrictSchema):
    id: UUID
    organization_id: UUID | None
    job_type: JobType
    status: JobStatus
    priority: int
    attempt_count: int
    max_attempts: int
    next_run_at: datetime
    last_error_code: str | None
    last_error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    failed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class OperatorJobListResponse(StrictSchema):
    items: list[OperatorJobSummary]
    next_cursor: str | None


class OperatorJobAttemptResponse(StrictSchema):
    id: UUID
    attempt_number: int
    started_at: datetime
    heartbeat_last_seen_at: datetime | None
    finished_at: datetime | None
    outcome: Literal["processing", "completed", "retry_scheduled", "failed", "interrupted"]
    error_code: str | None
    error_message: str | None
    next_retry_at: datetime | None


class OperatorEmailDeliveryResponse(StrictSchema):
    status: Literal["pending", "accepted", "delivered", "bounced", "failed"]
    provider: str
    accepted_by_provider_at: datetime | None
    delivered_at: datetime | None
    bounced_at: datetime | None
    failed_at: datetime | None
    error_code: str | None


class OperatorJobDetail(OperatorJobSummary):
    request_id: UUID | None
    locked_at: datetime | None
    heartbeat_at: datetime | None
    attempts: list[OperatorJobAttemptResponse]
    delivery: OperatorEmailDeliveryResponse | None


class OperatorJobRetryRequest(StrictSchema):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason", mode="before")
    @classmethod
    def normalize_reason(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Reason must not be blank")
        return normalized


class OperatorJobRetryResponse(StrictSchema):
    source_job_id: UUID
    job: OperatorJobSummary
    replayed: bool
