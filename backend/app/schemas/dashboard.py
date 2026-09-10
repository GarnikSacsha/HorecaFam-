from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class DashboardCounts(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DashboardEmployees(DashboardCounts):
    total: int = Field(ge=0)
    active: int = Field(ge=0)
    pending: int = Field(ge=0)
    paused: int = Field(ge=0)
    disabled: int = Field(ge=0)


class DashboardTraining(DashboardCounts):
    assigned: int = Field(ge=0)
    in_progress: int = Field(ge=0)
    completed: int = Field(ge=0)


class DashboardFinalExam(DashboardCounts):
    certified: int = Field(ge=0)
    needs_exam: int = Field(ge=0)
    retake: int = Field(ge=0)
    overdue_retake: int = Field(ge=0)


class DashboardAttention(DashboardCounts):
    unresolved: int = Field(ge=0)
    critical: int = Field(ge=0)


class DashboardResponse(DashboardCounts):
    organization_id: UUID
    location_id: UUID | None
    employees: DashboardEmployees
    training: DashboardTraining
    final_exam: DashboardFinalExam
    attention: DashboardAttention
