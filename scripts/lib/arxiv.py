"""
arXiv API client (Atom feed).

Docs:
  https://info.arxiv.org/help/api/index.html
"""

from __future__ import annotations

import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET


def query(
    query: str,
    categories: list,
    max_results: int = 50,
    delay_seconds: float = 3.0,
    raise_on_error: bool = False,
) -> list:
    """Query the arXiv API and return parsed results."""
    base_url = "http://export.arxiv.org/api/query"

    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    url = f"{base_url}?{urllib.parse.urlencode(params)}"

    try:
        time.sleep(delay_seconds)  # Rate limiting
        with urllib.request.urlopen(url, timeout=30) as response:
            xml_data = response.read().decode("utf-8")

        root = ET.fromstring(xml_data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            published_el = entry.find("atom:published", ns)
            id_el = entry.find("atom:id", ns)

            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text)

            entry_categories = []
            for cat in entry.findall("atom:category", ns):
                if "term" in cat.attrib:
                    entry_categories.append(cat.attrib["term"])

            # Filter by category
            if categories and not any(c in entry_categories for c in categories):
                continue

            arxiv_id = ""
            if id_el is not None and id_el.text:
                arxiv_id = id_el.text.split("/abs/")[-1].split("v")[0]

            results.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else "",
                    "abstract": summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else "",
                    "authors": authors,
                    "published": published_el.text if published_el is not None else "",
                    "categories": entry_categories,
                    "source": "arxiv",
                }
            )

        return results

    except Exception as e:
        if raise_on_error:
            raise
        print(f"  arXiv query failed: {e}")
        return []


def query_all(config: dict) -> list:
    """Query arXiv with all configured keywords."""
    all_results = {}
    categories = config.get("arxiv_categories", [])
    delay_seconds = config.get("arxiv_delay_seconds", 3)
    max_results = config.get("max_results_per_source", 50)

    # Build queries from primary keywords
    queries = config.get("primary_keywords", [])

    for q in queries:
        print(f"  Querying: {q}")
        results = query(q, categories, max_results, delay_seconds)
        for r in results:
            if r.get("arxiv_id") and r["arxiv_id"] not in all_results:
                all_results[r["arxiv_id"]] = r

    print(f"  Found {len(all_results)} unique papers")
    return list(all_results.values())
