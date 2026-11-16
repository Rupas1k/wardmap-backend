from enum import StrEnum

REPLAY_DELETED_ERROR = "Replay deleted from server"


class AccessLevel(StrEnum):
    ANONYMOUS = "anonymous"
    ADVANCED = "advanced"
    ADMIN = "admin"


class JobStatus(StrEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class LeagueTrackingStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"


class WardType(StrEnum):
    SENTRY = "sentry"
    OBSERVER = "observer"


class Team(StrEnum):
    RADIANT = "radiant"
    DIRE = "dire"
