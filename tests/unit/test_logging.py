import json

import pytest
from src.common.logging import configure_logging, get_logger


def test_logger_emits_json_line(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log = get_logger()
    log.info("order_synced", order_id=12345, marketplace="mercadolibre")

    out = capsys.readouterr().out.strip()
    payload = json.loads(out)
    assert payload["event"] == "order_synced"
    assert payload["order_id"] == 12345
    assert payload["marketplace"] == "mercadolibre"
    assert payload["level"] == "info"
    assert payload["service"].startswith("retail-order-sync-hub@")
    assert "timestamp" in payload


def test_level_filtering_drops_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    log = get_logger()
    log.debug("should_not_appear")
    assert capsys.readouterr().out.strip() == ""
