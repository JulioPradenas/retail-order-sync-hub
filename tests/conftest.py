"""Shared pytest fixtures and integration gating.

Integration tests (marked ``@pytest.mark.integration``) require the docker
stack. They are skipped unless ``ROSH_INTEGRATION=1`` so ``make check`` / CI
stay fast and hermetic.
"""

from __future__ import annotations

import os

import pytest

INTEGRATION_ENABLED = os.getenv("ROSH_INTEGRATION") == "1"


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if INTEGRATION_ENABLED:
        return
    skip = pytest.mark.skip(reason="integration test — set ROSH_INTEGRATION=1 to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip)
