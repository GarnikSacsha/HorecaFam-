from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AcademyWrite(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    slug: str = Field(min_length=1, max_length=120, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    title_uk: str = Field(min_length=1, max_length=200)
    summary_uk: str = Field(min_length=1, max_length=500)
    body_uk: str = Field(min_length=1, max_length=50000)
    category: str = Field(min_length=1, max_length=64, pattern=r"^[a-z0-9_]+$")
    status: Literal["draft", "published"] = "draft"
    position: int = Field(default=0, ge=0, le=100000)
    all_positions: bool = False
    operational_role_ids: list[UUID] = Field(default_factory=list, max_length=100)
    cover_asset_id: UUID | None = None

    @model_validator(mode="after")
    def valid_audience(self) -> Self:
        if self.all_positions == bool(self.operational_role_ids):
            raise ValueError("Choose either all positions or specific positions")
        if len(set(self.operational_role_ids)) != len(self.operational_role_ids):
            raise ValueError("Position IDs must be unique")
        return self


class AcademyUpdate(AcademyWrite):
    expected_revision: int = Field(ge=0)


class AcademyArticleResponse(AcademyWrite):
    id: UUID
    revision: int
    created_at: datetime
    updated_at: datetime


class AcademyCollection(BaseModel):
    items: list[AcademyArticleResponse]
    next_offset: int | None


class AcademySeedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    waiter_role_id: UUID
    runner_role_id: UUID
    bartender_role_id: UUID

    @model_validator(mode="after")
    def distinct_positions(self) -> Self:
        if len({self.waiter_role_id, self.runner_role_id, self.bartender_role_id}) != 3:
            raise ValueError("Choose three distinct positions")
        return self
