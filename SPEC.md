# Määrittely: `finna-isbn` — ISBN→metadata-mikropalvelu (Finna)

> Itsenäinen määrittely. Toteutetaan omassa repossaan `github.com/tonipuh/finna-isbn`
> täysin erillisessä ympäristössä. **Ainoa kytkös ulkomaailmaan on GHCR-image +
> sen dokumentoitu portti/env/kontrakti** — kaikki muu on tässä dokumentissa.

## 1. Tarkoitus
Stateless HTTP-mikropalvelu joka ottaa ISBN:n, kysyy **Finnan avoimesta REST-API:sta**
(Suomen kansalliskirjaston hakupalvelu) ja palauttaa **normalisoidun kirjatietueen**
+ linkin Finna-tietueeseen. Eristää Finnan API:n kummallisuudet vakaan, versioidun
kontraktin taakse.

## 2. Scope
**Mukana (v1):** ISBN-haku (ISBN-10 ja -13), normalisoitu JSON, kansikuva-URL,
Finna-record-URL, terveys/versio-endpointit, valinnainen cache.
**Ei mukana (v1):** nimellä/tekijällä haku (varaa `/v1/search` tulevaisuuteen),
kirjautuminen, kirjoitusoperaatiot, tietokanta (paitsi valinnainen in-memory-cache).

## 3. Toimitus = integraatiokontrakti
Ainoa asia jonka ulkomaailma (mm. IaC-deploy) kuluttaa:
- **Repo:** `github.com/tonipuh/finna-isbn`
- **Image:** `ghcr.io/tonipuh/finna-isbn:<tag>` — **multi-arch (linux/amd64 + linux/arm64)**, julkinen paketti.
- **Tagit:** semver (`v1.0.0`, `v1.0`, `v1`) **+** `latest`. Kuluttaja pinnaa tarkan tagin.
- **Portti:** kontti kuuntelee **HTTP :8080** (ei TLS:ää — reverse proxy hoitaa sen kuluttajan puolella).
- Kontti on **stateless** ja konfiguroidaan **pelkillä env-muuttujilla** (§6). Ei kirjautumista GHCR:ään tarvita (julkinen image).

## 4. HTTP-API (kontrakti — pidä vakaana, versioi polku)

### `GET /v1/isbn/{isbn}`
`{isbn}` saa sisältää väliviivoja/välilyöntejä (normalisoidaan). Palauttaa parhaan osuman.

**200 OK**
```json
{
  "isbn13": "9789511234567",
  "isbn10": "9511234567",
  "title": "Kirjan nimi",
  "subtitle": null,
  "authors": ["Sukunimi, Etunimi"],
  "year": 2020,
  "publisher": "Kustantaja",
  "languages": ["fin"],
  "formats": ["Book"],
  "cover_url": "https://…/Cover/Show?...",
  "finna_url": "https://www.finna.fi/Record/<finna_id>",
  "finna_id": "<finna_id>",
  "source": "finna"
}
```
- Kentät joita ei löydy → `null` (skalaarit) tai `[]` (listat). `cover_url` = `null` jos ei kantta.
- `?raw=true` → lisää `"raw": { …Finnan alkuperäinen record… }` (debuggaukseen).

**Virheet (JSON-body kaikille):**
```json
{ "error": "not_found", "message": "No Finna record for ISBN", "isbn": "9789511234567" }
```

| HTTP | `error` | Milloin |
|------|---------|---------|
| 400 | `invalid_isbn` | ISBN ei ole validi (checksum/pituus) |
| 404 | `not_found` | Finna ei palauta osumaa |
| 502 | `upstream_error` | Finna vastaa virheellä / epävalidilla |
| 504 | `upstream_timeout` | Finna ei vastaa `REQUEST_TIMEOUT_SECONDS`:issa |

### `GET /healthz` → `200 {"status":"ok"}` (liveness, ei ulkokutsuja)
### `GET /readyz` → `200` jos Finna tavoitettavissa, muuten `503` (valinnainen kevyt ping/cache)
### `GET /version` → `{"version":"v1.0.0","commit":"<sha>","buildTime":"<iso8601>"}`
### `GET /openapi.json` → palvelun oma OpenAPI-speksi (suositus)

## 5. Finna-integraatio (ulkoinen riippuvuus — ainoa)
- **Avoin REST, ei API-avainta.** Base: `https://api.finna.fi/v1`. OpenAPI:
  `https://api.finna.fi/api/v1/?openapi`, Swagger: `https://api.finna.fi/v1/`.
  **Toteuttaja: varmista tarkat kenttä-/parametrinimet tästä OpenAPI:sta.**
- **Haku (varmistettava tyyppi):**
  ```
  GET https://api.finna.fi/v1/search
      ?lookfor=<normalisoitu ISBN>
      &type=ISN                # VuFind ISBN/ISSN-haku — VERIFIOI OpenAPI:sta
      &field[]=id&field[]=title&field[]=shortTitle&field[]=authors
      &field[]=year&field[]=publishers&field[]=languages&field[]=formats
      &field[]=images&field[]=cleanIsbn
      &limit=1&lng=fi
  ```
- **Record-URL:** `https://www.finna.fi/Record/<id>` (URL-enkoodaa `id`).
- **Kansikuva:** joko record-vastauksen `images[]` (suhteellinen polku → etuliite
  `https://www.finna.fi`) TAI Finnan cover-API
  `https://api.finna.fi/Cover/Show?isbn=<isbn13>&size=large`. **Verifioi kumpi antaa
  vakaan absoluuttisen URL:n**; palauta absoluuttinen.
- **User-Agent pakollinen ja kuvaava:** esim.
  `finna-isbn/<version> (+https://github.com/tonipuh/finna-isbn)`. Finna toivoo
  tunnistettavaa UA:ta.
- **Kohteliaisuus:** yksi haku per pyyntö, cache (§7), älä hakkaa.

## 6. Konfiguraatio (env)
| Muuttuja | Oletus | Selitys |
|----------|--------|---------|
| `HTTP_PORT` | `8080` | Kuunteluportti |
| `FINNA_BASE_URL` | `https://api.finna.fi/v1` | Finna REST base |
| `FINNA_USER_AGENT` | *(pakollinen)* | Kuvaava UA |
| `FINNA_LANGUAGE` | `fin` | Kielisuodatus (tyhjä = kaikki) |
| `REQUEST_TIMEOUT_SECONDS` | `10` | Upstream-timeout |
| `CACHE_TTL_SECONDS` | `86400` | ISBN-cache TTL (`0` = pois) |
| `CACHE_MAX_ENTRIES` | `10000` | In-memory-cachen katto |
| `LOG_LEVEL` | `info` | `debug`/`info`/`warn`/`error` |

## 7. Ei-toiminnalliset vaatimukset
- **Stateless.** Cache **vain in-memory** (LRU + TTL) — ei ulkoista tietokantaa
  (pidä deploy triviaalina). Cache-miss ok aina.
- **ISBN-käsittely:** poista väliviivat/välilyönnit; validoi ISBN-10 ja -13 checksum;
  muunna 10↔13; hae Finnasta ISBN-13:lla mutta palauta molemmat.
- **Lokitus:** **structured JSON** stdoutiin (taso, viesti, isbn, finna_status, kesto,
  cache hit/miss). Ei PII.
- **Vaste** healthy-tilassa < ~1.5 s (cache-miss, Finnasta riippuen); cache-hit < 10 ms.
- **Graceful shutdown** SIGTERM:llä.

## 8. Kontti / build
- **Non-root**-käyttäjä, minimaalinen base (esim. distroless / alpine), `EXPOSE 8080`.
- **HEALTHCHECK** → `GET /healthz`.
- **Multi-arch build** (amd64 + arm64).
- Stack vapaa (esim. Go, tai Python/FastAPI, tai Node) — kontrakti + paketointi
  ratkaisee, ei kieli. Suositus: kevyt, nopea kylmäkäynnistys.

## 9. CI/CD
- **GitHub Actions:** buildaa + pushaa `ghcr.io/tonipuh/finna-isbn` pushissa `main`iin
  (`:latest`) ja gitin tagilla (`:v1.0.0`, `:v1.0`, `:v1`). Multi-arch `docker buildx`.
- Injektoi `version`/`commit`/`buildTime` buildissa (`/version`-endpointille).
- Julkinen GHCR-paketti (ei tarvitse tokenia vetoon).

## 10. Hyväksymiskriteerit (testicaset)
1. Validi ISBN-13 (löytyy Finnasta) → `200` + `title`, `authors`, `finna_url`, `cover_url`.
2. Sama kirja ISBN-10:llä ja väliviivoilla → sama tulos.
3. Tuntematon mutta validi ISBN → `404 not_found`.
4. Epävalidi ISBN → `400 invalid_isbn`.
5. Finna alhaalla / timeout → `502`/`504` (ei kaadu).
6. `/healthz` → `200`; `/version` → build-tiedot.
7. Cache: toinen sama pyyntö → `cache hit`, < 10 ms.
8. Kontti käynnistyy pelkillä env-oletuksilla (paitsi `FINNA_USER_AGENT`).

## 11. Kuluttajakonteksti (miksi kontrakti on tärkeä — ei toteuteta tässä)
Palvelua kutsuu HTTP:llä (a) itse-hostattu **kirjakatalogisofta metadata-providerina**
ja/tai (b) **oma mobiiliappi** (viivakoodiskannaus → tämä palvelu → kirjoittaa
katalogiin), ja se **deployataan erillisessä IaC-repossa pelkän GHCR-imagen + envin
kautta**. Siksi: **vakaa versioitu kontrakti, stateless, env-konffi, health** — ei
oletuksia kuluttajan sisäisistä. Älä lisää sitovia riippuvuuksia (esim. tiettyä DB:tä)
jotka monimutkaistaisivat deployta.

## 12. Varmistettavat (toteuttajan tehtävä ennen lukitusta)
- Finnan tarkka **ISBN-hakutyyppi** (`type=ISN`?) ja **kenttänimet** OpenAPI:sta.
- **Kansikuvan** vakain lähde (record `images` vs `Cover/Show`).
- Rate-limitit / suositellut käyttöehdot Finnan dokumentaatiosta.
