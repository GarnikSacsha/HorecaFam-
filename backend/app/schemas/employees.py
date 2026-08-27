from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

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


class EmployeeListResponse(StrictSchema):
    items: list[EmployeeSummary]
    next_cursor: str | None


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
