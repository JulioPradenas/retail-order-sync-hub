"""Run the MCP server via stdio: ``python -m src.mcp_server``."""

from __future__ import annotations

from src.common.config import get_settings
from src.common.logging import configure_logging
from src.mcp_server.server import mcp


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    mcp.run()


if __name__ == "__main__":
    main()
