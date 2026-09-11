# finna-isbn

Ohut välikerros kirjastosovelluksen (librarian) ja **Finnan** avoimen REST-API:n välissä:
antaa ISBN:n, saat normalisoidun kirjatietueen. Stateless HTTP, konfiguroidaan
env-muuttujilla, jaellaan GHCR-imagena.

## Käyttö

```bash
docker run --rm -p 8080:8080 \
  -e FINNA_USER_AGENT="finna-isbn/1.0 (+https://github.com/tonipuh/finna-isbn)" \
  ghcr.io/tonipuh/finna-isbn:v1
```

`FINNA_USER_AGENT` on ainoa pakollinen muuttuja. Image on multi-arch (amd64 + arm64).

## API

| Metodi & polku | Kuvaus |
|----------------|--------|
| `GET /v1/isbn/{isbn}` | ISBN-10/13 (väliviivat sallittu) → kirjatietue. `?raw=true` lisää alkuperäisen Finna-recordin. |
| `GET /healthz` | Liveness → `200 {"status":"ok"}` |
| `GET /readyz` | `200` jos Finna tavoitettavissa, muuten `503` |
| `GET /version` | `{"version","commit","buildTime"}` |
| `GET /openapi.json` | OpenAPI-speksi |

```bash
curl -s "http://localhost:8080/v1/isbn/978-951-0-39265-2"
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

Virheet (JSON-body): `400 invalid_isbn`, `404 not_found`, `502 upstream_error`, `504 upstream_timeout`.

## Konfiguraatio (env)

| Muuttuja | Oletus | Selitys |
|----------|--------|---------|
| `HTTP_PORT` | `8080` | Kuunteluportti |
| `FINNA_BASE_URL` | `https://api.finna.fi/v1` | Finna REST base |
| `FINNA_USER_AGENT` | *(pakollinen)* | Kuvaava User-Agent |
| `FINNA_LANGUAGE` | `fin` | Kielisuodatus (tyhjä = kaikki) |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Upstream-timeout |
| `CACHE_TTL_SECONDS` | `86400` | ISBN-cache TTL (`0` = pois) |
| `CACHE_MAX_ENTRIES` | `10000` | In-memory-cachen katto |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warn`/`error` |

## Kehitys

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest -q && ruff check app tests

FINNA_USER_AGENT="finna-isbn/dev" python -m app
```

## Toteutus lyhyesti

- Haku: `GET /search?lookfor=<isbn13>&type=ISN&…&limit=5`. Osumista valitaan se, jonka
  ISBN täsmää ja formaatti on kirja; muuten ensimmäinen.
- Kansikuva: recordin `images[]` (→ `https://www.finna.fi`-etuliite) tai fallback
  `Cover/Show?isbn=<isbn13>`.
- ISBN-cache in-memory (LRU+TTL), structured JSON -lokit, graceful shutdown SIGTERM:llä.
- Finnan metadata on CC0; ei API-avainta.

CI ([.github/workflows/build.yml](.github/workflows/build.yml)) ajaa lintin + testit ja
pushaa multi-arch-imagen GHCR:ään: `main` → `:latest`, `v*`-tagi → `:v1.0.0`/`:v1.0`/`:v1`.
