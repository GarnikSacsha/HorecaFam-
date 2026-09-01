"""Додає Attention/Retake persistence і детерміновану історичну проєкцію.

Revision ID: 0015_attention_retakes
Revises: 0014_practice_persistence
Create Date: 2026-09-01 10:44:07.969172
"""

# ruff: noqa: E501

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_attention_retakes"
down_revision: str | None = "0014_practice_persistence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _project_historical_follow_up() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            WITH critical_candidates AS (
                SELECT DISTINCT ON (answer.id)
                    answer.id AS submitted_answer_id,
                    attempt.organization_id,
                    attempt.location_id,
                    attempt.training_id,
                    attempt.employee_profile_id,
                    attempt.assignment_id,
                    attempt.id AS attempt_id,
                    question.id AS attempt_question_id,
                    item_version.menu_id,
                    item_version.menu_item_id,
                    allergen.allergen_id,
                    (
                        'menu_item:' || item_version.menu_item_id::text
                        || ':allergen:' || allergen.allergen_id::text
                    ) AS subject_key,
                    jsonb_build_object(
                        'assessment_type', assessment.assessment_type,
                        'attempt_question_position', question.position
                    ) AS safe_context,
                    answer.submitted_at AS occurred_at
                FROM submitted_answers AS answer
                JOIN assessment_attempts AS attempt
                  ON attempt.id = answer.attempt_id
                JOIN attempt_questions AS question
                  ON question.id = answer.attempt_question_id
                 AND question.attempt_id = answer.attempt_id
                JOIN assessment_versions AS assessment_version
                  ON assessment_version.id = attempt.assessment_version_id
                JOIN assessments AS assessment
                  ON assessment.id = assessment_version.assessment_id
                CROSS JOIN LATERAL jsonb_array_elements(
                    CASE
                        WHEN jsonb_typeof(question.provenance_snapshot -> 'sources') = 'array'
                        THEN question.provenance_snapshot -> 'sources'
                        ELSE '[]'::jsonb
                    END
                ) AS source(value)
                JOIN menu_item_version_allergens AS allergen
                  ON allergen.id = CASE
                      WHEN source.value ->> 'menu_item_version_allergen_id'
                           ~* '^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
                      THEN (source.value ->> 'menu_item_version_allergen_id')::uuid
                      ELSE NULL
                  END
                JOIN menu_item_versions AS item_version
                  ON item_version.id = allergen.menu_item_version_id
                WHERE attempt.status = 'completed'
                  AND attempt.question_count IN (10, 20)
                  AND assessment.assessment_type IN (
                      'whole_menu_knowledge_check',
                      'menu_final_exam'
                  )
                  AND question.is_critical IS TRUE
                  AND answer.is_critical_error IS TRUE
                  AND answer.is_correct IS FALSE
                  AND source.value ->> 'role' = 'correct_fact'
                  AND allergen.organization_id = attempt.organization_id
                  AND allergen.location_id = attempt.location_id
                ORDER BY answer.id, allergen.id
            )
            INSERT INTO critical_errors (
                id,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                assignment_id,
                attempt_id,
                attempt_question_id,
                submitted_answer_id,
                menu_id,
                menu_item_id,
                allergen_id,
                critical_type,
                subject_key,
                safe_context,
                occurred_at,
                created_at
            )
            SELECT
                md5('critical-error:' || submitted_answer_id::text)::uuid,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                assignment_id,
                attempt_id,
                attempt_question_id,
                submitted_answer_id,
                menu_id,
                menu_item_id,
                allergen_id,
                'allergen',
                subject_key,
                safe_context,
                occurred_at,
                occurred_at
            FROM critical_candidates
            ON CONFLICT (submitted_answer_id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            WITH grouped AS (
                SELECT
                    organization_id,
                    location_id,
                    training_id,
                    employee_profile_id,
                    subject_key,
                    min(occurred_at) AS opened_at
                FROM critical_errors
                GROUP BY
                    organization_id,
                    location_id,
                    training_id,
                    employee_profile_id,
                    subject_key
            )
            INSERT INTO attention_cases (
                id,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                case_type,
                subject_key,
                state,
                revision,
                created_at,
                updated_at
            )
            SELECT
                md5(
                    'critical-case:'
                    || organization_id::text || ':'
                    || employee_profile_id::text || ':'
                    || training_id::text || ':'
                    || subject_key
                )::uuid,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                'critical_allergen',
                subject_key,
                'open',
                0,
                opened_at,
                opened_at
            FROM grouped
            ON CONFLICT DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_case_sources (
                id,
                organization_id,
                location_id,
                attention_case_id,
                critical_error_id,
                created_at
            )
            SELECT
                md5('attention-source-critical:' || error.id::text)::uuid,
                error.organization_id,
                error.location_id,
                case_row.id,
                error.id,
                error.occurred_at
            FROM critical_errors AS error
            JOIN attention_cases AS case_row
              ON case_row.organization_id = error.organization_id
             AND case_row.employee_profile_id = error.employee_profile_id
             AND case_row.training_id = error.training_id
             AND case_row.case_type = 'critical_allergen'
             AND case_row.subject_key = error.subject_key
             AND case_row.state IN ('open', 'acknowledged')
            ON CONFLICT DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_case_actions (
                id,
                organization_id,
                location_id,
                attention_case_id,
                actor_type,
                action,
                from_state,
                to_state,
                details,
                created_at
            )
            SELECT
                md5('attention-opened:' || case_row.id::text)::uuid,
                case_row.organization_id,
                case_row.location_id,
                case_row.id,
                'system',
                'opened',
                NULL,
                'open',
                '{}'::jsonb,
                case_row.created_at
            FROM attention_cases AS case_row
            WHERE case_row.case_type = 'critical_allergen'
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_case_actions (
                id,
                organization_id,
                location_id,
                attention_case_id,
                actor_type,
                action,
                details,
                created_at
            )
            SELECT
                md5('attention-source-added:' || source.id::text)::uuid,
                source.organization_id,
                source.location_id,
                source.attention_case_id,
                'system',
                'source_added',
                jsonb_build_object('critical_error_id', source.critical_error_id),
                source.created_at
            FROM attention_case_sources AS source
            WHERE source.critical_error_id IS NOT NULL
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            WITH ordered_events AS (
                SELECT
                    result.id AS result_id,
                    result.attempt_id,
                    result.pass_status,
                    result.completed_at,
                    attempt.organization_id,
                    attempt.location_id,
                    attempt.training_id,
                    attempt.employee_profile_id,
                    attempt.assignment_id,
                    assessment.id AS target_assessment_id,
                    count(*) FILTER (WHERE result.pass_status = 'passed') OVER (
                        PARTITION BY
                            attempt.employee_profile_id,
                            attempt.training_id,
                            assessment.id
                        ORDER BY result.completed_at, result.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS cycle_number
                FROM attempt_results AS result
                JOIN assessment_attempts AS attempt
                  ON attempt.id = result.attempt_id
                JOIN assessment_versions AS assessment_version
                  ON assessment_version.id = attempt.assessment_version_id
                JOIN assessments AS assessment
                  ON assessment.id = assessment_version.assessment_id
                WHERE attempt.status = 'completed'
                  AND attempt.question_count = 20
                  AND result.total_count = 20
                  AND assessment.assessment_type = 'menu_final_exam'
                  AND result.pass_status IN ('passed', 'failed')
            ),
            first_failures AS (
                SELECT DISTINCT ON (
                    employee_profile_id,
                    training_id,
                    target_assessment_id,
                    cycle_number
                )
                    *
                FROM ordered_events
                WHERE pass_status = 'failed'
                ORDER BY
                    employee_profile_id,
                    training_id,
                    target_assessment_id,
                    cycle_number,
                    completed_at,
                    result_id
            ),
            cycles AS (
                SELECT
                    failure.*,
                    qualifying.attempt_id AS completion_attempt_id,
                    qualifying.completed_at AS completion_at
                FROM first_failures AS failure
                LEFT JOIN LATERAL (
                    SELECT event.attempt_id, event.completed_at
                    FROM ordered_events AS event
                    WHERE event.employee_profile_id = failure.employee_profile_id
                      AND event.training_id = failure.training_id
                      AND event.target_assessment_id = failure.target_assessment_id
                      AND event.cycle_number = failure.cycle_number
                      AND event.pass_status = 'passed'
                      AND (
                          event.completed_at > failure.completed_at
                          OR (
                              event.completed_at = failure.completed_at
                              AND event.result_id > failure.result_id
                          )
                      )
                    ORDER BY event.completed_at, event.result_id
                    LIMIT 1
                ) AS qualifying ON TRUE
            )
            INSERT INTO retake_requirements (
                id,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                assignment_id,
                target_assessment_id,
                reason,
                state,
                source_result_id,
                source_attempt_id,
                target_policy,
                confirmed_at,
                due_at,
                clock_frozen_at,
                frozen_seconds,
                completed_at,
                completion_attempt_id,
                revision,
                created_at,
                updated_at
            )
            SELECT
                md5(
                    'failed-requirement:'
                    || cycles.employee_profile_id::text || ':'
                    || cycles.training_id::text || ':'
                    || cycles.target_assessment_id::text || ':'
                    || cycles.result_id::text
                )::uuid,
                cycles.organization_id,
                cycles.location_id,
                cycles.training_id,
                cycles.employee_profile_id,
                cycles.assignment_id,
                cycles.target_assessment_id,
                'failed_exam',
                CASE
                    WHEN completion_attempt_id IS NULL THEN 'active'
                    ELSE 'completed'
                END,
                cycles.result_id,
                cycles.attempt_id,
                jsonb_build_object(
                    'assessment_type', 'menu_final_exam',
                    'minimum_result', 'passed'
                ),
                cycles.completed_at,
                cycles.completed_at + interval '7 days',
                CASE
                    WHEN completion_attempt_id IS NULL
                     AND (
                        membership.status = 'disabled'
                        OR membership.training_participation_status = 'paused'
                     )
                    THEN transaction_timestamp()
                    ELSE NULL
                END,
                0,
                cycles.completion_at,
                cycles.completion_attempt_id,
                0,
                cycles.completed_at,
                coalesce(cycles.completion_at, cycles.completed_at)
            FROM cycles
            JOIN employee_profiles AS employee
              ON employee.id = cycles.employee_profile_id
             AND employee.organization_id = cycles.organization_id
            JOIN organization_memberships AS membership
              ON membership.id = employee.membership_id
             AND membership.organization_id = employee.organization_id
            ON CONFLICT DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            WITH ordered_events AS (
                SELECT
                    result.id AS result_id,
                    result.attempt_id,
                    result.pass_status,
                    result.completed_at,
                    attempt.organization_id,
                    attempt.location_id,
                    attempt.training_id,
                    attempt.employee_profile_id,
                    assessment.id AS target_assessment_id,
                    count(*) FILTER (WHERE result.pass_status = 'passed') OVER (
                        PARTITION BY
                            attempt.employee_profile_id,
                            attempt.training_id,
                            assessment.id
                        ORDER BY result.completed_at, result.id
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) AS cycle_number
                FROM attempt_results AS result
                JOIN assessment_attempts AS attempt
                  ON attempt.id = result.attempt_id
                JOIN assessment_versions AS assessment_version
                  ON assessment_version.id = attempt.assessment_version_id
                JOIN assessments AS assessment
                  ON assessment.id = assessment_version.assessment_id
                WHERE attempt.status = 'completed'
                  AND attempt.question_count = 20
                  AND result.total_count = 20
                  AND assessment.assessment_type = 'menu_final_exam'
                  AND result.pass_status IN ('passed', 'failed')
            ),
            requirement_cycles AS (
                SELECT
                    requirement.id AS requirement_id,
                    requirement.organization_id,
                    requirement.location_id,
                    requirement.employee_profile_id,
                    requirement.training_id,
                    requirement.target_assessment_id,
                    source_event.cycle_number
                FROM retake_requirements AS requirement
                JOIN ordered_events AS source_event
                  ON source_event.result_id = requirement.source_result_id
                WHERE requirement.reason = 'failed_exam'
            )
            INSERT INTO retake_requirement_actions (
                id,
                organization_id,
                location_id,
                retake_requirement_id,
                actor_type,
                action,
                attempt_id,
                details,
                created_at
            )
            SELECT
                md5(
                    'retake-attempt-observed:'
                    || cycle.requirement_id::text || ':'
                    || event.result_id::text
                )::uuid,
                cycle.organization_id,
                cycle.location_id,
                cycle.requirement_id,
                'system',
                'attempt_observed',
                event.attempt_id,
                jsonb_build_object('pass_status', event.pass_status),
                event.completed_at
            FROM requirement_cycles AS cycle
            JOIN ordered_events AS event
              ON event.employee_profile_id = cycle.employee_profile_id
             AND event.training_id = cycle.training_id
             AND event.target_assessment_id = cycle.target_assessment_id
             AND event.cycle_number = cycle.cycle_number
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO retake_requirement_actions (
                id,
                organization_id,
                location_id,
                retake_requirement_id,
                actor_type,
                action,
                attempt_id,
                details,
                created_at
            )
            SELECT
                md5('retake-confirmed:' || requirement.id::text)::uuid,
                requirement.organization_id,
                requirement.location_id,
                requirement.id,
                'system',
                'confirmed',
                requirement.source_attempt_id,
                '{}'::jsonb,
                requirement.confirmed_at
            FROM retake_requirements AS requirement
            WHERE requirement.reason = 'failed_exam'
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO retake_requirement_actions (
                id,
                organization_id,
                location_id,
                retake_requirement_id,
                actor_type,
                action,
                attempt_id,
                details,
                created_at
            )
            SELECT
                md5('retake-completed:' || requirement.id::text)::uuid,
                requirement.organization_id,
                requirement.location_id,
                requirement.id,
                'system',
                'completed',
                requirement.completion_attempt_id,
                '{}'::jsonb,
                requirement.completed_at
            FROM retake_requirements AS requirement
            WHERE requirement.reason = 'failed_exam'
              AND requirement.state = 'completed'
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_cases (
                id,
                organization_id,
                location_id,
                training_id,
                employee_profile_id,
                case_type,
                subject_key,
                state,
                revision,
                created_at,
                updated_at
            )
            SELECT
                md5('retake-overdue-case:' || requirement.id::text)::uuid,
                requirement.organization_id,
                requirement.location_id,
                requirement.training_id,
                requirement.employee_profile_id,
                'retake_overdue',
                NULL,
                'open',
                0,
                requirement.due_at,
                requirement.due_at
            FROM retake_requirements AS requirement
            WHERE requirement.state = 'active'
              AND requirement.clock_frozen_at IS NULL
              AND requirement.due_at <= transaction_timestamp()
            ON CONFLICT DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_case_sources (
                id,
                organization_id,
                location_id,
                attention_case_id,
                retake_requirement_id,
                created_at
            )
            SELECT
                md5('attention-source-retake:' || requirement.id::text)::uuid,
                requirement.organization_id,
                requirement.location_id,
                case_row.id,
                requirement.id,
                requirement.due_at
            FROM retake_requirements AS requirement
            JOIN attention_cases AS case_row
              ON case_row.id =
                 md5('retake-overdue-case:' || requirement.id::text)::uuid
            ON CONFLICT DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO attention_case_actions (
                id,
                organization_id,
                location_id,
                attention_case_id,
                actor_type,
                action,
                from_state,
                to_state,
                details,
                created_at
            )
            SELECT
                md5('attention-opened:' || case_row.id::text)::uuid,
                case_row.organization_id,
                case_row.location_id,
                case_row.id,
                'system',
                'opened',
                NULL,
                'open',
                '{}'::jsonb,
                case_row.created_at
            FROM attention_cases AS case_row
            WHERE case_row.case_type = 'retake_overdue'
            ON CONFLICT (id) DO NOTHING
            """
        )
    )
    bind.execute(
        sa.text(
            """
            INSERT INTO retake_requirement_actions (
                id,
                organization_id,
                location_id,
                retake_requirement_id,
                actor_type,
                action,
                details,
                created_at
            )
            SELECT
                md5('retake-deadline-projected:' || requirement.id::text)::uuid,
                requirement.organization_id,
                requirement.location_id,
                requirement.id,
                'system',
                'deadline_projected',
                jsonb_build_object('timing_state', 'overdue'),
                requirement.due_at
            FROM retake_requirements AS requirement
            JOIN attention_case_sources AS source
              ON source.retake_requirement_id = requirement.id
            ON CONFLICT (id) DO NOTHING
            """
        )
    )


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_attempt_results_source_scope", "attempt_results", ["id", "attempt_id"]
    )
    op.create_unique_constraint(
        "uq_assessment_attempts_employee_training_scope",
        "assessment_attempts",
        [
            "id",
            "employee_profile_id",
            "organization_id",
            "location_id",
            "training_id",
        ],
    )
    op.create_unique_constraint(
        "uq_submitted_answers_source_scope",
        "submitted_answers",
        ["id", "attempt_id", "attempt_question_id"],
    )
    op.create_table(
        "attention_cases",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("case_type", sa.String(length=32), nullable=False),
        sa.Column("subject_key", sa.String(length=200), nullable=True),
        sa.Column("state", sa.String(length=16), server_default="open", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("acknowledged_by_user_id", sa.UUID(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_type", sa.String(length=32), nullable=True),
        sa.Column("resolution_actor_type", sa.String(length=16), nullable=True),
        sa.Column("resolved_by_user_id", sa.UUID(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_comment", sa.String(length=500), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(case_type = 'critical_allergen' AND subject_key IS NOT NULL) OR (case_type = 'retake_overdue' AND subject_key IS NULL)",
            name=op.f("ck_attention_cases_subject_matches_type"),
        ),
        sa.CheckConstraint(
            "(state = 'open' AND acknowledged_at IS NULL AND resolved_at IS NULL AND resolution_type IS NULL AND resolution_actor_type IS NULL AND resolved_by_user_id IS NULL AND resolution_comment IS NULL) OR (state = 'acknowledged' AND acknowledged_at IS NOT NULL AND acknowledged_by_user_id IS NOT NULL AND resolved_at IS NULL AND resolution_type IS NULL AND resolution_actor_type IS NULL AND resolved_by_user_id IS NULL AND resolution_comment IS NULL) OR (state = 'resolved' AND resolved_at IS NOT NULL AND resolution_type IS NOT NULL AND resolution_actor_type IN ('user', 'system') AND ((resolution_actor_type = 'user' AND resolved_by_user_id IS NOT NULL) OR (resolution_actor_type = 'system' AND resolved_by_user_id IS NULL)))",
            name=op.f("ck_attention_cases_lifecycle_fields_match"),
        ),
        sa.CheckConstraint(
            "case_type IN ('critical_allergen', 'retake_overdue')",
            name=op.f("ck_attention_cases_type_allowed"),
        ),
        sa.CheckConstraint(
            "resolution_type IS NULL OR resolution_type IN ('clean_retake', 'admin_follow_up', 'requirement_completed', 'requirement_cancelled')",
            name=op.f("ck_attention_cases_resolution_type_allowed"),
        ),
        sa.CheckConstraint(
            "state IN ('open', 'acknowledged', 'resolved')",
            name=op.f("ck_attention_cases_state_allowed"),
        ),
        sa.CheckConstraint(
            "resolution_comment IS NULL OR length(btrim(resolution_comment)) BETWEEN 1 AND 500",
            name=op.f("ck_attention_cases_resolution_comment_length"),
        ),
        sa.CheckConstraint("revision >= 0", name=op.f("ck_attention_cases_revision_nonnegative")),
        sa.CheckConstraint(
            "subject_key IS NULL OR length(btrim(subject_key)) BETWEEN 1 AND 200",
            name=op.f("ck_attention_cases_subject_key_length"),
        ),
        sa.ForeignKeyConstraint(
            ["acknowledged_by_user_id"],
            ["users.id"],
            name=op.f("fk_attention_cases_acknowledged_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_attention_cases_employee_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_id", "organization_id", "location_id"],
            ["trainings.id", "trainings.organization_id", "trainings.location_id"],
            name="fk_attention_cases_training_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"],
            ["users.id"],
            name=op.f("fk_attention_cases_resolved_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attention_cases")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_attention_cases_scope"
        ),
    )
    op.create_index(
        "ix_attention_cases_admin_queue",
        "attention_cases",
        ["organization_id", "state", "case_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "uq_attention_cases_unresolved_critical",
        "attention_cases",
        ["organization_id", "employee_profile_id", "training_id", "case_type", "subject_key"],
        unique=True,
        postgresql_where=sa.text(
            "case_type = 'critical_allergen' AND state IN ('open', 'acknowledged')"
        ),
    )
    op.create_table(
        "attention_case_actions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("attention_case_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("from_state", sa.String(length=16), nullable=True),
        sa.Column("to_state", sa.String(length=16), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "action IN ('opened', 'source_added', 'acknowledged', 'requirement_linked', 'resolved')",
            name=op.f("ck_attention_case_actions_action_allowed"),
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system') AND ((actor_type = 'user' AND actor_user_id IS NOT NULL) OR (actor_type = 'system' AND actor_user_id IS NULL))",
            name=op.f("ck_attention_case_actions_actor_matches_type"),
        ),
        sa.CheckConstraint(
            "from_state IS NULL OR from_state IN ('open', 'acknowledged', 'resolved')",
            name=op.f("ck_attention_case_actions_from_state_allowed"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name=op.f("ck_attention_case_actions_details_object"),
        ),
        sa.CheckConstraint(
            "to_state IS NULL OR to_state IN ('open', 'acknowledged', 'resolved')",
            name=op.f("ck_attention_case_actions_to_state_allowed"),
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) BETWEEN 1 AND 500",
            name=op.f("ck_attention_case_actions_comment_length"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_attention_case_actions_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_attention_case_actions_case_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attention_case_actions")),
    )
    op.create_index(
        "ix_attention_case_actions_history",
        "attention_case_actions",
        ["attention_case_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "retake_requirements",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("target_assessment_id", sa.UUID(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("state", sa.String(length=16), nullable=False),
        sa.Column("source_result_id", sa.UUID(), nullable=True),
        sa.Column("source_attempt_id", sa.UUID(), nullable=True),
        sa.Column("source_attention_case_id", sa.UUID(), nullable=True),
        sa.Column("management_source_key", sa.String(length=200), nullable=True),
        sa.Column("target_policy", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proposed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_by_user_id", sa.UUID(), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("clock_frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frozen_seconds", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_attempt_id", sa.UUID(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_by_user_id", sa.UUID(), nullable=True),
        sa.Column("cancellation_comment", sa.String(length=500), nullable=True),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(reason = 'failed_exam' AND source_result_id IS NOT NULL AND source_attempt_id IS NOT NULL AND source_attention_case_id IS NULL AND management_source_key IS NULL) OR (reason = 'critical_error' AND source_result_id IS NULL AND source_attempt_id IS NULL AND source_attention_case_id IS NOT NULL AND management_source_key IS NULL) OR (reason IN ('management_follow_up', 'material_content_change') AND source_result_id IS NULL AND source_attempt_id IS NULL AND source_attention_case_id IS NULL AND length(btrim(management_source_key)) BETWEEN 1 AND 200)",
            name=op.f("ck_retake_requirements_source_matches_reason"),
        ),
        sa.CheckConstraint(
            "(state = 'completed' AND completed_at IS NOT NULL AND completion_attempt_id IS NOT NULL AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_comment IS NULL) OR (state = 'cancelled' AND completed_at IS NULL AND completion_attempt_id IS NULL AND cancelled_at IS NOT NULL AND cancelled_by_user_id IS NOT NULL AND length(btrim(cancellation_comment)) BETWEEN 1 AND 500) OR (state IN ('proposed', 'active') AND completed_at IS NULL AND completion_attempt_id IS NULL AND cancelled_at IS NULL AND cancelled_by_user_id IS NULL AND cancellation_comment IS NULL)",
            name=op.f("ck_retake_requirements_terminal_state_match"),
        ),
        sa.CheckConstraint(
            "(state = 'proposed' AND proposed_at IS NOT NULL AND proposed_by_user_id IS NOT NULL AND confirmed_at IS NULL) OR (state IN ('active', 'completed') AND confirmed_at IS NOT NULL) OR (state = 'cancelled')",
            name=op.f("ck_retake_requirements_activation_fields_match"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(target_policy) = 'object'",
            name=op.f("ck_retake_requirements_target_policy_object"),
        ),
        sa.CheckConstraint(
            "reason IN ('failed_exam', 'critical_error', 'management_follow_up', 'material_content_change')",
            name=op.f("ck_retake_requirements_reason_allowed"),
        ),
        sa.CheckConstraint(
            "state IN ('proposed', 'active', 'completed', 'cancelled')",
            name=op.f("ck_retake_requirements_state_allowed"),
        ),
        sa.CheckConstraint(
            "frozen_seconds >= 0", name=op.f("ck_retake_requirements_frozen_seconds_nonnegative")
        ),
        sa.CheckConstraint(
            "revision >= 0", name=op.f("ck_retake_requirements_revision_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["assignment_id", "organization_id", "location_id", "training_id"],
            [
                "training_assignments.id",
                "training_assignments.organization_id",
                "training_assignments.location_id",
                "training_assignments.training_id",
            ],
            name="fk_retake_requirements_assignment_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["cancelled_by_user_id"],
            ["users.id"],
            name=op.f("fk_retake_requirements_cancelled_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "completion_attempt_id",
                "employee_profile_id",
                "organization_id",
                "location_id",
                "training_id",
            ],
            [
                "assessment_attempts.id",
                "assessment_attempts.employee_profile_id",
                "assessment_attempts.organization_id",
                "assessment_attempts.location_id",
                "assessment_attempts.training_id",
            ],
            name="fk_retake_requirements_completion_attempt",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["confirmed_by_user_id"],
            ["users.id"],
            name=op.f("fk_retake_requirements_confirmed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_retake_requirements_employee_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["proposed_by_user_id"],
            ["users.id"],
            name=op.f("fk_retake_requirements_proposed_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_retake_requirements_attention_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_result_id", "source_attempt_id"],
            ["attempt_results.id", "attempt_results.attempt_id"],
            name="fk_retake_requirements_source_result",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "source_attempt_id",
                "employee_profile_id",
                "assignment_id",
                "organization_id",
                "location_id",
                "training_id",
            ],
            [
                "assessment_attempts.id",
                "assessment_attempts.employee_profile_id",
                "assessment_attempts.assignment_id",
                "assessment_attempts.organization_id",
                "assessment_attempts.location_id",
                "assessment_attempts.training_id",
            ],
            name="fk_retake_requirements_source_attempt_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["target_assessment_id", "organization_id", "location_id", "training_id"],
            [
                "assessments.id",
                "assessments.organization_id",
                "assessments.location_id",
                "assessments.training_id",
            ],
            name="fk_retake_requirements_target_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retake_requirements")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_retake_requirements_scope"
        ),
    )
    op.create_index(
        "ix_retake_requirements_admin_due",
        "retake_requirements",
        ["organization_id", "state", "due_at"],
        unique=False,
    )
    op.create_index(
        "ix_retake_requirements_employee_current",
        "retake_requirements",
        ["employee_profile_id", "state", "due_at"],
        unique=False,
    )
    op.create_index(
        "uq_retake_requirements_critical_current",
        "retake_requirements",
        ["source_attention_case_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'critical_error' AND state IN ('proposed', 'active')"),
    )
    op.create_index(
        "uq_retake_requirements_failed_current",
        "retake_requirements",
        ["employee_profile_id", "training_id", "target_assessment_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'failed_exam' AND state IN ('proposed', 'active')"),
    )
    op.create_index(
        "uq_retake_requirements_failed_source",
        "retake_requirements",
        ["source_result_id"],
        unique=True,
        postgresql_where=sa.text("reason = 'failed_exam'"),
    )
    op.create_index(
        "uq_retake_requirements_management_current",
        "retake_requirements",
        ["employee_profile_id", "target_assessment_id", "management_source_key"],
        unique=True,
        postgresql_where=sa.text(
            "reason = 'management_follow_up' AND state IN ('proposed', 'active')"
        ),
    )
    op.create_table(
        "critical_errors",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_id", sa.UUID(), nullable=False),
        sa.Column("employee_profile_id", sa.UUID(), nullable=False),
        sa.Column("assignment_id", sa.UUID(), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=False),
        sa.Column("attempt_question_id", sa.UUID(), nullable=False),
        sa.Column("submitted_answer_id", sa.UUID(), nullable=False),
        sa.Column("menu_id", sa.UUID(), nullable=False),
        sa.Column("menu_item_id", sa.UUID(), nullable=False),
        sa.Column("allergen_id", sa.UUID(), nullable=False),
        sa.Column("critical_type", sa.String(length=32), nullable=False),
        sa.Column("subject_key", sa.String(length=200), nullable=False),
        sa.Column("safe_context", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "critical_type = 'allergen'", name=op.f("ck_critical_errors_critical_type_allergen")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(safe_context) = 'object'",
            name=op.f("ck_critical_errors_safe_context_object"),
        ),
        sa.CheckConstraint(
            "length(btrim(subject_key)) BETWEEN 1 AND 200",
            name=op.f("ck_critical_errors_subject_key_length"),
        ),
        sa.ForeignKeyConstraint(
            ["allergen_id"],
            ["allergens.id"],
            name=op.f("fk_critical_errors_allergen_id_allergens"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            [
                "attempt_id",
                "employee_profile_id",
                "assignment_id",
                "organization_id",
                "location_id",
                "training_id",
            ],
            [
                "assessment_attempts.id",
                "assessment_attempts.employee_profile_id",
                "assessment_attempts.assignment_id",
                "assessment_attempts.organization_id",
                "assessment_attempts.location_id",
                "assessment_attempts.training_id",
            ],
            name="fk_critical_errors_attempt_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_question_id", "attempt_id"],
            ["attempt_questions.id", "attempt_questions.attempt_id"],
            name="fk_critical_errors_question_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            name="fk_critical_errors_employee_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id", "menu_id", "organization_id", "location_id"],
            [
                "menu_items.id",
                "menu_items.menu_id",
                "menu_items.organization_id",
                "menu_items.location_id",
            ],
            name="fk_critical_errors_menu_item_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_answer_id", "attempt_id", "attempt_question_id"],
            [
                "submitted_answers.id",
                "submitted_answers.attempt_id",
                "submitted_answers.attempt_question_id",
            ],
            name="fk_critical_errors_answer_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_critical_errors")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_critical_errors_scope"
        ),
        sa.UniqueConstraint("submitted_answer_id", name="uq_critical_errors_source_answer"),
    )
    op.create_index(
        "ix_critical_errors_employee_subject",
        "critical_errors",
        ["organization_id", "employee_profile_id", "training_id", "subject_key", "occurred_at"],
        unique=False,
    )
    op.create_table(
        "retake_requirement_actions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("retake_requirement_id", sa.UUID(), nullable=False),
        sa.Column("actor_type", sa.String(length=16), nullable=False),
        sa.Column("actor_user_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("attempt_id", sa.UUID(), nullable=True),
        sa.Column("comment", sa.String(length=500), nullable=True),
        sa.Column(
            "details",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "action IN ('proposed', 'confirmed', 'attempt_observed', 'frozen', 'resumed', 'completed', 'cancelled', 'deadline_projected')",
            name=op.f("ck_retake_requirement_actions_action_allowed"),
        ),
        sa.CheckConstraint(
            "actor_type IN ('user', 'system') AND ((actor_type = 'user' AND actor_user_id IS NOT NULL) OR (actor_type = 'system' AND actor_user_id IS NULL))",
            name=op.f("ck_retake_requirement_actions_actor_matches_type"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(details) = 'object'",
            name=op.f("ck_retake_requirement_actions_details_object"),
        ),
        sa.CheckConstraint(
            "comment IS NULL OR length(btrim(comment)) BETWEEN 1 AND 500",
            name=op.f("ck_retake_requirement_actions_comment_length"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_retake_requirement_actions_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["attempt_id"],
            ["assessment_attempts.id"],
            name=op.f("fk_retake_requirement_actions_attempt_id_assessment_attempts"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retake_requirement_id", "organization_id", "location_id"],
            [
                "retake_requirements.id",
                "retake_requirements.organization_id",
                "retake_requirements.location_id",
            ],
            name="fk_retake_requirement_actions_requirement_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_retake_requirement_actions")),
    )
    op.create_index(
        "ix_retake_requirement_actions_history",
        "retake_requirement_actions",
        ["retake_requirement_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "attention_case_sources",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("attention_case_id", sa.UUID(), nullable=False),
        sa.Column("critical_error_id", sa.UUID(), nullable=True),
        sa.Column("retake_requirement_id", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint(
            "num_nonnulls(critical_error_id, retake_requirement_id) = 1",
            name=op.f("ck_attention_case_sources_exactly_one_source"),
        ),
        sa.ForeignKeyConstraint(
            ["attention_case_id", "organization_id", "location_id"],
            [
                "attention_cases.id",
                "attention_cases.organization_id",
                "attention_cases.location_id",
            ],
            name="fk_attention_case_sources_case_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["critical_error_id", "organization_id", "location_id"],
            [
                "critical_errors.id",
                "critical_errors.organization_id",
                "critical_errors.location_id",
            ],
            name="fk_attention_case_sources_critical_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["retake_requirement_id", "organization_id", "location_id"],
            [
                "retake_requirements.id",
                "retake_requirements.organization_id",
                "retake_requirements.location_id",
            ],
            name="fk_attention_case_sources_requirement_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_attention_case_sources")),
    )
    op.create_index(
        "uq_attention_case_sources_critical_error",
        "attention_case_sources",
        ["critical_error_id"],
        unique=True,
        postgresql_where=sa.text("critical_error_id IS NOT NULL"),
    )
    op.create_index(
        "uq_attention_case_sources_retake_requirement",
        "attention_case_sources",
        ["retake_requirement_id"],
        unique=True,
        postgresql_where=sa.text("retake_requirement_id IS NOT NULL"),
    )
    _project_historical_follow_up()


def downgrade() -> None:
    op.drop_index(
        "uq_attention_case_sources_retake_requirement",
        table_name="attention_case_sources",
        postgresql_where=sa.text("retake_requirement_id IS NOT NULL"),
    )
    op.drop_index(
        "uq_attention_case_sources_critical_error",
        table_name="attention_case_sources",
        postgresql_where=sa.text("critical_error_id IS NOT NULL"),
    )
    op.drop_table("attention_case_sources")
    op.drop_index("ix_retake_requirement_actions_history", table_name="retake_requirement_actions")
    op.drop_table("retake_requirement_actions")
    op.drop_index("ix_critical_errors_employee_subject", table_name="critical_errors")
    op.drop_table("critical_errors")
    op.drop_index(
        "uq_retake_requirements_management_current",
        table_name="retake_requirements",
        postgresql_where=sa.text(
            "reason = 'management_follow_up' AND state IN ('proposed', 'active')"
        ),
    )
    op.drop_index(
        "uq_retake_requirements_failed_source",
        table_name="retake_requirements",
        postgresql_where=sa.text("reason = 'failed_exam'"),
        if_exists=True,
    )
    op.drop_index(
        "uq_retake_requirements_failed_current",
        table_name="retake_requirements",
        postgresql_where=sa.text("reason = 'failed_exam' AND state IN ('proposed', 'active')"),
    )
    op.drop_index(
        "uq_retake_requirements_critical_current",
        table_name="retake_requirements",
        postgresql_where=sa.text("reason = 'critical_error' AND state IN ('proposed', 'active')"),
    )
    op.drop_index("ix_retake_requirements_employee_current", table_name="retake_requirements")
    op.drop_index("ix_retake_requirements_admin_due", table_name="retake_requirements")
    op.drop_table("retake_requirements")
    op.drop_index("ix_attention_case_actions_history", table_name="attention_case_actions")
    op.drop_table("attention_case_actions")
    op.drop_index(
        "uq_attention_cases_unresolved_critical",
        table_name="attention_cases",
        postgresql_where=sa.text(
            "case_type = 'critical_allergen' AND state IN ('open', 'acknowledged')"
        ),
    )
    op.drop_index("ix_attention_cases_admin_queue", table_name="attention_cases")
    op.drop_table("attention_cases")
    op.drop_constraint("uq_submitted_answers_source_scope", "submitted_answers", type_="unique")
    op.execute(
        "ALTER TABLE assessment_attempts "
        "DROP CONSTRAINT IF EXISTS uq_assessment_attempts_employee_training_scope"
    )
    op.drop_constraint("uq_attempt_results_source_scope", "attempt_results", type_="unique")
