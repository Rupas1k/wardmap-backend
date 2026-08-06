import logging
import logging.config
import sys
import time

from .settings import get_settings


class UTCFormatter(logging.Formatter):
    converter = time.gmtime


def build_logging_config() -> dict:
    configured_level = get_settings().log_level
    level = configured_level if configured_level in logging.getLevelNamesMapping() else "INFO"
    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "()": UTCFormatter,
                "format": (
                    "%(asctime)s.%(msecs)03dZ %(levelname)s [%(processName)s:%(process)d] %(name)s: %(message)s"
                ),
                "datefmt": "%Y-%m-%dT%H:%M:%S",
            }
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
                "stream": sys.stdout,
            }
        },
        "root": {"handlers": ["stdout"], "level": level},
        "loggers": {
            "gunicorn.access": {"handlers": ["stdout"], "level": level, "propagate": False},
            "gunicorn.error": {"handlers": ["stdout"], "level": level, "propagate": False},
        },
    }


def configure_logging() -> None:
    configured_level = get_settings().log_level
    logging.config.dictConfig(build_logging_config())

    if configured_level not in logging.getLevelNamesMapping():
        logging.getLogger(__name__).warning("Invalid LOG_LEVEL %r; using INFO", configured_level)
