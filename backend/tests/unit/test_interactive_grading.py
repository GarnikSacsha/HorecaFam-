from uuid import uuid4

from app.services.interactive_answers import grade_selected_options


def test_single_and_multiple_choice_grading_uses_snapshot_option_ids() -> None:
    correct = {uuid4(), uuid4()}
    wrong = uuid4()

    assert grade_selected_options("multiple_choice", correct, correct, [*correct, wrong]) is True
    assert (
        grade_selected_options("multiple_choice", {next(iter(correct))}, correct, [*correct])
        is False
    )
    only = next(iter(correct))
    assert grade_selected_options("single_choice", {only}, {only}, [only, wrong]) is True
    assert grade_selected_options("single_choice", {wrong}, {only}, [only, wrong]) is False
