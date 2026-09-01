from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    and_,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.core.email import normalize_email
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.models.enums import (
    LifecycleStatus,
    Locale,
    MembershipStatus,
    TrainingParticipationStatus,
)

if TYPE_CHECKING:
    from app.models.audit import AuditEvent
    from app.models.auth import (
        AdminAccess,
        MfaChallenge,
        MfaCredential,
        PasswordResetToken,
        Session,
    )


class Organization(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        CheckConstraint("default_locale IN ('uk', 'en')", name="locale_allowed"),
        CheckConstraint("length(btrim(timezone)) > 0", name="timezone_not_blank"),
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=LifecycleStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    default_locale: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=Locale.UK.value,
        server_default=text("'uk'"),
    )
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    locations: Mapped[list["Location"]] = relationship(back_populates="organization")
    operational_roles: Mapped[list["OperationalRole"]] = relationship(back_populates="organization")
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        back_populates="organization"
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="organization")


class Location(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "locations"
    __table_args__ = (
        UniqueConstraint("id", "organization_id", name="uq_locations_id_organization_id"),
        CheckConstraint("length(btrim(name)) > 0", name="name_not_blank"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        CheckConstraint("length(btrim(timezone)) > 0", name="timezone_not_blank"),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=LifecycleStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    address: Mapped[str | None] = mapped_column(String(500))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)

    organization: Mapped[Organization] = relationship(back_populates="locations")


class OperationalRole(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "operational_roles"
    __table_args__ = (
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_operational_roles_id_organization_id",
        ),
        CheckConstraint("length(btrim(code)) > 0", name="code_not_blank"),
        CheckConstraint("code = lower(btrim(code))", name="code_normalized"),
        CheckConstraint("length(btrim(name_uk)) > 0", name="name_uk_not_blank"),
        CheckConstraint("status IN ('active', 'archived')", name="status_allowed"),
        Index(
            "uq_operational_roles_active_code",
            "organization_id",
            "code",
            unique=True,
            postgresql_where=text("status = 'active'"),
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name_uk: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=LifecycleStatus.ACTIVE.value,
        server_default=text("'active'"),
    )

    organization: Mapped[Organization] = relationship(back_populates="operational_roles")


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("length(email_normalized) > 0", name="email_not_blank"),
        CheckConstraint(
            "email_normalized = lower(btrim(email_normalized))",
            name="email_normalized",
        ),
        CheckConstraint("preferred_locale IN ('uk', 'en')", name="locale_allowed"),
    )

    email_normalized: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255))
    preferred_locale: Mapped[str] = mapped_column(
        String(8),
        nullable=False,
        default=Locale.UK.value,
        server_default=text("'uk'"),
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["OrganizationMembership"]] = relationship(back_populates="user")
    audit_events: Mapped[list["AuditEvent"]] = relationship(back_populates="actor_user")
    admin_accesses: Mapped[list["AdminAccess"]] = relationship(
        back_populates="user",
        foreign_keys="AdminAccess.user_id",
    )
    sessions: Mapped[list["Session"]] = relationship(back_populates="user")
    mfa_credentials: Mapped[list["MfaCredential"]] = relationship(back_populates="user")
    mfa_challenges: Mapped[list["MfaChallenge"]] = relationship(back_populates="user")
    password_reset_tokens: Mapped[list["PasswordResetToken"]] = relationship(back_populates="user")

    @validates("email_normalized")
    def _normalize_email(self, _: str, value: str) -> str:
        return normalize_email(value)


class OrganizationMembership(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "user_id",
            name="uq_organization_memberships_organization_user",
        ),
        UniqueConstraint(
            "id",
            "organization_id",
            name="uq_organization_memberships_id_organization_id",
        ),
        CheckConstraint(
            "status IN ('pending', 'active', 'disabled')",
            name="status_allowed",
        ),
        CheckConstraint(
            "training_participation_status IN ('active', 'paused')",
            name="training_participation_allowed",
        ),
        CheckConstraint(
            "(status <> 'active' OR (activated_at IS NOT NULL AND disabled_at IS NULL))",
            name="active_timestamps",
        ),
        CheckConstraint(
            "(status <> 'disabled' OR disabled_at IS NOT NULL)",
            name="disabled_timestamp",
        ),
        CheckConstraint(
            "(status <> 'pending' OR (activated_at IS NULL AND disabled_at IS NULL))",
            name="pending_timestamps",
        ),
        CheckConstraint(
            "(training_participation_status = 'active' "
            "AND training_paused_at IS NULL "
            "AND training_pause_reason_code IS NULL "
            "AND training_pause_note IS NULL "
            "AND planned_resume_at IS NULL) OR "
            "(training_participation_status = 'paused' AND training_paused_at IS NOT NULL)",
            name="training_pause_state",
        ),
        CheckConstraint(
            "planned_resume_at IS NULL OR planned_resume_at > training_paused_at",
            name="planned_resume_after_pause",
        ),
        CheckConstraint(
            "training_pause_reason_code IS NULL OR "
            "training_pause_reason_code ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="pause_reason_code_format",
        ),
        CheckConstraint(
            "training_pause_note IS NULL OR "
            "(training_pause_note = btrim(training_pause_note) "
            "AND length(training_pause_note) BETWEEN 1 AND 500)",
            name="pause_note_trimmed",
        ),
        CheckConstraint(
            "status = 'disabled' OR (disabled_reason_code IS NULL AND disabled_note IS NULL)",
            name="disabled_reason_state",
        ),
        CheckConstraint(
            "disabled_reason_code IS NULL OR disabled_reason_code ~ '^[a-z][a-z0-9_]{0,63}$'",
            name="disabled_reason_code_format",
        ),
        CheckConstraint(
            "disabled_note IS NULL OR "
            "(disabled_note = btrim(disabled_note) AND length(disabled_note) BETWEEN 1 AND 500)",
            name="disabled_note_trimmed",
        ),
    )

    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=MembershipStatus.PENDING.value,
        server_default=text("'pending'"),
    )
    training_participation_status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default=TrainingParticipationStatus.ACTIVE.value,
        server_default=text("'active'"),
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    training_pause_reason_code: Mapped[str | None] = mapped_column(String(64))
    training_pause_note: Mapped[str | None] = mapped_column(String(500))
    planned_resume_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    disabled_reason_code: Mapped[str | None] = mapped_column(String(64))
    disabled_note: Mapped[str | None] = mapped_column(String(500))

    organization: Mapped[Organization] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="memberships")
    employee_profile: Mapped["EmployeeProfile | None"] = relationship(
        back_populates="membership",
        uselist=False,
        primaryjoin=lambda: and_(
            OrganizationMembership.id == EmployeeProfile.membership_id,
            OrganizationMembership.organization_id == EmployeeProfile.organization_id,
        ),
        foreign_keys=lambda: [
            EmployeeProfile.membership_id,
            EmployeeProfile.organization_id,
        ],
    )


class EmployeeProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "employee_profiles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["membership_id", "organization_id"],
            ["organization_memberships.id", "organization_memberships.organization_id"],
            name="fk_employee_profiles_membership_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["operational_role_id", "organization_id"],
            ["operational_roles.id", "operational_roles.organization_id"],
            name="fk_employee_profiles_role_organization",
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["location_id", "organization_id"],
            ["locations.id", "locations.organization_id"],
            name="fk_employee_profiles_location_organization",
            ondelete="RESTRICT",
        ),
        UniqueConstraint("membership_id", name="uq_employee_profiles_membership_id"),
        UniqueConstraint("id", "organization_id", name="uq_employee_profiles_id_organization_id"),
    )

    membership_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    first_name: Mapped[str | None] = mapped_column(String(120))
    last_name: Mapped[str | None] = mapped_column(String(120))
    operational_role_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        index=True,
    )
    location_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        index=True,
    )

    membership: Mapped[OrganizationMembership] = relationship(
        back_populates="employee_profile",
        primaryjoin=lambda: and_(
            EmployeeProfile.membership_id == OrganizationMembership.id,
            EmployeeProfile.organization_id == OrganizationMembership.organization_id,
        ),
        foreign_keys=lambda: [
            EmployeeProfile.membership_id,
            EmployeeProfile.organization_id,
        ],
    )
    operational_role: Mapped[OperationalRole | None] = relationship(
        primaryjoin=lambda: and_(
            EmployeeProfile.operational_role_id == OperationalRole.id,
            EmployeeProfile.organization_id == OperationalRole.organization_id,
        ),
        foreign_keys=lambda: [
            EmployeeProfile.operational_role_id,
            EmployeeProfile.organization_id,
        ],
        viewonly=True,
    )
    location: Mapped[Location | None] = relationship(
        primaryjoin=lambda: and_(
            EmployeeProfile.location_id == Location.id,
            EmployeeProfile.organization_id == Location.organization_id,
        ),
        foreign_keys=lambda: [EmployeeProfile.location_id, EmployeeProfile.organization_id],
        viewonly=True,
    )
