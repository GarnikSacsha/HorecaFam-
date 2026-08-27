from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr


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
