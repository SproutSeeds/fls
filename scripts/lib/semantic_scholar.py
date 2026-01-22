"""
Semantic Scholar API client (Graph API).

Docs:
  https://api.semanticscholar.org/api-docs/graph
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


def query(query: str, limit: int = 20, delay_seconds: float = 1.0, raise_on_error: bool = False) -> list:
    """Query Semantic Scholar API (paper/search)."""
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"

    params = {
        "query": query,
        "limit": limit,
        "fields": "paperId,title,abstract,authors,year,citationCount,isOpenAccess,openAccessPdf,externalIds,url",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    headers = {}
    api_key = os.environ.get("FLS_SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key

    try:
        time.sleep(delay_seconds)
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = []
        for paper in data.get("data", []):
            authors = [a.get("name", "") for a in paper.get("authors", [])]
            external_ids = paper.get("externalIds") or {}
            doi = external_ids.get("DOI") or external_ids.get("doi") or ""
            results.append(
                {
                    "s2_id": paper.get("paperId", ""),
                    "s2_url": paper.get("url", "") or "",
                    "doi": doi,
                    "title": paper.get("title", ""),
                    "abstract": paper.get("abstract", "") or "",
                    "authors": authors,
                    "year": str(paper.get("year", "")),
                    "citations": paper.get("citationCount", 0),
                    "is_open_access": paper.get("isOpenAccess", False),
                    "open_access_pdf": paper.get("openAccessPdf", {}).get("url") if paper.get("openAccessPdf") else None,
                    "source": "semantic_scholar",
                }
            )

        return results

    except urllib.error.HTTPError as e:
        if raise_on_error:
            raise
        print(f"  Semantic Scholar query failed: HTTP Error {e.code}: {e.reason}")
        return []
    except Exception as e:
        if raise_on_error:
            raise
        print(f"  Semantic Scholar query failed: {e}")
        return []


def query_all(config: dict) -> list:
    """Query Semantic Scholar with configured keywords."""
    all_results = {}
    delay_seconds = config.get("s2_delay_seconds", 1.0)
    max_results = config.get("max_results_per_source", 20)

    primary = config.get("primary_keywords", [])
    queries = [" ".join(primary[:3])]  # Combine first 3 keywords

    for q in queries:
        if not q.strip():
            continue
        print(f"  Querying: {q}")
        results = query(q, max_results, delay_seconds)
        for r in results:
            if r.get("s2_id") and r["s2_id"] not in all_results:
                all_results[r["s2_id"]] = r

    print(f"  Found {len(all_results)} unique papers")
    return list(all_results.values())
