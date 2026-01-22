#!/usr/bin/env python3
"""
Smoke-test the external API modules used by FLS.

This performs minimal live calls against:
  - arXiv
  - Semantic Scholar
  - OEIS
  - Unpaywall

It is intentionally lightweight and avoids any non-stdlib dependencies.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
import urllib.error

from lib import arxiv, dotenv, oeis, semantic_scholar, unpaywall


def ok(msg: str):
    print(f"OK   {msg}")


def warn(msg: str):
    print(f"WARN {msg}")


def fail(msg: str):
    print(f"FAIL {msg}")


def main() -> int:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="FLS API module smoke test (live calls)")
    parser.add_argument(
        "--delay-seconds",
        type=float,
        default=3.0,
        help="Delay before each request (rate limiting). arXiv recommends >= 3 seconds.",
    )
    parser.add_argument("--unpaywall-email", default="", help="Email for Unpaywall (or set FLS_UNPAYWALL_EMAIL)")
    parser.add_argument(
        "--require-unpaywall",
        action="store_true",
        help="Fail if Unpaywall email is not provided via --unpaywall-email or FLS_UNPAYWALL_EMAIL",
    )
    args = parser.parse_args()

    print(f"FLS API smoke test @ {datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')}")
    print("-" * 60)

    failures = 0

    # arXiv
    try:
        results = arxiv.query("sunflower", [], max_results=3, delay_seconds=args.delay_seconds, raise_on_error=True)
        if not isinstance(results, list):
            raise TypeError(f"Expected list, got {type(results)}")
        if results:
            ok(f"arXiv query returned {len(results)} result(s)")
        else:
            warn("arXiv query returned 0 results (unexpected for this smoke test)")
    except Exception as e:
        failures += 1
        fail(f"arXiv query failed: {e}")

    # Semantic Scholar
    try:
        results = semantic_scholar.query("sunflower lemma", limit=1, delay_seconds=args.delay_seconds, raise_on_error=True)
        if not isinstance(results, list):
            raise TypeError(f"Expected list, got {type(results)}")
        if results:
            ok(f"Semantic Scholar query returned {len(results)} result(s) (no API key required, but rate limits may apply)")
        else:
            warn("Semantic Scholar returned 0 results (possible rate limit without an API key)")
    except urllib.error.HTTPError as e:
        if e.code == 429:
            warn("Semantic Scholar rate limited (HTTP 429). This is common without an API key.")
        else:
            failures += 1
            fail(f"Semantic Scholar query failed: HTTP Error {e.code}: {e.reason}")
    except Exception as e:
        failures += 1
        fail(f"Semantic Scholar query failed: {e}")

    # OEIS
    try:
        results = oeis.query([1, 1, 2, 3, 5, 8], delay_seconds=args.delay_seconds, raise_on_error=True)
        if not isinstance(results, list):
            raise TypeError(f"Expected list, got {type(results)}")
        if results:
            ok(f"OEIS query returned {len(results)} result(s)")
        else:
            failures += 1
            fail("OEIS query returned 0 results (unexpected for this smoke test)")
    except Exception as e:
        failures += 1
        fail(f"OEIS query failed: {e}")

    # Unpaywall
    email = unpaywall.resolve_email(cli_email=args.unpaywall_email)
    if not email:
        msg = "Unpaywall test skipped (set FLS_UNPAYWALL_EMAIL or pass --unpaywall-email)"
        if args.require_unpaywall:
            failures += 1
            fail(msg)
        else:
            warn(msg)
    else:
        try:
            doi_obj = unpaywall.doi_lookup("10.1038/nature12373", email, delay_seconds=args.delay_seconds)
            if not isinstance(doi_obj, dict) or not doi_obj:
                raise TypeError("Expected non-empty dict response")

            doi_value = doi_obj.get("doi") or doi_obj.get("DOI") or ""
            best_pdf = unpaywall.select_best_pdf_url(doi_obj)
            ok(f"Unpaywall DOI lookup returned doi={doi_value!r} best_pdf={'yes' if best_pdf else 'no'}")
        except Exception as e:
            failures += 1
            fail(f"Unpaywall lookup failed: {e}")

    print("-" * 60)
    if failures:
        fail(f"{failures} test(s) failed")
        return 1

    ok("All API module smoke tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
