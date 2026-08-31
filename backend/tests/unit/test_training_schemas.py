from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.training import (
    ContentBlockWrite,
    EmployeeTrainingHomeResponse,
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
