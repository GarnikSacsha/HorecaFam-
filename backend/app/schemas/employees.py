from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LifecycleStatus = Literal["active", "archived"]
MembershipStatus = Literal["pending", "active", "disabled"]
Locale = Literal["uk", "en"]


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrganizationSummary(StrictSchema):
    id: UUID
    name: str
    status: LifecycleStatus
    default_locale: Locale
    timezone: str


class OrganizationReference(StrictSchema):
    id: UUID
    name: str


class LocationSummary(StrictSchema):
    id: UUID
    organization_id: UUID
    name: str
    status: LifecycleStatus
    address: str | None
    timezone: str


class OperationalRoleSummary(StrictSchema):
    id: UUID
    organization_id: UUID
    code: str
    name_uk: str
    status: LifecycleStatus


class EmployeeSummary(StrictSchema):
    id: UUID
    organization_id: UUID
    email: str
    first_name: str | None
    last_name: str | None
    membership_status: MembershipStatus
    operational_role: OperationalRoleSummary | None
    location: LocationSummary | None
    profile_complete: bool
    created_at: datetime
    updated_at: datetime


class EmployeeDetail(EmployeeSummary):
    membership_created_at: datetime
    activated_at: datetime | None
    disabled_at: datetime | None
    training_participation_status: Literal["active", "paused"]
    training_paused_at: datetime | None
    training_pause_reason_code: str | None
    training_pause_note: str | None
    planned_resume_at: datetime | None
    disabled_reason_code: str | None
    disabled_note: str | None


class EmployeeLifecycleActionResponse(StrictSchema):
    employee_id: UUID
    organization_id: UUID
    membership_status: Literal["active"]
    training_participation_status: Literal["active"]
    activated_at: datetime


class EmployeeLifecycleStateResponse(StrictSchema):
    employee_id: UUID
    organization_id: UUID
    membership_status: MembershipStatus
    training_participation_status: Literal["active", "paused"]
    activated_at: datetime | None
    disabled_at: datetime | None
    training_paused_at: datetime | None
    training_pause_reason_code: str | None
    training_pause_note: str | None
    planned_resume_at: datetime | None
    disabled_reason_code: str | None
    disabled_note: str | None


class EmployeeLifecycleReason(StrictSchema):
    reason_code: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=r"^[a-z][a-z0-9_]*$",
    )
    note: str | None = Field(default=None, min_length=1, max_length=500)

    @field_validator("note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Note must not be blank")
        return normalized


class EmployeeDisableRequest(EmployeeLifecycleReason):
    pass


class EmployeePauseRequest(EmployeeLifecycleReason):
    planned_resume_at: datetime | None = None


class EmployeeListResponse(StrictSchema):
    items: list[EmployeeSummary]
    next_cursor: str | None


class EmployeeUpdate(StrictSchema):
    first_name: str | None = Field(default=None, max_length=120)
    last_name: str | None = Field(default=None, max_length=120)
    operational_role_id: UUID | None = None
    location_id: UUID | None = None

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name must not be blank")
        return normalized

    @model_validator(mode="after")
    def require_supplied_field(self) -> "EmployeeUpdate":
        if not self.model_fields_set:
            raise ValueError("At least one field must be supplied")
        return self


class OwnEmployeeProfile(StrictSchema):
    id: UUID
    organization: OrganizationReference
    membership_status: MembershipStatus
    first_name: str | None
    last_name: str | None
    operational_role: OperationalRoleSummary | None
    location: LocationSummary | None
    profile_complete: bool
    updated_at: datetime


class OwnEmployeeProfilesResponse(StrictSchema):
    profiles: list[OwnEmployeeProfile]
