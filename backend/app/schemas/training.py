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
