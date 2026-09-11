"""Container entrypoint: `python -m app`. Binds to HTTP_PORT with graceful shutdown."""

from __future__ import annotations

import uvicorn

from .config import Settings


def main() -> None:
    settings = Settings.from_env()
    uvicorn.run(
        "app.main:create_app",
        factory=True,
        host="0.0.0.0",  # noqa: S104 - service is meant to listen on all interfaces in-container
        port=settings.http_port,
        log_config=None,  # our JSON logging is configured in create_app()
        access_log=False,
        server_header=False,
    )


if __name__ == "__main__":
    main()
