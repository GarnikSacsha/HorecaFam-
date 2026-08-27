from datetime import datetime
from typing import Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MenuAvailability = Literal[
    "available",
    "temporarily_unavailable",
    "seasonal",
    "discontinued",
]
FactDataStatus = Literal["unknown", "confirmed_none", "confirmed_present"]
MenuSourceKind = Literal["manual", "json_import"]
MenuVersionStatus = Literal["draft", "published", "archived"]
MenuDeltaKind = Literal["added", "changed", "removed", "unchanged"]
TrainingImpact = Literal["none", "review", "required"]


class StrictMenuSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _normalize_bounded_text(value: str, *, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError("Text must be non-blank and within the accepted bound")
    return normalized


class MenuComponentInput(StrictMenuSchema):
    id: UUID | None = None
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str = Field(min_length=1, max_length=200)
    optional: bool | None = None
    position: int = Field(ge=0)

    @field_validator("stable_code")
    @classmethod
    def normalize_stable_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)


class MenuItemWrite(StrictMenuSchema):
    category_id: UUID
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str = Field(min_length=1, max_length=200)
    description_uk: str | None = Field(default=None, max_length=4000)
    price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="UAH", pattern=r"^[A-Z]{3}$")
    availability: MenuAvailability = "available"
    position: int = Field(ge=0)
    component_data_status: FactDataStatus
    components: list[MenuComponentInput]
    allergen_data_status: FactDataStatus
    allergen_codes: list[str]
    source_kind: MenuSourceKind = "manual"
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    source_item_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_stable_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("description_uk")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("source_reference", "source_item_key")
    @classmethod
    def normalize_source_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("allergen_codes")
    @classmethod
    def normalize_allergen_codes(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            code = _normalize_bounded_text(value, maximum=64).lower()
            normalized.append(code)
        return normalized

    @model_validator(mode="after")
    def validate_fact_completeness(self) -> Self:
        if self.component_data_status == "confirmed_present" and not self.components:
            raise ValueError("confirmed_present components require at least one verified fact")
        if self.component_data_status != "confirmed_present" and self.components:
            raise ValueError("unknown or confirmed_none components require an empty fact list")
        if self.allergen_data_status == "confirmed_present" and not self.allergen_codes:
            raise ValueError("confirmed_present allergens require at least one controlled code")
        if self.allergen_data_status != "confirmed_present" and self.allergen_codes:
            raise ValueError("unknown or confirmed_none allergens require an empty fact list")

        component_ids = [component.id for component in self.components if component.id is not None]
        if len(component_ids) != len(set(component_ids)):
            raise ValueError("Component identities must be unique")
        stable_codes = [
            component.stable_code
            for component in self.components
            if component.stable_code is not None
        ]
        if len(stable_codes) != len(set(stable_codes)):
            raise ValueError("Component stable codes must be unique")
        if len(self.allergen_codes) != len(set(self.allergen_codes)):
            raise ValueError("Allergen codes must be unique")
        if [component.position for component in self.components] != list(
            range(len(self.components))
        ):
            raise ValueError("Component positions must be a complete zero-based sequence")
        return self


class MenuItemPatch(StrictMenuSchema):
    expected_revision: int = Field(ge=0)
    category_id: UUID | None = None
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str | None = Field(default=None, min_length=1, max_length=200)
    description_uk: str | None = Field(default=None, max_length=4000)
    price_minor: int | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    availability: MenuAvailability | None = None
    position: int | None = Field(default=None, ge=0)
    component_data_status: FactDataStatus | None = None
    components: list[MenuComponentInput] | None = None
    allergen_data_status: FactDataStatus | None = None
    allergen_codes: list[str] | None = None
    source_kind: MenuSourceKind | None = None
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    source_item_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_stable_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("description_uk")
    @classmethod
    def normalize_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("source_reference", "source_item_key")
    @classmethod
    def normalize_source_value(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("allergen_codes")
    @classmethod
    def normalize_allergen_codes(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        return [_normalize_bounded_text(value, maximum=64).lower() for value in values]

    @model_validator(mode="after")
    def require_mutable_field(self) -> Self:
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("At least one mutable field must be supplied")
        if self.components is not None:
            ids = [component.id for component in self.components if component.id is not None]
            codes = [
                component.stable_code
                for component in self.components
                if component.stable_code is not None
            ]
            if len(ids) != len(set(ids)) or len(codes) != len(set(codes)):
                raise ValueError("Components must be unique")
            if [component.position for component in self.components] != list(
                range(len(self.components))
            ):
                raise ValueError("Component positions must be a complete zero-based sequence")
        if self.allergen_codes is not None and len(self.allergen_codes) != len(
            set(self.allergen_codes)
        ):
            raise ValueError("Allergen codes must be unique")
        return self


class MenuVersionCreate(StrictMenuSchema):
    copy_from_version_id: UUID | None = None


class MenuVersionSummary(StrictMenuSchema):
    id: UUID
    menu_id: UUID
    organization_id: UUID
    location_id: UUID
    version_number: int = Field(ge=1)
    status: MenuVersionStatus
    base_version_id: UUID | None
    revision: int = Field(ge=0)
    section_count: int = Field(ge=0)
    category_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    created_at: datetime
    published_at: datetime | None
    archived_at: datetime | None


class MenuCategoryResponse(StrictMenuSchema):
    id: UUID
    section_id: UUID
    stable_code: str | None
    name_uk: str
    position: int = Field(ge=0)
    item_count: int = Field(ge=0)


class MenuSectionResponse(StrictMenuSchema):
    id: UUID
    stable_code: str | None
    name_uk: str
    position: int = Field(ge=0)
    category_count: int = Field(ge=0)
    categories: list[MenuCategoryResponse]


class MenuVersionDetail(MenuVersionSummary):
    sections: list[MenuSectionResponse]


class MenuVersionCollection(StrictMenuSchema):
    menu_id: UUID | None
    organization_id: UUID
    location_id: UUID
    current_published: MenuVersionSummary | None
    draft: MenuVersionSummary | None
    archived: list[MenuVersionSummary]


class MenuSectionCreate(StrictMenuSchema):
    name_uk: str = Field(min_length=1, max_length=200)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    position: int = Field(ge=0)
    expected_revision: int = Field(ge=0)

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()


class MenuSectionPatch(StrictMenuSchema):
    expected_revision: int = Field(ge=0)
    name_uk: str | None = Field(default=None, min_length=1, max_length=200)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    position: int | None = Field(default=None, ge=0)

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()

    @model_validator(mode="after")
    def require_mutation(self) -> Self:
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("At least one mutable field must be supplied")
        return self


class MenuCategoryCreate(StrictMenuSchema):
    section_id: UUID
    name_uk: str = Field(min_length=1, max_length=200)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    position: int = Field(ge=0)
    expected_revision: int = Field(ge=0)

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()


class MenuCategoryPatch(StrictMenuSchema):
    expected_revision: int = Field(ge=0)
    section_id: UUID | None = None
    name_uk: str | None = Field(default=None, min_length=1, max_length=200)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    position: int | None = Field(default=None, ge=0)

    @field_validator("name_uk")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _normalize_bounded_text(value, maximum=100).lower()

    @model_validator(mode="after")
    def require_mutation(self) -> Self:
        if not (self.model_fields_set - {"expected_revision"}):
            raise ValueError("At least one mutable field must be supplied")
        return self


class MenuReorderRequest(StrictMenuSchema):
    ordered_ids: list[UUID]
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        if len(self.ordered_ids) != len(set(self.ordered_ids)):
            raise ValueError("Ordered IDs must be unique")
        return self


class MenuCategoryReorderRequest(MenuReorderRequest):
    section_id: UUID


class MenuSectionMutationResponse(StrictMenuSchema):
    section: MenuSectionResponse
    revision: int = Field(ge=0)


class MenuCategoryMutationResponse(StrictMenuSchema):
    category: MenuCategoryResponse
    revision: int = Field(ge=0)


class MenuReorderResponse(StrictMenuSchema):
    ordered_ids: list[UUID]
    revision: int = Field(ge=0)


class MenuRevisionResponse(StrictMenuSchema):
    revision: int = Field(ge=0)


class MenuComponentResponse(StrictMenuSchema):
    id: UUID
    stable_code: str | None
    name_uk: str
    optional: bool | None
    position: int = Field(ge=0)
    source_kind: MenuSourceKind
    source_reference: str | None
    verified_at: datetime | None


class MenuItemResponse(StrictMenuSchema):
    item_id: UUID
    item_version_id: UUID
    version_id: UUID
    category_id: UUID
    stable_code: str | None
    name_uk: str
    description_uk: str | None
    price_minor: int | None
    currency: str
    availability: MenuAvailability
    position: int = Field(ge=0)
    component_data_status: FactDataStatus
    components: list[MenuComponentResponse]
    allergen_data_status: FactDataStatus
    allergen_codes: list[str]
    source_kind: MenuSourceKind
    source_reference: str | None
    source_item_key: str | None
    verified_at: datetime | None
    delta_kind: MenuDeltaKind
    training_impact: TrainingImpact
    changed_field_codes: list[str]
    created_at: datetime
    updated_at: datetime


class MenuItemCreate(MenuItemWrite):
    expected_revision: int = Field(ge=0)


class MenuItemMutationResponse(StrictMenuSchema):
    item: MenuItemResponse
    revision: int = Field(ge=0)


class MenuItemListResponse(StrictMenuSchema):
    items: list[MenuItemResponse]
    next_cursor: str | None
    revision: int = Field(ge=0)
