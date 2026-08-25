import os
from dataclasses import dataclass
from functools import lru_cache

import dotenv

dotenv.load_dotenv()


def _integer(name: str, default: int, *, minimum: int = 0) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc
    if value < minimum:
        raise RuntimeError(f"{name} must be at least {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class Settings:
    database_url: str
    redis_url: str
    opendota_api_url: str
    opendota_api_key: str | None
    opendota_timeout: float
    log_level: str
    cors_origins: tuple[str, ...]
    parser_workers: int
    collector_interval_seconds: int
    job_retention_days: int
    job_cleanup_interval_seconds: int
    anonymous_rate_limit: int
    advanced_rate_limit: int
    admin_rate_limit: int
    anonymous_max_ward_page_size: int
    advanced_max_ward_page_size: int
    admin_max_ward_page_size: int

    @classmethod
    def from_environment(cls) -> "Settings":
        try:
            database_url = os.environ["DB_URL"]
            redis_url = os.environ["REDIS_URL"]
        except KeyError as exc:
            raise RuntimeError(f"Required environment variable {exc.args[0]} is missing") from exc

        origins = tuple(
            origin.strip()
            for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        )
        try:
            opendota_timeout = float(os.getenv("OPENDOTA_TIMEOUT", "30"))
        except ValueError as exc:
            raise RuntimeError("OPENDOTA_TIMEOUT must be numeric") from exc
        if opendota_timeout <= 0:
            raise RuntimeError("OPENDOTA_TIMEOUT must be greater than zero")

        return cls(
            database_url=database_url,
            redis_url=redis_url,
            opendota_api_url=os.getenv("OPENDOTA_API_URL", "https://api.opendota.com/api").rstrip("/"),
            opendota_api_key=os.getenv("OPENDOTA_API_KEY") or None,
            opendota_timeout=opendota_timeout,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
            cors_origins=origins,
            parser_workers=_integer("PARSER_WORKERS", 2, minimum=1),
            collector_interval_seconds=_integer("COLLECTOR_INTERVAL_SECONDS", 300, minimum=60),
            job_retention_days=_integer("JOB_RETENTION_DAYS", 7, minimum=1),
            job_cleanup_interval_seconds=_integer("JOB_CLEANUP_INTERVAL_SECONDS", 3600, minimum=60),
            anonymous_rate_limit=_integer("ANONYMOUS_RATE_LIMIT_PER_MINUTE", 60),
            advanced_rate_limit=_integer("ADVANCED_RATE_LIMIT_PER_MINUTE", 600),
            admin_rate_limit=_integer("ADMIN_RATE_LIMIT_PER_MINUTE", 0),
            anonymous_max_ward_page_size=_integer("ANONYMOUS_MAX_WARD_PAGE_SIZE", 5000, minimum=1),
            advanced_max_ward_page_size=_integer("ADVANCED_MAX_WARD_PAGE_SIZE", 5000, minimum=1),
            admin_max_ward_page_size=_integer("ADMIN_MAX_WARD_PAGE_SIZE", 10000, minimum=1),
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_environment()
