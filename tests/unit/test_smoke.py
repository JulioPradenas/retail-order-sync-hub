"""Smoke test — gives CI something real to run from phase 0 onward."""

from src import __version__
from src.common import SERVICE_NAMESPACE, service_identity


def test_version_is_exposed() -> None:
    assert __version__ == "0.1.0"


def test_service_identity_combines_namespace_and_version() -> None:
    assert service_identity() == f"{SERVICE_NAMESPACE}@{__version__}"
    assert service_identity() == "retail-order-sync-hub@0.1.0"
