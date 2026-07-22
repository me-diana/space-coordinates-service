import logging

from .config import get_settings

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configure_logging() -> None:
    level_name = get_settings().log_level.upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        raise ValueError(
            f"Invalid LOG_LEVEL: {level_name!r}. "
            "Expected one of: DEBUG, INFO, WARNING, ERROR, CRITICAL."
        )

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        force=True,
    )

    for logger_name in _UVICORN_LOGGERS:
        logging.getLogger(logger_name).setLevel(level)
