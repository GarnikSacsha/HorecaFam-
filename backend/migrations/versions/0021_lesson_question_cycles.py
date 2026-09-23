"""Зберігаємо цикл видачі питань незалежно від версії уроку."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0021_lesson_question_cycles"
down_revision: str | None = "0020_menu_change_history"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _counts(short: bool) -> None:
    values = "1, 2, 3, 4, 5, 10, 20" if short else "5, 10, 20"
    for table, column in [
        ("assessment_attempts", "question_count"),
        ("attempt_results", "total_count"),
    ]:
        name = f"{column}_allowed"
        op.drop_constraint(op.f(f"ck_{table}_{name}"), table, type_="check")
        op.create_check_constraint(name, table, f"{column} IN ({values})")
    op.drop_constraint(
        op.f("ck_attempt_results_pass_status_matches_count"), "attempt_results", type_="check"
    )
    null_values = "1, 2, 3, 4, 5, 10" if short else "5, 10"
    op.create_check_constraint(
        "pass_status_matches_count",
        "attempt_results",
        f"(total_count IN ({null_values}) AND pass_status IS NULL) OR "
        "(total_count = 20 AND pass_status IN ('passed', 'failed'))",
    )


def upgrade() -> None:
    _counts(True)
    op.create_table(
        "lesson_question_cycles",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "organization_id",
            sa.UUID(),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            sa.UUID(),
            sa.ForeignKey("locations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column(
            "lesson_id", sa.UUID(), sa.ForeignKey("lessons.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "employee_profile_id", "lesson_id", "number", name="uq_lesson_cycle_number"
        ),
        sa.CheckConstraint("number > 0", name="number_positive"),
    )
    op.create_index(
        "uq_lesson_cycle_active",
        "lesson_question_cycles",
        ["employee_profile_id", "lesson_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )
    op.create_table(
        "lesson_question_cycle_items",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "cycle_id",
            sa.UUID(),
            sa.ForeignKey("lesson_question_cycles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("question_id", sa.UUID(), nullable=False),
        sa.Column("question_version_id", sa.UUID(), nullable=False),
        sa.Column(
            "attempt_question_id",
            sa.UUID(),
            sa.ForeignKey("attempt_questions.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.ForeignKeyConstraint(
            ["question_version_id", "question_id"],
            ["question_versions.id", "question_versions.question_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("cycle_id", "question_id", name="uq_lesson_cycle_question"),
        sa.CheckConstraint("origin IN ('legacy', 'reserved')", name="origin_allowed"),
    )
    statements = """
    CREATE FUNCTION validate_lesson_cycle() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'UPDATE' AND (NEW.organization_id <> OLD.organization_id
        OR NEW.location_id <> OLD.location_id OR NEW.employee_profile_id <> OLD.employee_profile_id
        OR NEW.lesson_id <> OLD.lesson_id OR NEW.number <> OLD.number
        OR NEW.created_at <> OLD.created_at OR OLD.ended_at IS NOT NULL) THEN
        RAISE EXCEPTION 'Immutable lesson cycle identity' USING ERRCODE='23514';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM lessons l JOIN training_modules m ON m.id=l.training_module_id
        JOIN trainings t ON t.id=m.training_id
        JOIN employee_profiles e ON e.id=NEW.employee_profile_id
        WHERE l.id=NEW.lesson_id AND t.organization_id=NEW.organization_id
        AND t.location_id=NEW.location_id AND e.organization_id=NEW.organization_id
        AND e.location_id=NEW.location_id) THEN
        RAISE EXCEPTION 'Invalid lesson cycle scope' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER lesson_cycle_scope BEFORE INSERT OR UPDATE ON lesson_question_cycles
      FOR EACH ROW EXECUTE FUNCTION validate_lesson_cycle();
    CREATE FUNCTION validate_lesson_cycle_item() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Immutable lesson cycle item' USING ERRCODE='23514';
      END IF;
      IF NOT EXISTS (SELECT 1 FROM lesson_question_cycles c
        JOIN attempt_questions q ON q.id=NEW.attempt_question_id
        JOIN assessment_attempts a ON a.id=q.attempt_id
        JOIN assessment_versions v ON v.id=a.assessment_version_id
        JOIN assessments s ON s.id=v.assessment_id
        JOIN question_versions qv ON qv.id=q.question_version_id
        WHERE c.id=NEW.cycle_id AND a.organization_id=c.organization_id
        AND a.location_id=c.location_id AND a.employee_profile_id=c.employee_profile_id
        AND v.lesson_id=c.lesson_id AND s.assessment_type='interactive_training'
        AND qv.organization_id=c.organization_id AND qv.location_id=c.location_id
        AND q.question_version_id=NEW.question_version_id AND qv.question_id=NEW.question_id) THEN
        RAISE EXCEPTION 'Invalid lesson cycle item scope' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER lesson_cycle_item_scope BEFORE INSERT OR UPDATE ON lesson_question_cycle_items
      FOR EACH ROW EXECUTE FUNCTION validate_lesson_cycle_item();
    CREATE FUNCTION validate_assessment_actual_count() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE kind text;
    BEGIN
      SELECT s.assessment_type INTO kind FROM assessment_versions v
        JOIN assessments s ON s.id=v.assessment_id WHERE v.id=NEW.assessment_version_id;
      IF NOT ((kind='interactive_training' AND NEW.question_count BETWEEN 1 AND 5)
        OR (kind='whole_menu_knowledge_check' AND NEW.question_count=10)
        OR (kind='menu_final_exam' AND NEW.question_count=20)) THEN
        RAISE EXCEPTION 'Invalid assessment count' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER assessment_actual_count BEFORE INSERT OR UPDATE ON assessment_attempts
      FOR EACH ROW EXECUTE FUNCTION validate_assessment_actual_count();
    CREATE FUNCTION validate_result_actual_count() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF NOT EXISTS (SELECT 1 FROM assessment_attempts a WHERE a.id=NEW.attempt_id
        AND a.question_count=NEW.total_count) THEN
        RAISE EXCEPTION 'Invalid result count' USING ERRCODE='23514';
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER result_actual_count BEFORE INSERT OR UPDATE ON attempt_results
      FOR EACH ROW EXECUTE FUNCTION validate_result_actual_count();
    """
    for statement in statements.split("\n    CREATE "):
        if statement.strip():
            op.execute("CREATE " + statement.strip())


def downgrade() -> None:
    op.execute("DROP TRIGGER result_actual_count ON attempt_results")
    op.execute("DROP FUNCTION validate_result_actual_count()")
    op.execute("DROP TRIGGER assessment_actual_count ON assessment_attempts")
    op.execute("DROP FUNCTION validate_assessment_actual_count()")
    op.drop_table("lesson_question_cycle_items")
    op.drop_table("lesson_question_cycles")
    op.execute("DROP FUNCTION validate_lesson_cycle_item()")
    op.execute("DROP FUNCTION validate_lesson_cycle()")
    _counts(False)
