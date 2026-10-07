"""Версії стандартів зберігають перевірене походження навчальних питань."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0024_standard_sources"
down_revision: str | None = "0023_course_assessment_type"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "standard_sets",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
        sa.Column("domain_type", sa.String(length=32), nullable=False),
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
            "domain_type IN ('service', 'sales', 'venue_standards')",
            name=op.f("ck_standard_sets_domain_allowed"),
        ),
        sa.CheckConstraint(
            "length(btrim(code)) BETWEEN 1 AND 100", name=op.f("ck_standard_sets_code_length")
        ),
        sa.ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_standard_sets_location_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_standard_sets")),
        sa.UniqueConstraint("id", "organization_id", "location_id", name="uq_standard_sets_scope"),
        sa.UniqueConstraint("location_id", "code", name="uq_standard_sets_code"),
    )
    op.create_table(
        "standard_rules",
        sa.Column("standard_set_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False),
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
            "length(btrim(code)) BETWEEN 1 AND 100", name=op.f("ck_standard_rules_code_length")
        ),
        sa.ForeignKeyConstraint(
            ["standard_set_id"],
            ["standard_sets.id"],
            name=op.f("fk_standard_rules_standard_set_id_standard_sets"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_standard_rules")),
        sa.UniqueConstraint("id", "standard_set_id", name="uq_standard_rules_set"),
        sa.UniqueConstraint("standard_set_id", "code", name="uq_standard_rules_code"),
    )
    op.create_table(
        "standard_set_versions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("standard_set_id", sa.UUID(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("title_uk", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by_user_id", sa.UUID(), nullable=True),
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
            "(status = 'draft' AND published_at IS NULL AND published_by_user_id IS NULL) OR "
            "(status IN ('published', 'archived') AND published_at IS NOT NULL "
            "AND published_by_user_id IS NOT NULL)",
            name=op.f("ck_standard_set_versions_publication_matches_status"),
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'published', 'archived')",
            name=op.f("ck_standard_set_versions_status_allowed"),
        ),
        sa.CheckConstraint(
            "length(btrim(title_uk)) BETWEEN 1 AND 200",
            name=op.f("ck_standard_set_versions_title_length"),
        ),
        sa.CheckConstraint(
            "version_number >= 1", name=op.f("ck_standard_set_versions_version_positive")
        ),
        sa.ForeignKeyConstraint(
            ["published_by_user_id"],
            ["users.id"],
            name=op.f("fk_standard_set_versions_published_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["standard_set_id", "organization_id", "location_id"],
            ["standard_sets.id", "standard_sets.organization_id", "standard_sets.location_id"],
            name="fk_standard_set_versions_set_scope",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_standard_set_versions")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_standard_set_versions_scope"
        ),
        sa.UniqueConstraint("id", "standard_set_id", name="uq_standard_set_versions_set"),
        sa.UniqueConstraint(
            "standard_set_id", "version_number", name="uq_standard_set_versions_number"
        ),
    )
    op.create_table(
        "standard_rule_versions",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("standard_set_id", sa.UUID(), nullable=False),
        sa.Column("standard_set_version_id", sa.UUID(), nullable=False),
        sa.Column("standard_rule_id", sa.UUID(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("scenario_uk", sa.Text(), nullable=True),
        sa.Column("allowed_action_uk", sa.Text(), nullable=True),
        sa.Column("prohibited_actions_uk", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("conditions_uk", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action_order_uk", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation_uk", sa.Text(), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("verified", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_critical", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
            "jsonb_typeof(action_order_uk) = 'array'",
            name=op.f("ck_standard_rule_versions_order_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(conditions_uk) = 'array'",
            name=op.f("ck_standard_rule_versions_conditions_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(prohibited_actions_uk) = 'array'",
            name=op.f("ck_standard_rule_versions_prohibited_array"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(provenance) = 'object'",
            name=op.f("ck_standard_rule_versions_provenance_object"),
        ),
        sa.CheckConstraint(
            "position >= 0", name=op.f("ck_standard_rule_versions_position_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["standard_rule_id", "standard_set_id"],
            ["standard_rules.id", "standard_rules.standard_set_id"],
            name="fk_standard_rule_versions_rule_set",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["standard_set_version_id", "organization_id", "location_id"],
            [
                "standard_set_versions.id",
                "standard_set_versions.organization_id",
                "standard_set_versions.location_id",
            ],
            name="fk_standard_rule_versions_version_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["standard_set_version_id", "standard_set_id"],
            ["standard_set_versions.id", "standard_set_versions.standard_set_id"],
            name="fk_standard_rule_versions_version_set",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_standard_rule_versions")),
        sa.UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_standard_rule_versions_scope"
        ),
        sa.UniqueConstraint(
            "standard_set_version_id", "position", name="uq_standard_rule_versions_position"
        ),
        sa.UniqueConstraint(
            "standard_set_version_id", "standard_rule_id", name="uq_standard_rule_versions_rule"
        ),
    )
    op.create_table(
        "training_module_standard_dependencies",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("location_id", sa.UUID(), nullable=False),
        sa.Column("training_version_id", sa.UUID(), nullable=False),
        sa.Column("training_module_version_id", sa.UUID(), nullable=False),
        sa.Column("standard_set_version_id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(
            ["standard_set_version_id", "organization_id", "location_id"],
            [
                "standard_set_versions.id",
                "standard_set_versions.organization_id",
                "standard_set_versions.location_id",
            ],
            name="fk_module_standard_dependency_standard",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_module_version_id", "training_version_id"],
            ["training_module_versions.id", "training_module_versions.training_version_id"],
            name="fk_module_standard_dependency_module",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_module_standard_dependency_training",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_training_module_standard_dependencies")),
        sa.UniqueConstraint("training_module_version_id", name="uq_module_standard_dependency"),
    )
    op.add_column("question_source_links", sa.Column("standard_rule_version_id", sa.UUID()))
    op.create_foreign_key(
        "fk_question_source_links_standard_scope",
        "question_source_links",
        "standard_rule_versions",
        ["standard_rule_version_id", "organization_id", "location_id"],
        ["id", "organization_id", "location_id"],
        ondelete="RESTRICT",
    )
    op.drop_constraint(op.f("ck_question_source_links_exactly_one_source"), "question_source_links")
    op.create_check_constraint(
        "exactly_one_source",
        "question_source_links",
        "num_nonnulls(menu_item_version_id, menu_item_version_component_id, "
        "menu_item_version_allergen_id, standard_rule_version_id) = 1",
    )
    op.drop_constraint(
        op.f("ck_question_generation_rules_domain_type_menu"), "question_generation_rules"
    )
    op.create_check_constraint(
        "domain_type_menu",
        "question_generation_rules",
        "domain_type IN ('menu', 'service', 'sales', 'venue_standards')",
    )
    op.execute("""
    CREATE FUNCTION protect_standard_rule_version() RETURNS trigger LANGUAGE plpgsql AS $$
    DECLARE source_status text;
    BEGIN
      IF TG_OP <> 'INSERT' THEN
        SELECT status INTO source_status FROM standard_set_versions
          WHERE id=OLD.standard_set_version_id FOR UPDATE;
        IF source_status <> 'draft' THEN
          RAISE EXCEPTION 'Published standard rules are immutable' USING ERRCODE='23514';
        END IF;
      END IF;
      IF TG_OP <> 'DELETE' THEN
        SELECT status INTO source_status FROM standard_set_versions
          WHERE id=NEW.standard_set_version_id FOR UPDATE;
        IF source_status <> 'draft' THEN
          RAISE EXCEPTION 'Published standard rules are immutable' USING ERRCODE='23514';
        END IF;
        RETURN NEW;
      END IF;
      RETURN OLD;
    END $$;
    """)
    op.execute("""
    CREATE TRIGGER standard_rule_version_immutable
      BEFORE INSERT OR UPDATE OR DELETE ON standard_rule_versions
      FOR EACH ROW EXECUTE FUNCTION protect_standard_rule_version();
    """)
    op.execute("""
    CREATE FUNCTION protect_standard_set_version() RETURNS trigger LANGUAGE plpgsql AS $$
    BEGIN
      IF OLD.status <> 'draft' THEN
        IF TG_OP = 'DELETE' THEN
          RAISE EXCEPTION 'Published standard versions are immutable' USING ERRCODE='23514';
        END IF;
        IF NEW.status = 'draft' OR (OLD.status = 'archived' AND NEW.status <> 'archived')
          OR (to_jsonb(NEW) - 'status' - 'updated_at') <>
             (to_jsonb(OLD) - 'status' - 'updated_at') THEN
          RAISE EXCEPTION 'Published standard versions are immutable' USING ERRCODE='23514';
        END IF;
      END IF;
      IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
      RETURN NEW;
    END $$;
    """)
    op.execute("""
    CREATE TRIGGER standard_set_version_immutable BEFORE UPDATE OR DELETE ON standard_set_versions
      FOR EACH ROW EXECUTE FUNCTION protect_standard_set_version();
    """)


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT EXISTS (SELECT 1 FROM standard_sets)")):
        raise RuntimeError("Downgrade would discard standard sources")
    op.drop_constraint("fk_question_source_links_standard_scope", "question_source_links")
    op.drop_constraint(op.f("ck_question_source_links_exactly_one_source"), "question_source_links")
    op.create_check_constraint(
        "exactly_one_source",
        "question_source_links",
        "num_nonnulls(menu_item_version_id, menu_item_version_component_id, "
        "menu_item_version_allergen_id) = 1",
    )
    op.drop_column("question_source_links", "standard_rule_version_id")
    op.drop_constraint(
        op.f("ck_question_generation_rules_domain_type_menu"), "question_generation_rules"
    )
    op.create_check_constraint(
        "domain_type_menu", "question_generation_rules", "domain_type = 'menu'"
    )
    op.execute("DROP TRIGGER standard_rule_version_immutable ON standard_rule_versions")
    op.execute("DROP TRIGGER standard_set_version_immutable ON standard_set_versions")
    op.execute("DROP FUNCTION protect_standard_rule_version()")
    op.execute("DROP FUNCTION protect_standard_set_version()")
    op.drop_table("training_module_standard_dependencies")
    op.drop_table("standard_rule_versions")
    op.drop_table("standard_set_versions")
    op.drop_table("standard_rules")
    op.drop_table("standard_sets")
