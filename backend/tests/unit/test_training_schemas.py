from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.training import (
    ContentBlockWrite,
    EmployeeTrainingHomeResponse,
    ReorderRequest,
    validate_content_payload,
)


@pytest.mark.parametrize(
    ("block_type", "payload"),
    [
        ("heading", {"level": 2, "text_uk": "Походження страви"}),
        ("text", {"text_uk": "Подавайте теплою."}),
        ("list", {"style": "unordered", "items_uk": ["Перше", "Друге"]}),
        ("callout", {"tone": "tip", "title_uk": "Порада", "text_uk": "Уточніть алергени."}),
        ("menu_item_card", {"menu_item_id": uuid4(), "note_uk": "Рекомендуйте до вина."}),
        ("image", {"asset_id": uuid4(), "alt_uk": "Борщ у білій тарілці", "caption_uk": None}),
        (
            "external_video",
            {
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title_uk": "Подача",
                "summary_uk": "Коротка демонстрація подачі.",
            },
        ),
    ],
)
def test_all_content_block_variants_are_strict(block_type: str, payload: dict[str, object]) -> None:
    request = ContentBlockWrite(type=block_type, payload=payload, expected_revision=0)
    canonical, menu_item_id, asset_id = validate_content_payload(request.type, request.payload)

    assert canonical
    if block_type == "external_video":
        assert canonical == {
            "provider": "youtube",
            "video_id": "dQw4w9WgXcQ",
            "title_uk": "Подача",
            "summary_uk": "Коротка демонстрація подачі.",
        }
    assert menu_item_id == payload.get("menu_item_id")
    assert asset_id == payload.get("asset_id")


@pytest.mark.parametrize(
    ("block_type", "payload"),
    [
        ("heading", {"level": 1, "text_uk": "Неправильний рівень"}),
        ("text", {"text_uk": ""}),
        ("list", {"style": "ordered", "items_uk": []}),
        ("callout", {"tone": "other", "text_uk": "Текст"}),
        ("menu_item_card", {"menu_item_id": uuid4(), "unknown": True}),
        ("image", {"asset_id": uuid4(), "alt_uk": ""}),
        (
            "external_video",
            {"url": "https://example.com/video", "title_uk": "Відео", "summary_uk": "Опис"},
        ),
    ],
)
def test_invalid_content_payload_is_rejected(block_type: str, payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ContentBlockWrite(type=block_type, payload=payload, expected_revision=0)


def test_unknown_fields_and_block_types_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ContentBlockWrite(
            type="html",
            payload={"html": "<iframe src='https://example.com'></iframe>"},
            expected_revision=0,
        )


def test_employee_home_contract_exposes_final_exam_as_a_bounded_next_action() -> None:
    response = EmployeeTrainingHomeResponse(
        assignment=None,
        training=None,
        modules=[],
        progress=None,
        next_action="open_final_exam",
        content_locale="uk",
        translation_fallback=False,
    )

    assert response.next_action == "open_final_exam"


@pytest.mark.parametrize(
    "url",
    [
        "https://youtu.be/dQw4w9WgXcQ",
        "https://m.youtube.com/shorts/dQw4w9WgXcQ",
        "https://youtube.com/embed/dQw4w9WgXcQ",
    ],
)
def test_supported_video_links_store_only_canonical_identity(url: str) -> None:
    request = ContentBlockWrite(
        type="external_video",
        expected_revision=0,
        payload={
            "url": url,
            "title_uk": " Подача ",
            "summary_uk": " Демонстрація ",
        },
    )
    canonical, item, asset = validate_content_payload(request.type, request.payload)
    assert canonical == {
        "provider": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "title_uk": "Подача",
        "summary_uk": "Демонстрація",
    }
    assert item is asset is None


@pytest.mark.parametrize(
    "url",
    [
        "http://youtu.be/dQw4w9WgXcQ",
        "https:///watch?v=dQw4w9WgXcQ",
        "https://youtube.com/watch",
        "https://youtube.com/channel/dQw4w9WgXcQ",
        "https://youtu.be/short",
        "https://youtube.com.evil.test/watch?v=dQw4w9WgXcQ",
    ],
)
def test_invalid_video_links_are_rejected(url: str) -> None:
    with pytest.raises(ValidationError):
        ContentBlockWrite(
            type="external_video",
            expected_revision=0,
            payload={
                "url": url,
                "title_uk": "Подача",
                "summary_uk": "Демонстрація",
            },
        )


@pytest.mark.parametrize("text", ["   ", "я" * 301])
def test_list_entries_require_bounded_nonblank_text(text: str) -> None:
    with pytest.raises(ValidationError):
        ContentBlockWrite(
            type="list", expected_revision=0, payload={"style": "ordered", "items_uk": [text]}
        )


def test_optional_copy_normalizes_blank_and_order_rejects_duplicates() -> None:
    request = ContentBlockWrite(
        type="callout",
        expected_revision=0,
        payload={"tone": "info", "title_uk": "  ", "text_uk": " Текст "},
    )
    canonical, _, _ = validate_content_payload(request.type, request.payload)
    assert canonical == {"tone": "info", "title_uk": None, "text_uk": "Текст"}
    identifier = uuid4()
    with pytest.raises(ValidationError):
        ReorderRequest(expected_revision=0, ordered_ids=[identifier, identifier])


def test_duplicate_audience_and_blank_revoke_reason_are_rejected() -> None:
    from app.schemas.training import TrainingAssignmentRevoke, TrainingAudienceUpdate

    role_id = uuid4()
    with pytest.raises(ValidationError, match="Operational Role ids must be unique"):
        TrainingAudienceUpdate(expected_revision=0, operational_role_ids=[role_id, role_id])
    with pytest.raises(ValidationError, match="Reason must not be blank"):
        TrainingAssignmentRevoke(reason="   ")
