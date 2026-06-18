"""Run paris-mock: ``python -m src.paris_mock`` (or via docker-compose)."""

from __future__ import annotations

import uvicorn

from src.paris_mock.app import create_app

app = create_app()


def main() -> None:
    uvicorn.run(app, host="0.0.0.0", port=9100)


if __name__ == "__main__":
    main()
