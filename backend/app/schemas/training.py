import re
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
