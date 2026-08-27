from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr

from app.schemas.auth import SessionResponse


class InvitationCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class InvitationValidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr


class InvitationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    email: EmailStr
    status: Literal["pending", "expired", "revoked", "accepted"]
    expires_at: datetime
    created_at: datetime
    updated_at: datetime


class InvitationValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["valid"] = "valid"
    organization_id: UUID
    organization_name: str
    email_masked: str
    acceptance_mode: Literal["activate_access", "accept_existing_account"]
    expires_at: datetime


class InvitationActivateAccessRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr
    acceptance_mode: Literal["activate_access"]
    password: SecretStr = Field(min_length=8, max_length=128)


class InvitationAcceptExistingAccountRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr
    acceptance_mode: Literal["accept_existing_account"]
    password: SecretStr = Field(min_length=1, max_length=128)


InvitationAcceptanceRequest = Annotated[
    InvitationActivateAccessRequest | InvitationAcceptExistingAccountRequest,
    Field(discriminator="acceptance_mode"),
]


class PendingMembershipResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    employee_profile_id: UUID
    status: Literal["pending"] = "pending"


class InvitationAcceptanceResponse(SessionResponse):
    status: Literal["accepted"] = "accepted"
    acceptance_mode: Literal["activate_access", "accept_existing_account"]
    membership: PendingMembershipResponse
