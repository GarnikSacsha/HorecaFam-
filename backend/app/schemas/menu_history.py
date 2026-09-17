from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.menu import FactDataStatus, MenuAvailability


class MenuHistoryComponent(BaseModel):
    name: str
    optional: bool | None


class MenuBusinessValues(BaseModel):
    name: str
    description: str | None
    price_minor: int | None
    currency: str
    availability: MenuAvailability
    component_data_status: FactDataStatus
    components: list[MenuHistoryComponent]
    allergen_data_status: FactDataStatus
    allergen_codes: list[str]


class MenuChangeEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    location_id: UUID
    menu_version_id: UUID
    menu_item_id: UUID
    actor_email: str
    action: Literal["created", "updated", "removed"]
    item_name: str
    old_values: MenuBusinessValues | None
    new_values: MenuBusinessValues | None
    created_at: datetime


class MenuChangeHistoryResponse(BaseModel):
    items: list[MenuChangeEventResponse]
    next_cursor: str | None
