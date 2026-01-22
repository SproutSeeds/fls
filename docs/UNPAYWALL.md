# Unpaywall REST API (Open-Access Lookup + Title Search Notes)

FLS can optionally use the **Unpaywall REST API** to:

- Find an **open-access PDF** (or landing page) for a known DOI.
- Run **title-based research queries** (Unpaywall search endpoint) to discover relevant DOI records.

Official product page: https://unpaywall.org/products/api

---

## Authentication / Identification (Required)

Unpaywall requests must include an `email` query parameter:

```text
https://api.unpaywall.org/v2/<doi>?email=YOUR_EMAIL
```

FLS supports this via:

- Config: `unpaywall_email`
- Env var: `FLS_UNPAYWALL_EMAIL`

Note: Unpaywall enforces this and may reject placeholder emails (use a real email you control).

Unpaywall does **not** require an API key or account signup for this REST API; the `email` parameter is the primary requirement.

---

## Rate Limits

Unpaywall asks clients to limit usage to **100,000 calls/day**. If you need more/faster access, consider the Unpaywall database snapshot for local querying.

---

## Endpoints

### 1) DOI lookup: `GET /v2/:doi`

**Use case:** given a DOI, get OA status + bibliographic info + OA locations.

Example:

```bash
curl "https://api.unpaywall.org/v2/10.1038/nature12373?email=YOUR_EMAIL"
```

Returns a **DOI Object** (schema is shared across the API + snapshot + data feed). Full schema reference:
https://unpaywall.org/data-format

**Fields FLS typically cares about:**

- `is_oa` (boolean): whether Unpaywall found any OA location.
- `oa_status` (string): Unpaywall “OA color” (e.g., `gold`, `hybrid`, `bronze`, `green`).
- `best_oa_location` (object|null): “best” OA location (prioritizes publisher-hosted first, then closer-to-VOR versions, then more authoritative repos).
- `best_oa_location.url_for_pdf` (string|null): direct PDF URL when available.
- `best_oa_location.url_for_landing_page` (string|null): landing page URL.
- `oa_locations` (array): all OA locations (each an “OA Location Object”).

Useful OA location fields you may want to inspect when picking a download URL:

- `host_type` (e.g., `publisher` vs `repository`)
- `version` (e.g., `publishedVersion`, `acceptedVersion`, `submittedVersion`)
- `license`
- `evidence` (how the OA status was determined)
- `url`, `url_for_pdf`, `url_for_landing_page`

### 2) Title search: `GET /v2/search`

**Use case:** title-based research discovery; returns full DOI lookup responses for matching titles.

Important: in local tests on **2026-01-22**, `GET /v2/search` returned HTTP 500 (server error). Keep this endpoint as a “nice-to-have”; for discovery, Semantic Scholar is usually more reliable.

Request shape:

```text
GET /v2/search?query=<your_query>[&is_oa=true|false][&page=1..]&email=YOUR_EMAIL
```

Example:

```bash
curl "https://api.unpaywall.org/v2/search?query=cell%20thermometry&is_oa=true&email=YOUR_EMAIL"
```

**What it searches:** titles only (not authors, abstracts, etc.). Results include:

- `results[]` where each item contains:
  - `response`: the full DOI Object (same as `/v2/:doi`)
  - `score`: ranking score
  - `snippet`: **HTML-formatted** match snippet (treat as untrusted if displaying)
- `elapsed_seconds`

**Query syntax notes (title search):**

- Terms separated by whitespace are **AND**’d by default (title must contain all terms).
- `"quoted phrases"` require an exact phrase match.
- `OR` switches to OR logic between terms.
- `-term` excludes titles containing `term`.

---

## How FLS Uses Unpaywall

When enabled and a DOI is available, FLS uses Unpaywall as an **open-access PDF fallback**:

1. Try arXiv PDF (if `arxiv_id` exists).
2. Try Semantic Scholar `openAccessPdf.url` (when present).
3. If still missing and DOI is present, call Unpaywall and download `best_oa_location.url_for_pdf` (or another `oa_locations[].url_for_pdf` if needed).

To enable:

- Set `unpaywall_email` in your `fls_config.json`, export `FLS_UNPAYWALL_EMAIL`, or put it in `.env.local` (auto-loaded).

---

## Handy CLI (Optional)

This repo also includes a small helper script for interactive lookups:

```bash
# DOI lookup (prints full JSON)
python3 scripts/unpaywall_query.py doi 10.1038/nature12373 --pretty --email YOU@DOMAIN.COM

# DOI lookup (prints just the “best” PDF URL, if any)
python3 scripts/unpaywall_query.py doi 10.1038/nature12373 --best-pdf --email YOU@DOMAIN.COM

# Title search
python3 scripts/unpaywall_query.py search "cell thermometry" --is-oa true --page 1 --pretty --email YOU@DOMAIN.COM
```
