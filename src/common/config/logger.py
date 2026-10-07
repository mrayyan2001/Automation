"""Logging formatters and application logging configuration."""

import logging
import logging.config
from datetime import (
    UTC,
    datetime,
)
from pathlib import (
    Path,
)
from typing import (
    ClassVar,
)


class ColoredFormatter(logging.Formatter):
    """Format log levels with ANSI colors for console output."""

    COLORS: ClassVar[
        dict[
            int,
            str,
        ]
    ] = {
        # ANSI color escape sequence keyed by logging level.
        logging.DEBUG: "\033[36m",  # Cyan
        logging.INFO: "\033[32m",  # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",  # Red
        logging.CRITICAL: "\033[1;31m",  # Bold Red
    }
    RESET = "\033[0m"
    """ANSI escape sequence that resets the console color."""

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        """Format a log record with a colored, padded level name.

        Args:
            record: Log record to format.

        Returns:
            The formatted log message.
        """
        color = self.COLORS.get(
            record.levelno,
            self.RESET,
        )

        level_with_colon = f"{record.levelname}:"
        padded_level = f"{level_with_colon:<9}"

        log_fmt = f"{color}{padded_level}{self.RESET} %(message)s"

        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


# Ensure the logs directory exists
LOGS_DIR = Path("logs")
"""Directory where per-run application log files are written."""
LOGS_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

# Generate a unique log filename per execution based on datetime
run_timestamp = datetime.now(UTC).strftime("%Y-%m-%d_%H-%M-%S")
"""Timestamp used to make the current run's log filename unique."""
log_filepath = LOGS_DIR / f"app_{run_timestamp}.log"
"""Path to the current run's application log file."""


LOGGING_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "colored": {
            "()": ColoredFormatter,
        },
        "file_standard": {
            "format": "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "colored",
            "stream": "ext://sys.stdout",
        },
        "file": {
            "class": "logging.FileHandler",
            "filename": str(log_filepath),
            "formatter": "file_standard",
            "mode": "a",
            "encoding": "utf-8",
        },
    },
    "loggers": {
        "": {
            "handlers": [
                "console",
                "file",
            ],
            "level": "INFO",
        },
    },
}
"""Dictionary configuration consumed by :func:`setup_logging`."""


def setup_logging() -> None:
    """Configure console and file logging for the application."""
    logging.config.dictConfig(LOGGING_CONFIG)
    logger = logging.getLogger(__name__)
    logger.info("Logging configured")
