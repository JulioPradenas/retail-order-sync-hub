"""Run bq_sync once: ``python -m src.bq_sync``."""

from __future__ import annotations

from src.bq_sync.sync import run_sync
from src.common.config import get_settings
from src.common.logging import configure_logging, get_logger

log = get_logger()


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    result = run_sync(settings)
    log.info("bq_sync.done", **result)


if __name__ == "__main__":
    main()
