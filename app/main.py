"""FastAPI application exposing the versioned ISBN contract."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse

from .cache import Cache
from .config import Settings
from .finna import FinnaClient, UpstreamError, UpstreamTimeout, normalize_record
from .isbn import ISBN, InvalidISBNError
from .logging import configure_logging, get_logger
from .models import BookRecord, ErrorResponse, HealthResponse, VersionResponse

_NOT_FOUND = object()  # cache sentinel for a validated-but-missing ISBN
_READY_CACHE_TTL = 5.0  # seconds; avoid hammering Finna on /readyz


def _error(status: int, error: str, message: str, isbn: str | None = None) -> JSONResponse:
    body = ErrorResponse(error=error, message=message, isbn=isbn).model_dump()
    return JSONResponse(status_code=status, content=body)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    configure_logging(settings.log_level)
    log = get_logger()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.settings = settings
        app.state.cache = Cache(settings.cache_ttl_seconds, settings.cache_max_entries)
        app.state.finna = FinnaClient(
            base_url=settings.finna_base_url,
            user_agent=settings.finna_user_agent,
            language=settings.finna_language,
            timeout_seconds=settings.request_timeout_seconds,
        )
        app.state.ready_cache = {"value": False, "at": 0.0}
        log.info(
            "service started",
            extra={"version": settings.version, "port": settings.http_port},
        )
        try:
            yield
        finally:
            await app.state.finna.aclose()
            log.info("service stopped")

    app = FastAPI(
        title="finna-isbn",
        version=settings.version,
        description="ISBN -> normalized book metadata backed by the Finna open REST API.",
        lifespan=lifespan,
    )

    @app.get(
        "/v1/isbn/{isbn}",
        response_model=BookRecord,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def get_isbn(isbn: str, raw: bool = False) -> Response:
        started = time.monotonic()
        cache: Cache = app.state.cache
        finna: FinnaClient = app.state.finna

        try:
            parsed = ISBN.parse(isbn)
        except InvalidISBNError as exc:
            log.info(
                "invalid isbn",
                extra={"isbn": isbn, "duration_ms": _ms(started), "cache": "n/a"},
            )
            return _error(400, "invalid_isbn", str(exc), isbn)

        cache_key = parsed.isbn13
        cached = cache.get(cache_key)
        if cached is not None:
            if cached is _NOT_FOUND:
                log.info(
                    "isbn lookup",
                    extra={
                        "isbn": parsed.isbn13,
                        "finna_status": "not_found",
                        "cache": "hit",
                        "duration_ms": _ms(started),
                    },
                )
                return _error(404, "not_found", "No Finna record for ISBN", parsed.isbn13)
            result = normalize_record(cached, parsed, include_raw=raw)
            log.info(
                "isbn lookup",
                extra={
                    "isbn": parsed.isbn13,
                    "finna_status": "ok",
                    "cache": "hit",
                    "duration_ms": _ms(started),
                },
            )
            return JSONResponse(content=_clean(result))

        try:
            record = await finna.find_by_isbn(parsed)
        except UpstreamTimeout:
            log.warning(
                "upstream timeout",
                extra={"isbn": parsed.isbn13, "duration_ms": _ms(started), "cache": "miss"},
            )
            return _error(504, "upstream_timeout", "Finna did not respond in time", parsed.isbn13)
        except UpstreamError as exc:
            log.warning(
                "upstream error",
                extra={
                    "isbn": parsed.isbn13,
                    "finna_status": "error",
                    "duration_ms": _ms(started),
                    "cache": "miss",
                    "detail": str(exc),
                },
            )
            return _error(502, "upstream_error", "Finna returned an error", parsed.isbn13)

        if record is None:
            cache.set(cache_key, _NOT_FOUND)
            log.info(
                "isbn lookup",
                extra={
                    "isbn": parsed.isbn13,
                    "finna_status": "not_found",
                    "cache": "miss",
                    "duration_ms": _ms(started),
                },
            )
            return _error(404, "not_found", "No Finna record for ISBN", parsed.isbn13)

        cache.set(cache_key, record)
        result = normalize_record(record, parsed, include_raw=raw)
        log.info(
            "isbn lookup",
            extra={
                "isbn": parsed.isbn13,
                "finna_status": "ok",
                "cache": "miss",
                "duration_ms": _ms(started),
            },
        )
        return JSONResponse(content=_clean(result))

    @app.get("/healthz", response_model=HealthResponse)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", responses={200: {"model": HealthResponse}, 503: {"model": HealthResponse}})
    async def readyz() -> Response:
        finna: FinnaClient = app.state.finna
        ready_cache: dict[str, Any] = app.state.ready_cache
        now = time.monotonic()
        if now - ready_cache["at"] < _READY_CACHE_TTL:
            ok = ready_cache["value"]
        else:
            ok = await finna.ping()
            ready_cache["value"] = ok
            ready_cache["at"] = now
        if ok:
            return JSONResponse(content={"status": "ok"})
        return JSONResponse(status_code=503, content={"status": "unavailable"})

    @app.get("/version", response_model=VersionResponse)
    async def version() -> dict[str, str]:
        return {
            "version": settings.version,
            "commit": settings.commit,
            "buildTime": settings.build_time,
        }

    return app


def _ms(started: float) -> float:
    return round((time.monotonic() - started) * 1000, 2)


def _clean(result: dict[str, Any]) -> dict[str, Any]:
    """Drop the raw key when it was not requested so the contract stays tight."""
    if "raw" in result and result["raw"] is None:
        result.pop("raw")
    return result


# Uvicorn entrypoint (factory mode): `uvicorn app.main:create_app --factory`
# Using a factory avoids requiring env vars at import time (keeps tests importable).
