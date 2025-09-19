"""Logging utilities"""

import sys

from loguru import logger


def setup_logging(level: str = "INFO"):  # noqa: ANN201 - Can't declare the loguru type with private class access
    """Setup structured logging for noxus-sdk"""
    logger.remove()

    logger.add(
        sys.stderr,
        level=level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    return logger
