"""Command-line entry point to run the Wanxiang API server."""
from __future__ import annotations

import os
from typing import Final

import uvicorn

DEFAULT_HOST: Final[str] = "0.0.0.0"
DEFAULT_PORT: Final[int] = 8000
APP_IMPORT_PATH: Final[str] = "api_server.main:app"


def main() -> None:
    """Launch the ASGI server using environment-provided host/port."""

    host = os.getenv("API_HOST", DEFAULT_HOST)
    try:
        port = int(os.getenv("API_PORT", DEFAULT_PORT))
    except ValueError as exc:  # pragma: no cover - runtime validation
        raise SystemExit(f"Invalid API_PORT value: {exc}") from exc

    uvicorn.run(APP_IMPORT_PATH, host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":  # pragma: no cover - manual execution path
    main()
