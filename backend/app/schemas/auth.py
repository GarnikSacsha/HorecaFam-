from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr


class PasswordForgotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr


class PasswordForgotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["accepted"] = "accepted"


class PasswordResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: SecretStr = Field(min_length=32, max_length=256)
    new_password: SecretStr = Field(min_length=8, max_length=128)


class PasswordChangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_password: SecretStr = Field(min_length=1, max_length=128)
    new_password: SecretStr = Field(min_length=8, max_length=128)


class SessionUser(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    preferred_locale: Literal["uk", "en"]


class SessionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    absolute_expires_at: datetime
    mfa_verified: bool


class OrganizationAccess(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: UUID
    membership_status: Literal["pending", "active", "disabled"] | None
    is_employee: bool
    is_organization_admin: bool


class SessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user: SessionUser
    session: SessionInfo
    organization_access: list[OrganizationAccess]
    platform_operator: bool
    csrf_token: str


class MfaRequiredResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["mfa_required"] = "mfa_required"
    expires_at: datetime


class MfaVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(pattern=r"^\d{6}$")
