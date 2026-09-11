import pytest

from app.config import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        http_port=8080,
        finna_base_url="https://api.finna.fi/v1",
        finna_user_agent="finna-isbn-test/0.0 (+https://example.test)",
        finna_language="fin",
        request_timeout_seconds=5,
        cache_ttl_seconds=60,
        cache_max_entries=100,
        log_level="warn",
        version="test",
        commit="deadbeef",
        build_time="2026-01-01T00:00:00Z",
    )


@pytest.fixture
def no_cache_settings(settings: Settings) -> Settings:
    from dataclasses import replace

    return replace(settings, cache_ttl_seconds=0)


def finna_search_response(records: list[dict]) -> dict:
    return {"resultCount": len(records), "records": records, "status": "OK"}


@pytest.fixture
def book_record() -> dict:
    return {
        "id": "helka.993408423506253",
        "title": "Hytti nro 6",
        "subTitle": "romaani",
        "authors": {
            "primary": {"Liksom, Rosa": {"role": ["kirjoittaja"]}},
            "secondary": [],
            "corporate": [],
        },
        "year": "2011",
        "publishers": ["WSOY"],
        "languages": ["fin"],
        "formats": [
            {"value": "0/Book/", "translated": "Kirja"},
            {"value": "1/Book/Book/", "translated": "Kirja"},
        ],
        "images": ["/Cover/Show?source=Solr&id=helka.993408423506253&index=0&size=large"],
        "cleanIsbn": "9510392650",
        "isbns": ["978-951-0-39265-2"],
    }
