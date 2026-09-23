from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDPrimaryKeyMixin


class LessonQuestionCycle(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lesson_question_cycles"
    __table_args__ = (
        ForeignKeyConstraint(
            ["employee_profile_id", "organization_id"],
            ["employee_profiles.id", "employee_profiles.organization_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint(
            "employee_profile_id", "lesson_id", "number", name="uq_lesson_cycle_number"
        ),
        CheckConstraint("number > 0", name="number_positive"),
        Index(
            "uq_lesson_cycle_active",
            "employee_profile_id",
            "lesson_id",
            unique=True,
            postgresql_where=text("ended_at IS NULL"),
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    location_id: Mapped[UUID] = mapped_column(ForeignKey("locations.id", ondelete="RESTRICT"))
    employee_profile_id: Mapped[UUID]
    lesson_id: Mapped[UUID] = mapped_column(ForeignKey("lessons.id", ondelete="RESTRICT"))
    number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class LessonQuestionCycleItem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "lesson_question_cycle_items"
    __table_args__ = (
        UniqueConstraint("cycle_id", "question_id", name="uq_lesson_cycle_question"),
        ForeignKeyConstraint(
            ["question_version_id", "question_id"],
            ["question_versions.id", "question_versions.question_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("origin IN ('legacy', 'reserved')", name="origin_allowed"),
    )
    cycle_id: Mapped[UUID] = mapped_column(
        ForeignKey("lesson_question_cycles.id", ondelete="RESTRICT")
    )
    question_id: Mapped[UUID]
    question_version_id: Mapped[UUID]
    attempt_question_id: Mapped[UUID] = mapped_column(
        ForeignKey("attempt_questions.id", ondelete="RESTRICT")
    )
    origin: Mapped[str] = mapped_column(String(16))
