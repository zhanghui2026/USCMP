"""Application logging configuration."""

import logging
import sys
from app.core.config import settings


def setup_logging() -> logging.Logger:
    logger = logging.getLogger("congress-graph")

    if settings.app_env == "development":
        logger.setLevel(logging.DEBUG)
    else:
        logger.setLevel(logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


logger = setup_logging()
