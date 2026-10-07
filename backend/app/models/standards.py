from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class StandardSet(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standard_sets"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", "location_id", name="uq_standard_sets_scope"),
        UniqueConstraint("location_id", "code", name="uq_standard_sets_code"),
        CheckConstraint(
            "domain_type IN ('service', 'sales', 'venue_standards')", name="domain_allowed"
        ),
        CheckConstraint("length(btrim(code)) BETWEEN 1 AND 100", name="code_length"),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_standard_sets_location_scope",
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    code: Mapped[str] = mapped_column(String(100), nullable=False)
    domain_type: Mapped[str] = mapped_column(String(32), nullable=False)


class StandardSetVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standard_set_versions"
    __table_args__ = (
        UniqueConstraint(
            "standard_set_id", "version_number", name="uq_standard_set_versions_number"
        ),
        UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_standard_set_versions_scope"
        ),
        UniqueConstraint("id", "standard_set_id", name="uq_standard_set_versions_set"),
        CheckConstraint("version_number >= 1", name="version_positive"),
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="status_allowed"),
        CheckConstraint("length(btrim(title_uk)) BETWEEN 1 AND 200", name="title_length"),
        CheckConstraint(
            "(status = 'draft' AND published_at IS NULL AND published_by_user_id IS NULL) OR "
            "(status IN ('published', 'archived') AND published_at IS NOT NULL "
            "AND published_by_user_id IS NOT NULL)",
            name="publication_matches_status",
        ),
        ForeignKeyConstraint(
            ["standard_set_id", "organization_id", "location_id"],
            ["standard_sets.id", "standard_sets.organization_id", "standard_sets.location_id"],
            name="fk_standard_set_versions_set_scope",
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    standard_set_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    title_uk: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default="draft"
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_by_user_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
    )


class StandardRule(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standard_rules"
    __table_args__ = (
        UniqueConstraint("id", "standard_set_id", name="uq_standard_rules_set"),
        UniqueConstraint("standard_set_id", "code", name="uq_standard_rules_code"),
        CheckConstraint("length(btrim(code)) BETWEEN 1 AND 100", name="code_length"),
    )
    standard_set_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("standard_sets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(String(100), nullable=False)


class StandardRuleVersion(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "standard_rule_versions"
    __table_args__ = (
        UniqueConstraint(
            "id", "organization_id", "location_id", name="uq_standard_rule_versions_scope"
        ),
        UniqueConstraint(
            "standard_set_version_id", "standard_rule_id", name="uq_standard_rule_versions_rule"
        ),
        UniqueConstraint(
            "standard_set_version_id", "position", name="uq_standard_rule_versions_position"
        ),
        ForeignKeyConstraint(
            ["standard_set_version_id", "organization_id", "location_id"],
            [
                "standard_set_versions.id",
                "standard_set_versions.organization_id",
                "standard_set_versions.location_id",
            ],
            name="fk_standard_rule_versions_version_scope",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["standard_set_version_id", "standard_set_id"],
            ["standard_set_versions.id", "standard_set_versions.standard_set_id"],
            name="fk_standard_rule_versions_version_set",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["standard_rule_id", "standard_set_id"],
            ["standard_rules.id", "standard_rules.standard_set_id"],
            name="fk_standard_rule_versions_rule_set",
            ondelete="RESTRICT",
        ),
        CheckConstraint("position >= 0", name="position_nonnegative"),
        CheckConstraint("jsonb_typeof(prohibited_actions_uk) = 'array'", name="prohibited_array"),
        CheckConstraint("jsonb_typeof(conditions_uk) = 'array'", name="conditions_array"),
        CheckConstraint("jsonb_typeof(action_order_uk) = 'array'", name="order_array"),
        CheckConstraint("jsonb_typeof(provenance) = 'object'", name="provenance_object"),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    standard_set_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    standard_set_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    standard_rule_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    scenario_uk: Mapped[str | None] = mapped_column(Text)
    allowed_action_uk: Mapped[str | None] = mapped_column(Text)
    prohibited_actions_uk: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    conditions_uk: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    action_order_uk: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    explanation_uk: Mapped[str | None] = mapped_column(Text)
    provenance: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict)
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    is_critical: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )


class TrainingModuleStandardDependency(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "training_module_standard_dependencies"
    __table_args__ = (
        UniqueConstraint("training_module_version_id", name="uq_module_standard_dependency"),
        ForeignKeyConstraint(
            ["training_module_version_id", "training_version_id"],
            ["training_module_versions.id", "training_module_versions.training_version_id"],
            name="fk_module_standard_dependency_module",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["training_version_id", "organization_id", "location_id"],
            [
                "training_versions.id",
                "training_versions.organization_id",
                "training_versions.location_id",
            ],
            name="fk_module_standard_dependency_training",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["standard_set_version_id", "organization_id", "location_id"],
            [
                "standard_set_versions.id",
                "standard_set_versions.organization_id",
                "standard_set_versions.location_id",
            ],
            name="fk_module_standard_dependency_standard",
            ondelete="RESTRICT",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    location_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    training_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), nullable=False)
    training_module_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    standard_set_version_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
