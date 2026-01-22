"""
Unpaywall REST API helpers.

Docs:
  https://unpaywall.org/products/api
  https://unpaywall.org/data-format

Unpaywall requests must include an `email` query parameter.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from typing import Optional


DEFAULT_USER_AGENT = "FLS (Frontier Literature Scanner)"


def resolve_email(*, config: Optional[dict] = None, cli_email: str = "") -> str:
    """Resolve Unpaywall email from CLI, config, or environment."""
    email = (cli_email or "").strip()
    if email:
        return email
    if config:
        email = (config.get("unpaywall_email") or "").strip()
        if email:
            return email
    return (os.environ.get("FLS_UNPAYWALL_EMAIL") or os.environ.get("UNPAYWALL_EMAIL") or "").strip()


def build_doi_url(doi: str, email: str) -> str:
    """Build the Unpaywall DOI endpoint URL."""
    # Keep "/" unescaped (many servers reject encoded slashes in path segments).
    doi_path = urllib.parse.quote((doi or "").strip(), safe="/")
    params = urllib.parse.urlencode({"email": (email or "").strip()})
    return f"https://api.unpaywall.org/v2/{doi_path}?{params}"


def build_search_url(*, query: str, email: str, is_oa: str = "any", page: int = 1) -> str:
    """Build the Unpaywall title search URL."""
    params = {"query": query, "email": email, "page": str(page)}
    if is_oa != "any":
        params["is_oa"] = is_oa
    return f"https://api.unpaywall.org/v2/search?{urllib.parse.urlencode(params)}"


def http_get_json(
    url: str,
    *,
    delay_seconds: float = 0.0,
    timeout_seconds: float = 30.0,
    user_agent: str = DEFAULT_USER_AGENT,
) -> dict:
    """GET JSON from a URL (simple stdlib client)."""
    headers = {"User-Agent": user_agent}
    time.sleep(max(0.0, delay_seconds))
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def doi_lookup(
    doi: str,
    email: str,
    *,
    delay_seconds: float = 0.0,
    timeout_seconds: float = 30.0,
) -> dict:
    """Fetch the Unpaywall DOI Object for a DOI."""
    url = build_doi_url(doi, email)
    return http_get_json(url, delay_seconds=delay_seconds, timeout_seconds=timeout_seconds)


def title_search(
    query: str,
    email: str,
    *,
    is_oa: str = "any",
    page: int = 1,
    delay_seconds: float = 0.0,
    timeout_seconds: float = 30.0,
) -> dict:
    """Search titles and return results with embedded DOI Objects."""
    url = build_search_url(query=query, email=email, is_oa=is_oa, page=page)
    return http_get_json(url, delay_seconds=delay_seconds, timeout_seconds=timeout_seconds)


def select_best_pdf_url(doi_obj: dict) -> Optional[str]:
    """Pick a PDF URL from a Unpaywall DOI Object, preferring best_oa_location."""
    best = doi_obj.get("best_oa_location") or {}
    url = best.get("url_for_pdf")
    if url:
        return url

    for loc in doi_obj.get("oa_locations", []) or []:
        url = (loc or {}).get("url_for_pdf")
        if url:
            return url

    return None
