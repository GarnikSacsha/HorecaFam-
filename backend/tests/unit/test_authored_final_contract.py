from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.main import create_app
from app.schemas.assessment import AuthoredQuestionRequest


def test_authored_candidate_and_versioned_final_mutations_exist() -> None:
    schema = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://localhost/horeca_test")
    ).openapi()
    prefix = "/api/v1/organizations/{organization_id}/locations/{location_id}"
    for path in (
        prefix + "/question-candidates/authored",
        prefix + "/training-versions/{version_id}/final-exam/versions",
    ):
        assert path in schema["paths"]
        operation = schema["paths"][path]["post"]
        assert any(p["name"] == "Idempotency-Key" for p in operation["parameters"])


@pytest.mark.parametrize(
    "invalid",
    ["unknown_key", "multiple_keys", "missing_evidence", "rationales", "duplicate_labels"],
)
def test_authored_answer_and_evidence_must_be_unambiguous(invalid: str) -> None:
    payload = {
        "training_version_id": str(uuid4()),
        "lesson_version_id": str(uuid4()),
        "prompt_payload": {
            "stem": "Question",
            "selection_mode": "single",
            "options": [{"stable_key": str(i), "text": str(i)} for i in range(4)],
        },
        "answer_payload": {"correct_option_keys": ["0"]},
        "explanation_payload": {
            "text": "Explanation",
            "authoring": {
                "menu_version_id": str(uuid4()),
                "menu_item_version_id": str(uuid4()),
                "source_quote": "Source",
                "option_rationales": {str(i): "Reason" for i in range(4)},
            },
        },
    }
    valid = AuthoredQuestionRequest.model_validate(payload)
    if invalid == "unknown_key":
        valid.answer_payload.correct_option_keys = ["outside"]
    elif invalid == "multiple_keys":
        valid.answer_payload.correct_option_keys = ["0", "1"]
    elif invalid == "missing_evidence":
        valid.explanation_payload.authoring = None
    elif invalid == "rationales":
        assert valid.explanation_payload.authoring is not None
        valid.explanation_payload.authoring.option_rationales = {
            str(i + 1): "Reason" for i in range(4)
        }
    else:
        valid.prompt_payload.options[1].text = valid.prompt_payload.options[0].text
    raw = valid.model_dump(mode="json")
    if valid.explanation_payload.authoring is not None:
        raw["explanation_payload"]["authoring"] = valid.explanation_payload.authoring.model_dump(
            mode="json"
        )
    with pytest.raises(ValidationError):
        AuthoredQuestionRequest.model_validate(raw)
