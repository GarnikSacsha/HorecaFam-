"""Тип перевірки відокремлює навчальний бал від сертифікації Final Exam."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0023_course_assessment_type"
down_revision: str | None = "0022_module_position_audiences"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_CONFIGURATION = (
    "(lesson_id IS NOT NULL AND lesson_version_id IS NOT NULL "
    "AND question_count = 5 AND threshold_percent IS NULL AND feedback_policy = 'immediate') OR "
    "(lesson_id IS NULL AND lesson_version_id IS NULL "
    "AND ((question_count = 10 AND threshold_percent = 40) "
    "OR (question_count = 20 AND threshold_percent = 70)) "
    "AND feedback_policy = 'after_final_submission')"
)
COURSE_CONFIGURATION = (
    "(assessment_type = 'interactive_training' AND lesson_id IS NOT NULL "
    "AND lesson_version_id IS NOT NULL AND question_count = 5 AND threshold_percent IS NULL "
    "AND feedback_policy = 'immediate') OR "
    "(lesson_id IS NULL AND lesson_version_id IS NULL "
    "AND ((assessment_type = 'whole_menu_knowledge_check' "
    "AND question_count = 10 AND threshold_percent = 40) "
    "OR (assessment_type = 'menu_final_exam' AND question_count = 20 AND threshold_percent = 70)) "
    "AND feedback_policy = 'after_final_submission') OR "
    "(assessment_type = 'course_knowledge_check' AND lesson_id IS NOT NULL "
    "AND lesson_version_id IS NOT NULL AND question_count BETWEEN 1 AND 20 "
    "AND threshold_percent IS NULL AND feedback_policy = 'after_final_submission')"
)
LEGACY_PASS = (
    "(total_count IN (1, 2, 3, 4, 5, 10) AND pass_status IS NULL) OR "
    "(total_count = 20 AND pass_status IN ('passed', 'failed'))"
)


def _check(table: str, name: str, expression: str) -> None:
    op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
    op.create_check_constraint(name, table, expression)


def _actual_count_trigger(*, include_course: bool) -> None:
    course = (
        "OR (kind='course_knowledge_check' AND NEW.question_count=required_count)"
        if include_course
        else ""
    )
    op.execute(f"""
    CREATE OR REPLACE FUNCTION validate_assessment_actual_count()
    RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE kind text; required_count integer;
    BEGIN
      SELECT s.assessment_type, v.question_count INTO kind, required_count
        FROM assessment_versions v JOIN assessments s ON s.id=v.assessment_id
        WHERE v.id=NEW.assessment_version_id;
      IF NOT ((kind='interactive_training' AND NEW.question_count BETWEEN 1 AND 5)
        OR (kind='whole_menu_knowledge_check' AND NEW.question_count=10)
        OR (kind='menu_final_exam' AND NEW.question_count=20) {course}) THEN
        RAISE EXCEPTION 'Invalid assessment count' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    """)


def upgrade() -> None:
    _actual_count_trigger(include_course=True)
    for table in ("assessment_versions", "assessment_attempts", "attempt_results"):
        op.add_column(
            table,
            sa.Column(
                "assessment_type",
                sa.String(32),
                nullable=False,
                server_default="interactive_training",
            ),
        )
    op.execute(
        "UPDATE assessment_versions v SET assessment_type = a.assessment_type "
        "FROM assessments a WHERE a.id = v.assessment_id"
    )
    op.execute(
        "UPDATE assessment_attempts a SET assessment_type = v.assessment_type "
        "FROM assessment_versions v WHERE v.id = a.assessment_version_id"
    )
    op.execute(
        "UPDATE attempt_results r SET assessment_type = a.assessment_type "
        "FROM assessment_attempts a WHERE a.id = r.attempt_id"
    )
    for table in ("assessments", "assessment_versions", "assessment_attempts"):
        op.create_unique_constraint(f"uq_{table}_type_scope", table, ["id", "assessment_type"])
    for table, parent, key in (
        ("assessment_versions", "assessments", "assessment_id"),
        ("assessment_attempts", "assessment_versions", "assessment_version_id"),
        ("attempt_results", "assessment_attempts", "attempt_id"),
    ):
        op.create_foreign_key(
            f"fk_{table}_type_scope",
            table,
            parent,
            [key, "assessment_type"],
            ["id", "assessment_type"],
            ondelete="RESTRICT",
        )
    _check(
        "assessments",
        "assessment_type_allowed",
        "assessment_type IN ('interactive_training', 'whole_menu_knowledge_check', "
        "'menu_final_exam', 'course_knowledge_check')",
    )
    _check(
        "assessments",
        "scope_matches_type",
        "(assessment_type IN ('interactive_training', 'course_knowledge_check') "
        "AND lesson_id IS NOT NULL) OR "
        "(assessment_type IN ('whole_menu_knowledge_check', 'menu_final_exam') "
        "AND lesson_id IS NULL)",
    )
    _check("assessment_versions", "configuration_matches_scope", COURSE_CONFIGURATION)
    _check(
        "assessment_readiness",
        "counts_valid",
        "eligible_count >= 0 AND required_count BETWEEN 1 AND 20",
    )
    for table, column in (
        ("assessment_attempts", "question_count"),
        ("attempt_results", "total_count"),
    ):
        _check(
            table,
            f"{column}_allowed",
            f"(assessment_type = 'course_knowledge_check' AND {column} BETWEEN 1 AND 20) OR "
            "(assessment_type <> 'course_knowledge_check' "
            f"AND {column} IN (1, 2, 3, 4, 5, 10, 20))",
        )
    _check(
        "attempt_results",
        "pass_status_matches_count",
        "(assessment_type = 'course_knowledge_check' AND pass_status IS NULL) OR "
        f"(assessment_type <> 'course_knowledge_check' AND ({LEGACY_PASS}))",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM assessments "
            "WHERE assessment_type = 'course_knowledge_check')"
        )
    ):
        raise RuntimeError("Downgrade would discard course knowledge checks")
    _actual_count_trigger(include_course=False)
    _check("attempt_results", "pass_status_matches_count", LEGACY_PASS)
    for table, column in (
        ("assessment_attempts", "question_count"),
        ("attempt_results", "total_count"),
    ):
        _check(table, f"{column}_allowed", f"{column} IN (1, 2, 3, 4, 5, 10, 20)")
    _check(
        "assessment_readiness",
        "counts_valid",
        "eligible_count >= 0 AND required_count IN (5, 10, 20)",
    )
    _check("assessment_versions", "configuration_matches_scope", LEGACY_CONFIGURATION)
    _check(
        "assessments",
        "scope_matches_type",
        "(assessment_type = 'interactive_training' AND lesson_id IS NOT NULL) OR "
        "(assessment_type IN ('whole_menu_knowledge_check', 'menu_final_exam') "
        "AND lesson_id IS NULL)",
    )
    _check(
        "assessments",
        "assessment_type_allowed",
        "assessment_type IN ('interactive_training', 'whole_menu_knowledge_check', "
        "'menu_final_exam')",
    )
    for table in ("attempt_results", "assessment_attempts", "assessment_versions"):
        op.drop_constraint(f"fk_{table}_type_scope", table, type_="foreignkey")
    for table in ("assessment_attempts", "assessment_versions", "assessments"):
        op.drop_constraint(f"uq_{table}_type_scope", table, type_="unique")
    for table in ("attempt_results", "assessment_attempts", "assessment_versions"):
        op.drop_column(table, "assessment_type")
