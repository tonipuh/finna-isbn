import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app

from .conftest import finna_search_response

SEARCH_URL = "https://api.finna.fi/v1/search"


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def nocache_client(no_cache_settings):
    app = create_app(no_cache_settings)
    with TestClient(app) as c:
        yield c


# --- Acceptance criterion 1: valid ISBN-13 found -> 200 with core fields ---
@respx.mock
def test_valid_isbn13_found(client, book_record):
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=finna_search_response([book_record]))
    )
    r = client.get("/v1/isbn/9789510392652")
    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Hytti nro 6"
    assert body["authors"] == ["Liksom, Rosa"]
    assert body["finna_url"] == "https://www.finna.fi/Record/helka.993408423506253"
    assert body["cover_url"]
    assert body["isbn13"] == "9789510392652"
    assert body["isbn10"] == "9510392650"


# --- Acceptance criterion 2: same book via ISBN-10 + hyphens -> same result ---
@respx.mock
def test_isbn10_with_hyphens_same_result(client, book_record):
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=finna_search_response([book_record]))
    )
    r = client.get("/v1/isbn/951-0-39265-0")
    assert r.status_code == 200
    body = r.json()
    assert body["isbn13"] == "9789510392652"
    assert body["title"] == "Hytti nro 6"


# --- Acceptance criterion 3: unknown but valid ISBN -> 404 not_found ---
@respx.mock
def test_unknown_isbn_not_found(client):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=finna_search_response([])))
    r = client.get("/v1/isbn/9789510392652")
    assert r.status_code == 404
    assert r.json()["error"] == "not_found"


# --- Acceptance criterion 4: invalid ISBN -> 400 invalid_isbn ---
def test_invalid_isbn(client):
    r = client.get("/v1/isbn/1234567890")
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_isbn"


# --- Acceptance criterion 5: Finna down / timeout -> 502 / 504 (no crash) ---
@respx.mock
def test_upstream_error(nocache_client):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(500))
    r = nocache_client.get("/v1/isbn/9789510392652")
    assert r.status_code == 502
    assert r.json()["error"] == "upstream_error"


@respx.mock
def test_upstream_timeout(nocache_client):
    respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))
    r = nocache_client.get("/v1/isbn/9789510392652")
    assert r.status_code == 504
    assert r.json()["error"] == "upstream_timeout"


# --- Acceptance criterion 6: /healthz and /version ---
def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_version(client):
    r = client.get("/version")
    assert r.status_code == 200
    body = r.json()
    assert body["version"] == "test"
    assert body["commit"] == "deadbeef"
    assert body["buildTime"] == "2026-01-01T00:00:00Z"


# --- Acceptance criterion 7: second request is a cache hit (single upstream call) ---
@respx.mock
def test_cache_hit_only_one_upstream_call(client, book_record):
    route = respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=finna_search_response([book_record]))
    )
    r1 = client.get("/v1/isbn/9789510392652")
    r2 = client.get("/v1/isbn/9789510392652")  # ISBN-10 normalizes to same key
    r3 = client.get("/v1/isbn/951-0-39265-0")
    assert r1.status_code == r2.status_code == r3.status_code == 200
    assert route.call_count == 1  # subsequent lookups served from cache


# --- readyz ---
@respx.mock
def test_readyz_ok(client):
    respx.get(SEARCH_URL).mock(return_value=httpx.Response(200, json=finna_search_response([])))
    r = client.get("/readyz")
    assert r.status_code == 200


@respx.mock
def test_readyz_unavailable(nocache_client):
    respx.get(SEARCH_URL).mock(side_effect=httpx.ConnectError("down"))
    r = nocache_client.get("/readyz")
    assert r.status_code == 503


# --- raw passthrough ---
@respx.mock
def test_raw_flag_includes_raw(client, book_record):
    respx.get(SEARCH_URL).mock(
        return_value=httpx.Response(200, json=finna_search_response([book_record]))
    )
    r = client.get("/v1/isbn/9789510392652?raw=true")
    assert r.status_code == 200
    assert r.json()["raw"]["id"] == "helka.993408423506253"

    r2 = client.get("/v1/isbn/9789510392652")
    assert "raw" not in r2.json()


# --- openapi ---
def test_openapi(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert r.json()["info"]["title"] == "finna-isbn"
