from app.core.config import Settings
from app.main import create_app


def test_final_exam_attempt_lifecycle_is_exposed_without_answer_keys() -> None:
    openapi = create_app(
        Settings(app_env="test", database_url="postgresql+asyncpg://localhost/horeca_test")
    ).openapi()
    expected = {
        "/api/v1/me/training/final-exam",
        "/api/v1/me/training/final-exam/attempts",
        "/api/v1/me/training/final-exam/attempts/{attempt_id}",
        "/api/v1/me/training/final-exam/attempts/{attempt_id}/takeover",
        "/api/v1/me/training/final-exam/attempts/{attempt_id}/answer",
    }

    assert expected <= set(openapi["paths"])
    question = openapi["components"]["schemas"]["FinalExamAttemptQuestionResponse"]["properties"]
    option = openapi["components"]["schemas"]["FinalExamAttemptOptionResponse"]["properties"]
    assert "grading_payload" not in question
    assert "explanation_payload" not in question
    assert "provenance_snapshot" not in question
    assert "is_critical" not in question
    assert "is_correct" not in option
    answer = openapi["components"]["schemas"]["FinalExamAnswerResponse"]["properties"]
    assert "feedback" not in answer
    assert "result" not in answer
