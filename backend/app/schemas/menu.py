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
MenuImportStatus = Literal[
    "uploaded",
    "processing",
    "ready_for_review",
    "confirmed",
    "failed",
    "stale",
]
MenuFindingSeverity = Literal["blocker", "requires_review", "warning"]
MenuFindingResolutionStatus = Literal["unresolved", "resolved"]
MenuFindingResolutionAction = Literal[
    "confirm_legitimate",
    "map_existing",
    "confirm_removal",
    "confirm_critical_change",
    "exclude_source_record",
]


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


class MenuReadinessIssue(StrictMenuSchema):
    code: str
    message: str
    entity_type: str
    entity_id: UUID | None


class MenuReadinessResponse(StrictMenuSchema):
    menu_id: UUID
    menu_version_id: UUID
    organization_id: UUID
    location_id: UUID
    revision: int = Field(ge=0)
    can_publish: bool
    blocking_errors: list[MenuReadinessIssue]
    warnings: list[MenuReadinessIssue]
    required_training_asset_count: int = Field(ge=0)
    ready_training_asset_count: int = Field(ge=0)
    applicable_training_content_count: int = Field(ge=0)


class MenuPublishRequest(StrictMenuSchema):
    expected_revision: int = Field(ge=0)


class MenuDiffCounts(StrictMenuSchema):
    added: int = Field(ge=0)
    changed: int = Field(ge=0)
    removed: int = Field(ge=0)
    unchanged: int = Field(ge=0)


class MenuTrainingImpactCounts(StrictMenuSchema):
    none: int = Field(ge=0)
    review: int = Field(ge=0)
    required: int = Field(ge=0)


class MenuApplicabilityCounts(StrictMenuSchema):
    published_content_count: int = Field(ge=0)
    assignment_count: int = Field(ge=0)
    notification_count: int = Field(ge=0)


class MenuPublishResponse(StrictMenuSchema):
    published: MenuVersionSummary
    previous_published_version_id: UUID | None
    diff_counts: MenuDiffCounts
    training_impact_counts: MenuTrainingImpactCounts
    applicability: MenuApplicabilityCounts


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


class MenuImportComponent(MenuComponentInput):
    source_key: str | None = Field(default=None, min_length=1, max_length=200)


class MenuImportItem(StrictMenuSchema):
    source_key: str = Field(min_length=1, max_length=200)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str = Field(min_length=1, max_length=200)
    description_uk: str | None = Field(default=None, max_length=4000)
    price_minor: int | None = Field(default=None, ge=0)
    currency: str = Field(default="UAH", pattern=r"^[A-Z]{3}$")
    availability: MenuAvailability = "available"
    position: int = Field(ge=0)
    component_data_status: FactDataStatus
    components: list[MenuImportComponent]
    allergen_data_status: FactDataStatus
    allergen_codes: list[str]
    source_kind: MenuSourceKind = "json_import"
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    source_item_key: str | None = Field(default=None, min_length=1, max_length=200)

    @field_validator("source_key", "name_uk")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_stable_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().lower()

    @field_validator("allergen_codes")
    @classmethod
    def normalize_allergens(cls, values: list[str]) -> list[str]:
        return [value.strip().lower() for value in values]

    @model_validator(mode="after")
    def validate_facts(self) -> Self:
        MenuItemWrite.model_validate(
            {
                "category_id": UUID(int=0),
                "stable_code": self.stable_code,
                "name_uk": self.name_uk,
                "description_uk": self.description_uk,
                "price_minor": self.price_minor,
                "currency": self.currency,
                "availability": self.availability,
                "position": self.position,
                "component_data_status": self.component_data_status,
                "components": [
                    component.model_dump(exclude={"source_key"}) for component in self.components
                ],
                "allergen_data_status": self.allergen_data_status,
                "allergen_codes": self.allergen_codes,
                "source_kind": self.source_kind,
                "source_reference": self.source_reference,
                "source_item_key": self.source_item_key or self.source_key,
            }
        )
        return self


class MenuImportCategory(StrictMenuSchema):
    source_key: str = Field(min_length=1, max_length=100)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0)
    items: list[MenuImportItem]

    @field_validator("source_key", "name_uk")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @model_validator(mode="after")
    def validate_items(self) -> Self:
        keys = [item.source_key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("Item source keys must be unique inside a category")
        if [item.position for item in self.items] != list(range(len(self.items))):
            raise ValueError("Item positions must be a complete zero-based sequence")
        return self


class MenuImportSection(StrictMenuSchema):
    source_key: str = Field(min_length=1, max_length=100)
    stable_code: str | None = Field(default=None, min_length=1, max_length=100)
    name_uk: str = Field(min_length=1, max_length=200)
    position: int = Field(ge=0)
    categories: list[MenuImportCategory]

    @field_validator("source_key", "name_uk")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        return _normalize_bounded_text(value, maximum=200)

    @field_validator("stable_code")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        return value.strip().lower() if value is not None else None

    @model_validator(mode="after")
    def validate_categories(self) -> Self:
        keys = [category.source_key for category in self.categories]
        if len(keys) != len(set(keys)):
            raise ValueError("Category source keys must be unique inside a section")
        if [category.position for category in self.categories] != list(range(len(self.categories))):
            raise ValueError("Category positions must be a complete zero-based sequence")
        return self


class MenuImportCreate(StrictMenuSchema):
    source_filename: str = Field(min_length=1, max_length=255)
    source_reference: str | None = Field(default=None, min_length=1, max_length=500)
    sections: list[MenuImportSection]

    @field_validator("source_filename", "source_reference")
    @classmethod
    def normalize_source_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("Source text must not be blank")
        return normalized

    @model_validator(mode="after")
    def validate_sections(self) -> Self:
        keys = [section.source_key for section in self.sections]
        if len(keys) != len(set(keys)):
            raise ValueError("Section source keys must be unique")
        if [section.position for section in self.sections] != list(range(len(self.sections))):
            raise ValueError("Section positions must be a complete zero-based sequence")
        return self


class MenuImportFindingResponse(StrictMenuSchema):
    id: UUID
    severity: MenuFindingSeverity
    code: str
    entity_type: str
    source_key: str | None
    message: str
    resolution_status: MenuFindingResolutionStatus
    allowed_actions: list[MenuFindingResolutionAction]
    resolution_action: MenuFindingResolutionAction | None
    target_entity_id: UUID | None
    resolution_comment: str | None
    resolved_at: datetime | None


class MenuImportDetail(StrictMenuSchema):
    id: UUID
    organization_id: UUID
    location_id: UUID
    menu_id: UUID
    base_menu_version_id: UUID | None
    status: MenuImportStatus
    review_revision: int = Field(ge=0)
    source_filename: str
    source_reference: str | None
    source_checksum: str
    section_count: int = Field(ge=0)
    category_count: int = Field(ge=0)
    item_count: int = Field(ge=0)
    added_count: int = Field(ge=0)
    changed_count: int = Field(ge=0)
    removed_count: int = Field(ge=0)
    unchanged_count: int = Field(ge=0)
    blocker_count: int = Field(ge=0)
    review_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    findings: list[MenuImportFindingResponse]
    created_at: datetime
    confirmed_at: datetime | None
    failure_code: str | None


class MenuFindingResolveRequest(StrictMenuSchema):
    action: MenuFindingResolutionAction
    target_entity_id: UUID | None = None
    comment: str | None = Field(default=None, max_length=1000)
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        if self.action == "map_existing" and self.target_entity_id is None:
            raise ValueError("map_existing requires target_entity_id")
        if self.action != "map_existing" and self.target_entity_id is not None:
            raise ValueError("target_entity_id is only valid for map_existing")
        return self


class MenuFindingResolveResponse(StrictMenuSchema):
    finding: MenuImportFindingResponse
    review_revision: int = Field(ge=0)


class MenuImportConfirmRequest(StrictMenuSchema):
    expected_revision: int = Field(ge=0)
    acknowledge_warnings: bool


class MenuImportConfirmResponse(StrictMenuSchema):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    import_: MenuImportDetail = Field(alias="import", serialization_alias="import")
    draft: MenuVersionDetail
