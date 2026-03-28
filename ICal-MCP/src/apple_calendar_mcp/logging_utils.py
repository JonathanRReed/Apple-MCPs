import logging

from apple_calendar_mcp.config import load_settings


_LOGGER_NAME = "apple_calendar_mcp"


def get_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger

    settings = load_settings()
    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def audit_log(tool_name: str, result: str, **fields: object) -> None:
    logger = get_logger()
    payload = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    message = f"{tool_name} {result}"
    if payload:
        message = f"{message} {payload}"
    logger.info(message)
