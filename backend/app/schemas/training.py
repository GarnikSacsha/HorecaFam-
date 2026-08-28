import re
from datetime import datetime
from typing import Literal, Self
from urllib.parse import parse_qs, urlparse
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import ContentBlockType

YOUTUBE_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")


class StrictTrainingSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _text(value: str, *, maximum: int) -> str:
    normalized = value.strip()
    if not normalized or len(normalized) > maximum:
        raise ValueError("Text is outside the accepted bounds")
    return normalized


def _optional_text(value: str | None, *, maximum: int) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > maximum:
        raise ValueError("Text is outside the accepted bounds")
    return normalized


class HeadingPayload(StrictTrainingSchema):
    level: Literal[2, 3]
    text_uk: str = Field(min_length=1, max_length=160)

    @field_validator("text_uk")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _text(value, maximum=160)


class TextPayload(StrictTrainingSchema):
    text_uk: str = Field(min_length=1, max_length=8000)

    @field_validator("text_uk")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _text(value, maximum=8000)


class ListPayload(StrictTrainingSchema):
    style: Literal["unordered", "ordered"]
    items_uk: list[str] = Field(min_length=1, max_length=20)

    @field_validator("items_uk")
    @classmethod
    def normalize_items(cls, values: list[str]) -> list[str]:
        return [_text(value, maximum=300) for value in values]


class CalloutPayload(StrictTrainingSchema):
    tone: Literal["info", "tip", "warning", "critical"]
    title_uk: str | None = Field(default=None, max_length=120)
    text_uk: str = Field(min_length=1, max_length=2000)

    @field_validator("title_uk")
    @classmethod
    def normalize_title(cls, value: str | None) -> str | None:
        return _optional_text(value, maximum=120)

    @field_validator("text_uk")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return _text(value, maximum=2000)


class MenuItemCardPayload(StrictTrainingSchema):
    menu_item_id: UUID
    note_uk: str | None = Field(default=None, max_length=500)

    @field_validator("note_uk")
    @classmethod
    def normalize_note(cls, value: str | None) -> str | None:
        return _optional_text(value, maximum=500)


class ImagePayload(StrictTrainingSchema):
    asset_id: UUID
    alt_uk: str = Field(min_length=1, max_length=300)
    caption_uk: str | None = Field(default=None, max_length=500)

    @field_validator("alt_uk")
    @classmethod
    def normalize_alt(cls, value: str) -> str:
        return _text(value, maximum=300)

    @field_validator("caption_uk")
    @classmethod
    def normalize_caption(cls, value: str | None) -> str | None:
        return _optional_text(value, maximum=500)


def _youtube_video_id(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS YouTube URLs are accepted")
    host = parsed.hostname.lower() if parsed.hostname else ""
    video_id: str | None = None
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/")[0]
    elif host in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        if parsed.path == "/watch":
            video_id = parse_qs(parsed.query).get("v", [None])[0]
        elif parsed.path.startswith(("/shorts/", "/embed/")):
            video_id = parsed.path.strip("/").split("/")[1]
    if video_id is None or YOUTUBE_VIDEO_ID.fullmatch(video_id) is None:
        raise ValueError("A valid YouTube video URL is required")
    return video_id


class ExternalVideoPayload(StrictTrainingSchema):
    url: str = Field(min_length=1, max_length=500)
    title_uk: str = Field(min_length=1, max_length=200)
    summary_uk: str = Field(min_length=1, max_length=2000)

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        _youtube_video_id(value)
        return value.strip()

    @field_validator("title_uk")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return _text(value, maximum=200)

    @field_validator("summary_uk")
    @classmethod
    def normalize_summary(cls, value: str) -> str:
        return _text(value, maximum=2000)


PAYLOAD_MODELS: dict[ContentBlockType, type[StrictTrainingSchema]] = {
    ContentBlockType.HEADING: HeadingPayload,
    ContentBlockType.TEXT: TextPayload,
    ContentBlockType.LIST: ListPayload,
    ContentBlockType.CALLOUT: CalloutPayload,
    ContentBlockType.MENU_ITEM_CARD: MenuItemCardPayload,
    ContentBlockType.IMAGE: ImagePayload,
    ContentBlockType.EXTERNAL_VIDEO: ExternalVideoPayload,
}


def validate_content_payload(
    block_type: ContentBlockType,
    payload: dict[str, object],
) -> tuple[dict[str, object], UUID | None, UUID | None]:
    validated = PAYLOAD_MODELS[block_type].model_validate(payload)
    values = validated.model_dump()
    menu_item_id = values.pop("menu_item_id", None)
    asset_id = values.pop("asset_id", None)
    if block_type == ContentBlockType.EXTERNAL_VIDEO:
        url = values.pop("url")
        values = {
            "provider": "youtube",
            "video_id": _youtube_video_id(str(url)),
            **values,
        }
    return values, menu_item_id, asset_id


class ContentBlockWrite(StrictTrainingSchema):
    type: ContentBlockType
    payload: dict[str, object]
    expected_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_payload_shape(self) -> Self:
        validate_content_payload(self.type, self.payload)
        return self


class ContentBlockUpdate(StrictTrainingSchema):
    payload: dict[str, object]
    expected_revision: int = Field(ge=0)


class ReorderRequest(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)
    ordered_ids: list[UUID]

    @model_validator(mode="after")
    def require_unique_ids(self) -> Self:
        if len(self.ordered_ids) != len(set(self.ordered_ids)):
            raise ValueError("Ordered IDs must be unique")
        return self


class TrainingVersionCreate(StrictTrainingSchema):
    base_version_id: UUID | None = None


class TrainingModulePatch(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)
    title_uk: str = Field(min_length=1, max_length=200)
    description_uk: str | None = Field(default=None, max_length=2000)
    required: bool


class TrainingLessonCreate(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)
    title_uk: str = Field(min_length=1, max_length=200)
    description_uk: str | None = Field(default=None, max_length=2000)
    required: bool
    estimated_minutes: int | None = Field(default=None, ge=1, le=240)


class TrainingLessonPatch(TrainingLessonCreate):
    pass


class AssetUploadIntentCreate(StrictTrainingSchema):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    size_bytes: int = Field(ge=1, le=5 * 1024 * 1024)
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class AssetUploadComplete(StrictTrainingSchema):
    sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")


class TrainingAssetResponse(StrictTrainingSchema):
    id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    ready_at: datetime | None
    created_at: datetime


class AssetUploadIntentResponse(StrictTrainingSchema):
    asset_id: UUID
    upload_url: str
    upload_fields: dict[str, str]
    expires_at: datetime


class AssetAccessResponse(StrictTrainingSchema):
    url: str
    expires_in: Literal[300] = 300


class TrainingContentBlockResponse(StrictTrainingSchema):
    id: UUID
    type: ContentBlockType
    position: int
    payload: dict[str, object]
    menu_item_id: UUID | None
    asset: TrainingAssetResponse | None


class TrainingLessonResponse(StrictTrainingSchema):
    id: UUID
    position: int
    title_uk: str
    description_uk: str | None
    required: bool
    estimated_minutes: int | None
    translation_status_en: str | None
    content_blocks: list[TrainingContentBlockResponse]


class TrainingModuleResponse(StrictTrainingSchema):
    id: UUID
    domain_type: Literal["menu"]
    position: int
    title_uk: str
    description_uk: str | None
    required: bool
    translation_status_en: str | None
    lessons: list[TrainingLessonResponse]


class TrainingVersionSummary(StrictTrainingSchema):
    id: UUID
    training_id: UUID
    location_id: UUID
    version_number: int
    status: Literal["draft", "published", "archived"]
    revision: int
    base_version_id: UUID | None
    module_count: int
    lesson_count: int
    created_at: datetime
    published_at: datetime | None
    archived_at: datetime | None


class TrainingVersionDetail(TrainingVersionSummary):
    modules: list[TrainingModuleResponse]
    menu_version_id: UUID | None


class TrainingVersionCollection(StrictTrainingSchema):
    published: TrainingVersionSummary | None
    draft: TrainingVersionSummary | None
    archived: list[TrainingVersionSummary]


class TrainingModuleMutationResponse(StrictTrainingSchema):
    module: TrainingModuleResponse
    revision: int


class TrainingLessonMutationResponse(StrictTrainingSchema):
    lesson: TrainingLessonResponse
    revision: int


class TrainingContentBlockMutationResponse(StrictTrainingSchema):
    content_block: TrainingContentBlockResponse
    revision: int


class TrainingRevisionResponse(StrictTrainingSchema):
    revision: int


class TrainingReorderResponse(StrictTrainingSchema):
    ordered_ids: list[UUID]
    revision: int


class TrainingReadinessIssue(StrictTrainingSchema):
    code: str
    message: str
    entity_type: str
    entity_id: UUID | None


class TrainingReadinessCounts(StrictTrainingSchema):
    module_count: int
    lesson_count: int
    required_lesson_count: int
    content_block_count: int
    required_asset_count: int
    ready_asset_count: int
    menu_item_link_count: int


class TrainingReadinessResponse(StrictTrainingSchema):
    training_id: UUID
    training_version_id: UUID
    organization_id: UUID
    location_id: UUID
    revision: int
    can_publish: bool
    blocking_errors: list[TrainingReadinessIssue]
    warnings: list[TrainingReadinessIssue]
    counts: TrainingReadinessCounts


class TrainingPublishRequest(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)


class TrainingAudienceUpdate(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)
    operational_role_ids: list[UUID]

    @field_validator("operational_role_ids")
    @classmethod
    def require_unique_roles(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Operational Role ids must be unique")
        return value


class TrainingAudienceResponse(StrictTrainingSchema):
    training_version_id: UUID
    revision: int
    operational_role_ids: list[UUID]


class TrainingPublishResponse(StrictTrainingSchema):
    published: TrainingVersionSummary
    previous_published_version_id: UUID | None
    employee_reference_switched: bool
    assignment_count: int = Field(ge=0)
    completion_count: int = Field(ge=0)
    progress_count: int = Field(ge=0)
    rollout_count: int = Field(ge=0)
    notification_count: int = Field(ge=0)
    rollout_id: UUID | None = None


class TrainingAssignmentCreate(StrictTrainingSchema):
    training_version_id: UUID | None = None
    reason: str | None = Field(default=None, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class TrainingAssignmentRevoke(StrictTrainingSchema):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Reason must not be blank")
        return normalized


class TrainingAssignmentReassign(TrainingAssignmentCreate):
    pass


class TrainingAssignmentResponse(StrictTrainingSchema):
    id: UUID
    organization_id: UUID
    location_id: UUID
    training_id: UUID
    employee_profile_id: UUID
    training_version_id: UUID
    status: Literal["assigned", "in_progress", "completed", "revoked"]
    source: Literal["automatic", "admin", "reassign", "rollout"]
    previous_assignment_id: UUID | None
    source_rollout_id: UUID | None
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    revoked_at: datetime | None
    revoke_reason: Literal["admin", "role_changed", "location_changed", "rollout"] | None
    revoke_note: str | None


class TrainingProgressResponse(StrictTrainingSchema):
    required_lesson_count: int = Field(ge=0)
    completed_required_lesson_count: int = Field(ge=0)
    percentage: int = Field(ge=0, le=100)
    is_complete: bool


class TrainingAssignmentListResponse(StrictTrainingSchema):
    current: TrainingAssignmentResponse | None
    history: list[TrainingAssignmentResponse]
    progress: TrainingProgressResponse | None


class EmployeeTrainingSummary(StrictTrainingSchema):
    id: UUID
    version_number: int
    published_at: datetime


class EmployeeTrainingAssignmentSummary(StrictTrainingSchema):
    id: UUID
    status: Literal["assigned", "in_progress", "completed"]
    assigned_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class EmployeeTrainingModuleSummary(StrictTrainingSchema):
    id: UUID
    domain_type: Literal["menu"]
    title: str
    description: str | None
    position: int
    required: bool
    lesson_count: int
    content_locale: Literal["uk", "en"]
    translation_fallback: bool


class EmployeeTrainingLessonSummary(StrictTrainingSchema):
    id: UUID
    title: str
    description: str | None
    position: int
    required: bool
    estimated_minutes: int | None
    completed: bool
    content_locale: Literal["uk", "en"]
    translation_fallback: bool


class EmployeeTrainingContentBlock(StrictTrainingSchema):
    id: UUID
    type: ContentBlockType
    position: int
    payload: dict[str, object]
    content_locale: Literal["uk", "en"]
    translation_fallback: bool


class EmployeeTrainingHomeResponse(StrictTrainingSchema):
    assignment: EmployeeTrainingAssignmentSummary | None
    training: EmployeeTrainingSummary | None
    modules: list[EmployeeTrainingModuleSummary]
    progress: TrainingProgressResponse | None
    next_action: Literal["open_lesson", "review_training", "none"]
    content_locale: Literal["uk", "en"]
    translation_fallback: bool


class EmployeeTrainingModuleDetail(EmployeeTrainingModuleSummary):
    lessons: list[EmployeeTrainingLessonSummary]


class EmployeeTrainingLessonDetail(EmployeeTrainingLessonSummary):
    content_blocks: list[EmployeeTrainingContentBlock]


class LessonCompletionSummary(StrictTrainingSchema):
    id: UUID
    assignment_id: UUID
    lesson_id: UUID
    lesson_version_id: UUID
    completion_source: Literal["employee", "rollout_preserved", "reassignment_preserved"]
    completed_at: datetime


class LessonCompletionResponse(StrictTrainingSchema):
    completion: LessonCompletionSummary
    assignment: EmployeeTrainingAssignmentSummary
    progress: TrainingProgressResponse
    next_action: Literal["open_lesson", "review_training", "none"]


class TrainingRolloutCreate(StrictTrainingSchema):
    from_version_id: UUID
    to_version_id: UUID


class TrainingRolloutPreviewRequest(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)


class TrainingRolloutLessonRuleUpdate(StrictTrainingSchema):
    expected_revision: int = Field(ge=0)
    rule: Literal["preserve_completion", "needs_repeat"]


class TrainingRolloutVersionSummary(StrictTrainingSchema):
    id: UUID
    version_number: int = Field(ge=1)
    status: Literal["published", "archived"]
    revision: int = Field(ge=0)


class TrainingRolloutLessonRuleResponse(StrictTrainingSchema):
    lesson_id: UUID
    from_lesson_version_id: UUID | None
    to_lesson_version_id: UUID | None
    rule: (
        Literal[
            "preserve_completion",
            "needs_repeat",
            "new_incomplete",
            "removed_historical",
        ]
        | None
    )
    requires_admin_decision: bool
    decided_by_user_id: UUID | None
    decided_at: datetime | None


class TrainingRolloutEmployeeImpactResponse(StrictTrainingSchema):
    employee_profile_id: UUID
    source_assignment_id: UUID
    current_required_count: int = Field(ge=0)
    current_completed_count: int = Field(ge=0)
    current_progress_percentage: int = Field(ge=0, le=100)
    projected_required_count: int = Field(ge=0)
    projected_completed_count: int = Field(ge=0)
    projected_progress_percentage: int = Field(ge=0, le=100)
    lesson_impact: dict[str, list[UUID]]
    validation_codes: list[str]
    warning_codes: list[str]


class TrainingRolloutImpactCounts(StrictTrainingSchema):
    employee_count: int = Field(ge=0)
    unresolved_rule_count: int = Field(ge=0)


class TrainingRolloutResponse(StrictTrainingSchema):
    id: UUID
    organization_id: UUID
    location_id: UUID
    training_id: UUID
    from_version: TrainingRolloutVersionSummary
    to_version: TrainingRolloutVersionSummary
    status: Literal[
        "draft",
        "preview_ready",
        "confirmed",
        "processing",
        "completed",
        "failed",
        "cancelled",
        "stale",
    ]
    revision: int = Field(ge=0)
    rules: list[TrainingRolloutLessonRuleResponse]
    employee_impacts: list[TrainingRolloutEmployeeImpactResponse]
    impact_counts: TrainingRolloutImpactCounts
    is_stale: bool
    warning_codes: list[str]
    previewed_at: datetime | None
    created_at: datetime
