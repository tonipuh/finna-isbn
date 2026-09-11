# finna-isbn

Stateless HTTP microservice that resolves an **ISBN** to a normalized book record
using the **Finna** open REST API (National Library of Finland). It hides Finna's
quirks behind a stable, versioned contract.

The only thing consumers depend on is the **GHCR image + its documented port/env/contract**
— see [SPEC.md](SPEC.md).

## Image

```
ghcr.io/tonipuh/finna-isbn:<tag>   # multi-arch: linux/amd64 + linux/arm64
```

Tags: `v1.0.0`, `v1.0`, `v1`, `latest`. Pin an exact tag in production.

## Run

```bash
docker run --rm -p 8080:8080 \
  -e FINNA_USER_AGENT="finna-isbn/1.0 (+https://github.com/tonipuh/finna-isbn)" \
  ghcr.io/tonipuh/finna-isbn:v1
```

`FINNA_USER_AGENT` is the only required variable.

## API

| Method & path | Description |
|---------------|-------------|
| `GET /v1/isbn/{isbn}` | Resolve an ISBN-10/13 (hyphens/spaces allowed). `?raw=true` appends the original Finna record. |
| `GET /healthz` | Liveness → `200 {"status":"ok"}` |
| `GET /readyz` | Readiness → `200` if Finna reachable, else `503` |
| `GET /version` | `{"version","commit","buildTime"}` |
| `GET /openapi.json` | OpenAPI spec |

### Example

```bash
curl -s "http://localhost:8080/v1/isbn/978-951-0-39265-2" | jq
```

```json
{
  "isbn13": "9789510392652",
  "isbn10": "9510392650",
  "title": "Hytti nro 6",
  "subtitle": null,
  "authors": ["Liksom, Rosa"],
  "year": 2011,
  "publisher": "WSOY",
  "languages": ["fin"],
  "formats": ["Kirja"],
  "cover_url": "https://www.finna.fi/Cover/Show?isbn=9789510392652&size=large",
  "finna_url": "https://www.finna.fi/Record/<id>",
  "finna_id": "<id>",
  "source": "finna"
}
```

### Errors (JSON body for all)

| HTTP | `error` | When |
|------|---------|------|
| 400 | `invalid_isbn` | ISBN fails length/checksum |
| 404 | `not_found` | No Finna match |
| 502 | `upstream_error` | Finna errored / invalid response |
| 504 | `upstream_timeout` | Finna did not respond within `REQUEST_TIMEOUT_SECONDS` |

## Configuration (env)

| Variable | Default | Description |
|----------|---------|-------------|
| `HTTP_PORT` | `8080` | Listen port |
| `FINNA_BASE_URL` | `https://api.finna.fi/v1` | Finna REST base |
| `FINNA_USER_AGENT` | *(required)* | Descriptive User-Agent |
| `FINNA_LANGUAGE` | `fin` | Language filter (empty = all) |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Upstream timeout |
| `CACHE_TTL_SECONDS` | `86400` | ISBN cache TTL (`0` = off) |
| `CACHE_MAX_ENTRIES` | `10000` | In-memory cache cap |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warn`/`error` |

## How it talks to Finna

- Search: `GET {FINNA_BASE_URL}/search?lookfor=<isbn13>&type=ISN&field[]=…&limit=5&lng=<lang>`
  (`type=ISN` is VuFind's ISBN/ISSN search, verified against the live API).
- Best-match selection: among the results, prefer a record whose `cleanIsbn`/`isbns`
  matches the queried ISBN and whose format is a printed book; fall back to the first result.
- Cover: use the record's `images[]` (relative → prefixed with `https://www.finna.fi`)
  when present, otherwise `https://www.finna.fi/Cover/Show?isbn=<isbn13>&size=large`.
- Metadata is licensed CC0; no API key or registration required. A descriptive
  User-Agent is expected.

## Development

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check app tests

# Run locally
FINNA_USER_AGENT="finna-isbn/dev (+https://github.com/tonipuh/finna-isbn)" python -m app
```

## CI/CD

`.github/workflows/build.yml` runs lint + tests, then builds and pushes a multi-arch
image to GHCR on pushes to `main` (`:latest`) and on `v*` tags (`:v1.0.0`, `:v1.0`, `:v1`).
Build injects `version`/`commit`/`buildTime` (exposed at `/version`).
