from sqlalchemy import CheckConstraint, Index, UniqueConstraint

from app.db.base import Base
from app.models import (
    AttentionCase,
    AttentionCaseAction,
    AttentionCaseSource,
    AttentionCaseState,
    AttentionCaseType,
    CriticalError,
    RetakeRequirement,
    RetakeRequirementAction,
    RetakeRequirementReason,
    RetakeRequirementState,
)

ATTENTION_RETAKE_TABLES = {
    "critical_errors",
    "attention_cases",
    "attention_case_sources",
    "attention_case_actions",
    "retake_requirements",
    "retake_requirement_actions",
}


def _constraint_names(table_name: str, kind: type[object]) -> set[str]:
    table = Base.metadata.tables[table_name]
    return {
        constraint.name
        for constraint in table.constraints
        if isinstance(constraint, kind) and isinstance(constraint.name, str)
    }


def _index_names(table_name: str) -> set[str]:
    return {
        index.name
        for index in Base.metadata.tables[table_name].indexes
        if isinstance(index, Index) and index.name is not None
    }


def test_attention_retake_models_register_exact_tables() -> None:
    assert {
        CriticalError.__tablename__,
        AttentionCase.__tablename__,
        AttentionCaseSource.__tablename__,
        AttentionCaseAction.__tablename__,
        RetakeRequirement.__tablename__,
        RetakeRequirementAction.__tablename__,
    } == ATTENTION_RETAKE_TABLES
    assert set(Base.metadata.tables) >= ATTENTION_RETAKE_TABLES


def test_attention_retake_state_values_are_stable() -> None:
    assert {item.value for item in AttentionCaseState} == {
        "open",
        "acknowledged",
        "resolved",
    }
    assert {item.value for item in AttentionCaseType} == {
        "critical_allergen",
        "retake_overdue",
    }
    assert {item.value for item in RetakeRequirementState} == {
        "proposed",
        "active",
        "completed",
        "cancelled",
    }
    assert {item.value for item in RetakeRequirementReason} == {
        "failed_exam",
        "critical_error",
        "management_follow_up",
        "material_content_change",
    }


def test_critical_error_and_attention_constraints_protect_source_history() -> None:
    assert "uq_critical_errors_source_answer" in _constraint_names(
        "critical_errors", UniqueConstraint
    )
    assert "ck_attention_case_sources_exactly_one_source" in _constraint_names(
        "attention_case_sources", CheckConstraint
    )
    assert "uq_attention_cases_unresolved_critical" in _index_names("attention_cases")
    assert "uq_attention_case_sources_critical_error" in _index_names("attention_case_sources")
    assert "uq_attention_case_sources_retake_requirement" in _index_names("attention_case_sources")


def test_retake_constraints_protect_one_current_obligation_and_terminal_state() -> None:
    assert "uq_retake_requirements_failed_current" in _index_names("retake_requirements")
    assert "uq_retake_requirements_failed_source" in _index_names("retake_requirements")
    assert "uq_retake_requirements_critical_current" in _index_names("retake_requirements")
    assert "ck_retake_requirements_terminal_state_match" in _constraint_names(
        "retake_requirements", CheckConstraint
    )
    assert "ck_retake_requirements_target_policy_object" in _constraint_names(
        "retake_requirements", CheckConstraint
    )
