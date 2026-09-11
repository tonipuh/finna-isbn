"""Response contract models (SPEC.md section 4)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class BookRecord(BaseModel):
    isbn13: str | None = None
    isbn10: str | None = None
    title: str | None = None
    subtitle: str | None = None
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    publisher: str | None = None
    languages: list[str] = Field(default_factory=list)
    formats: list[str] = Field(default_factory=list)
    cover_url: str | None = None
    finna_url: str | None = None
    finna_id: str | None = None
    source: str = "finna"
    raw: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    error: str
    message: str
    isbn: str | None = None


class VersionResponse(BaseModel):
    version: str
    commit: str
    buildTime: str


class HealthResponse(BaseModel):
    status: str
