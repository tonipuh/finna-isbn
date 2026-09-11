"""Finna REST API client + record normalization (SPEC.md sections 4-5)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from .isbn import ISBN, normalize

# Fields requested from Finna (verified against api.finna.fi/v1/search).
_FIELDS = [
    "id",
    "title",
    "shortTitle",
    "subTitle",
    "authors",
    "year",
    "publishers",
    "languages",
    "formats",
    "images",
    "cleanIsbn",
    "isbns",
]

FINNA_RECORD_BASE = "https://www.finna.fi/Record/"
FINNA_COVER_BASE = "https://www.finna.fi/Cover/Show"
FINNA_WEB_BASE = "https://www.finna.fi"


class UpstreamError(Exception):
    """Finna responded with an error / invalid payload -> 502."""


class UpstreamTimeout(Exception):
    """Finna did not respond within REQUEST_TIMEOUT_SECONDS -> 504."""


class FinnaClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        language: str,
        timeout_seconds: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._language = language
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout_seconds),
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    def _search_params(self, lookfor: str, limit: int) -> list[tuple[str, str]]:
        params: list[tuple[str, str]] = [
            ("lookfor", lookfor),
            ("type", "ISN"),  # VuFind ISBN/ISSN search (verified against Finna).
            ("limit", str(limit)),
        ]
        for field in _FIELDS:
            params.append(("field[]", field))
        if self._language:
            params.append(("lng", self._language))
        return params

    async def _search(self, lookfor: str, limit: int) -> dict[str, Any]:
        url = f"{self._base_url}/search"
        try:
            resp = await self._client.get(url, params=self._search_params(lookfor, limit))
        except httpx.TimeoutException as exc:
            raise UpstreamTimeout(str(exc)) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(str(exc)) from exc

        if resp.status_code >= 500:
            raise UpstreamError(f"Finna returned HTTP {resp.status_code}")
        if resp.status_code >= 400:
            raise UpstreamError(f"Finna returned HTTP {resp.status_code}")
        try:
            data = resp.json()
        except ValueError as exc:
            raise UpstreamError("Finna returned non-JSON body") from exc
        if not isinstance(data, dict) or data.get("status") != "OK":
            raise UpstreamError(f"Finna status not OK: {data if isinstance(data, dict) else 'n/a'}")
        return data

    async def find_by_isbn(self, isbn: ISBN) -> dict[str, Any] | None:
        """Return the best-matching raw Finna record for an ISBN, or None if not found."""
        data = await self._search(isbn.isbn13, limit=5)
        records = data.get("records") or []
        if not records:
            return None
        return _select_best(records, isbn)

    async def ping(self) -> bool:
        """Lightweight readiness probe: a limit=0 search that must return status OK."""
        try:
            await self._search("9789510000000", limit=0)
            return True
        except (UpstreamError, UpstreamTimeout):
            return False


def _select_best(records: list[dict[str, Any]], isbn: ISBN) -> dict[str, Any]:
    """Score records and return the best match; stable (first wins on ties)."""
    wanted = {isbn.isbn13}
    if isbn.isbn10:
        wanted.add(isbn.isbn10)

    def isbn_matches(rec: dict[str, Any]) -> bool:
        candidates: set[str] = set()
        clean = rec.get("cleanIsbn")
        if clean:
            candidates.add(normalize(str(clean)))
        for raw in rec.get("isbns") or []:
            candidates.add(normalize(str(raw)))
        return bool(candidates & wanted)

    def format_values(rec: dict[str, Any]) -> list[str]:
        out = []
        for fmt in rec.get("formats") or []:
            value = fmt.get("value", "") if isinstance(fmt, dict) else str(fmt)
            out.append(value.lower())
        return out

    def score(rec: dict[str, Any]) -> int:
        values = format_values(rec)
        s = 0
        if isbn_matches(rec):
            s += 4
        if any("book/book" in v for v in values):  # printed book, e.g. 1/Book/Book/
            s += 2
        elif any("book" in v for v in values):  # any book family (audiobook, ebook, ...)
            s += 1
        return s

    best_index = max(range(len(records)), key=lambda i: (score(records[i]), -i))
    return records[best_index]


def _extract_authors(authors: Any) -> list[str]:
    """Finna authors is an object: {primary:{name:{...}}, secondary:[...], corporate:[...]}."""
    if not isinstance(authors, dict):
        return []
    result: list[str] = []
    for group in ("primary", "secondary", "corporate"):
        value = authors.get(group)
        if isinstance(value, dict):
            result.extend(value.keys())
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    result.append(item)
                elif isinstance(item, dict):
                    result.extend(item.keys())
    # De-duplicate while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for name in result:
        if name and name not in seen:
            seen.add(name)
            ordered.append(name)
    return ordered


def _extract_formats(formats: Any) -> list[str]:
    result: list[str] = []
    for fmt in formats or []:
        if isinstance(fmt, dict):
            label = fmt.get("translated") or fmt.get("value")
            if label:
                result.append(str(label))
        elif isinstance(fmt, str):
            result.append(fmt)
    seen: set[str] = set()
    ordered: list[str] = []
    for label in result:
        if label not in seen:
            seen.add(label)
            ordered.append(label)
    return ordered


def _parse_year(year: Any) -> int | None:
    if year is None:
        return None
    try:
        return int(str(year).strip()[:4])
    except (ValueError, TypeError):
        return None


def _first_str(value: Any) -> str | None:
    if isinstance(value, list):
        for item in value:
            if item:
                return str(item)
        return None
    if value in (None, ""):
        return None
    return str(value)


def _cover_url(record: dict[str, Any], isbn: ISBN) -> str | None:
    """Prefer the record's own image; fall back to the ISBN-based cover endpoint."""
    images = record.get("images") or []
    if images:
        first = str(images[0])
        if first.startswith("http://") or first.startswith("https://"):
            return first
        if first.startswith("/"):
            return FINNA_WEB_BASE + first
        return f"{FINNA_WEB_BASE}/{first}"
    return f"{FINNA_COVER_BASE}?isbn={isbn.isbn13}&size=large"


def normalize_record(record: dict[str, Any], isbn: ISBN, include_raw: bool) -> dict[str, Any]:
    finna_id = record.get("id")
    finna_url = None
    if finna_id:
        # Percent-encode the id so slashes/colons in Finna ids survive in the URL path.
        finna_url = FINNA_RECORD_BASE + quote(str(finna_id), safe="")

    title = _first_str(record.get("title")) or _first_str(record.get("shortTitle"))
    subtitle = _first_str(record.get("subTitle"))

    result: dict[str, Any] = {
        "isbn13": isbn.isbn13,
        "isbn10": isbn.isbn10,
        "title": title,
        "subtitle": subtitle,
        "authors": _extract_authors(record.get("authors")),
        "year": _parse_year(record.get("year")),
        "publisher": _first_str(record.get("publishers")),
        "languages": [str(x) for x in (record.get("languages") or []) if x],
        "formats": _extract_formats(record.get("formats")),
        "cover_url": _cover_url(record, isbn),
        "finna_url": finna_url,
        "finna_id": str(finna_id) if finna_id else None,
        "source": "finna",
    }
    if include_raw:
        result["raw"] = record
    return result
