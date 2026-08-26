from enum import StrEnum


class Locale(StrEnum):
    UK = "uk"
    EN = "en"


class LifecycleStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class MembershipStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    DISABLED = "disabled"


class AuditActorType(StrEnum):
    USER = "user"
    SYSTEM = "system"
    WORKER = "worker"
    CRON = "cron"


class AuditOutcome(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
