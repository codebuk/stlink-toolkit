"""Coloured logger for stlink_toolkit.

Uses stdlib ``logging`` so callers can add their own handlers/levels.
The default handler writes to stderr with ANSI colour codes:

    ERROR    -> red       (something went wrong; user attention required)
    WARNING  -> yellow    (recoverable but worth noticing)
    NOTICE   -> purple    (custom level 25 — important user-facing event,
                            e.g. SWD frequency fallback that should never happen)
    INFO     -> default
    DEBUG    -> dim grey
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Final

NOTICE: Final[int] = 25
logging.addLevelName(NOTICE, "NOTICE")

_RESET = "\033[0m"
_COLOURS = {
    logging.DEBUG: "\033[2m",        # dim
    logging.INFO: "",                # default
    NOTICE: "\033[35m",              # purple/magenta
    logging.WARNING: "\033[33m",     # yellow
    logging.ERROR: "\033[31m",       # red
    logging.CRITICAL: "\033[1;31m",  # bold red
}


class _ColourFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # noqa: D401
        msg = super().format(record)
        if not _use_colour():
            return msg
        colour = _COLOURS.get(record.levelno, "")
        return f"{colour}{msg}{_RESET}" if colour else msg


def _use_colour() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return sys.stderr.isatty()


_LOGGER_NAME = "stlink_toolkit"
_logger = logging.getLogger(_LOGGER_NAME)


def _bootstrap() -> None:
    if _logger.handlers:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(_ColourFormatter("[%(name)s] %(message)s"))
    _logger.addHandler(handler)
    _logger.setLevel(logging.INFO)
    _logger.propagate = False


_bootstrap()


def get_logger(name: str = _LOGGER_NAME) -> logging.Logger:
    """Return the toolkit logger (or a child logger)."""
    if name == _LOGGER_NAME:
        return _logger
    return _logger.getChild(name)


def notice(msg: str, *args, **kwargs) -> None:
    """Log a NOTICE (purple) — user-visible event that should rarely happen."""
    _logger.log(NOTICE, msg, *args, **kwargs)


def info(msg: str, *args, **kwargs) -> None:
    _logger.info(msg, *args, **kwargs)


def warning(msg: str, *args, **kwargs) -> None:
    _logger.warning(msg, *args, **kwargs)


def error(msg: str, *args, **kwargs) -> None:
    _logger.error(msg, *args, **kwargs)


def critical(msg: str, *args, **kwargs) -> None:
    _logger.critical(msg, *args, **kwargs)


def debug(msg: str, *args, **kwargs) -> None:
    _logger.debug(msg, *args, **kwargs)
