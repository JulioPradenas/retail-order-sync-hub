from sqlalchemy import create_engine, inspect
from src.common import models  # noqa: F401  (register tables on Base.metadata)
from src.common.db import Base


def test_metadata_declares_all_skeleton_tables() -> None:
    expected = {
        "webhook_log",
        "webhook_dedup",
        "orders",
        "outbox",
        "oauth_tokens",
        "mcp_audit_log",
    }
    assert expected <= set(Base.metadata.tables)


def test_create_all_on_sqlite() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())
    assert "outbox" in tables
    assert "mcp_audit_log" in tables
