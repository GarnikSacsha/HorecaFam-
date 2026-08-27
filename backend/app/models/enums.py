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


class AdminScope(StrEnum):
    ORGANIZATION_ADMIN = "organization_admin"
    PLATFORM_OPERATOR = "platform_operator"


class AccessStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class MfaCredentialType(StrEnum):
    TOTP = "totp"


class AuthRateLimitAction(StrEnum):
    LOGIN = "login"


class BackgroundJobType(StrEnum):
    INVITATION_EMAIL = "invitation_email"


class BackgroundJobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EmailDeliveryStatus(StrEnum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DELIVERED = "delivered"
    BOUNCED = "bounced"
    FAILED = "failed"


class MenuVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class MenuAvailability(StrEnum):
    AVAILABLE = "available"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    SEASONAL = "seasonal"
    DISCONTINUED = "discontinued"


class FactDataStatus(StrEnum):
    UNKNOWN = "unknown"
    CONFIRMED_NONE = "confirmed_none"
    CONFIRMED_PRESENT = "confirmed_present"


class MenuDeltaKind(StrEnum):
    ADDED = "added"
    CHANGED = "changed"
    REMOVED = "removed"
    UNCHANGED = "unchanged"


class TrainingImpact(StrEnum):
    NONE = "none"
    REVIEW = "review"
    REQUIRED = "required"


class MenuSourceKind(StrEnum):
    MANUAL = "manual"
    JSON_IMPORT = "json_import"


class TranslationStatus(StrEnum):
    DRAFT = "draft"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
