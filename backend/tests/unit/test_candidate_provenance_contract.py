from app.models import QuestionSourceLink


def test_candidate_and_question_provenance_have_exclusive_owners() -> None:
    columns = QuestionSourceLink.__table__.columns
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in QuestionSourceLink.__table__.constraints
        if hasattr(constraint, "sqltext")
    }

    assert columns["question_candidate_id"].nullable is True
    assert columns["question_version_id"].nullable is True
    assert "ck_question_source_links_exactly_one_owner" in checks
