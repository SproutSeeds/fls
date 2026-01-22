#!/usr/bin/env python3
"""
Unpaywall API helper (for FLS)

USAGE:
  # DOI lookup
  python3 scripts/unpaywall_query.py doi 10.1038/nature12373 --email you@yourdomain.com
  python3 scripts/unpaywall_query.py doi 10.1038/nature12373 --best-pdf

  # Title search
  python3 scripts/unpaywall_query.py search "cell thermometry" --is-oa true --page 1

AUTH:
  Unpaywall requires requests include an email query parameter.
  Provide it via --email or env var FLS_UNPAYWALL_EMAIL.
"""

import argparse
import json
import sys
import urllib.error

from lib import dotenv, unpaywall


def main() -> int:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="Unpaywall API helper (for FLS)")
    parser.add_argument("--email", help="Email for Unpaywall API (or set FLS_UNPAYWALL_EMAIL)")
    parser.add_argument("--delay-seconds", type=float, default=0.0, help="Delay before request (rate limiting)")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    sub = parser.add_subparsers(dest="cmd", required=True)

    p_doi = sub.add_parser("doi", help="Lookup a DOI record")
    p_doi.add_argument("doi", help="DOI to look up")
    p_doi.add_argument("--best-pdf", action="store_true", help="Print only the best PDF URL (if available)")

    p_search = sub.add_parser("search", help="Title search (Unpaywall /v2/search)")
    p_search.add_argument("query", help="Query string (title search)")
    p_search.add_argument(
        "--is-oa",
        choices=["true", "false", "any"],
        default="any",
        help="Filter to OA/non-OA results (default: any)",
    )
    p_search.add_argument("--page", type=int, default=1, help="Page number (1-based, default: 1)")

    args = parser.parse_args()
    email = unpaywall.resolve_email(cli_email=args.email)
    if not email:
        print("ERROR: Unpaywall requires an email. Provide --email or set FLS_UNPAYWALL_EMAIL.", file=sys.stderr)
        return 2

    try:
        if args.cmd == "doi":
            data = unpaywall.doi_lookup(args.doi, email, delay_seconds=args.delay_seconds)
            if args.best_pdf:
                pdf_url = unpaywall.select_best_pdf_url(data)
                if pdf_url:
                    print(pdf_url)
                    return 0
                return 1
        else:
            data = unpaywall.title_search(
                args.query,
                email,
                is_oa=args.is_oa,
                page=args.page,
                delay_seconds=args.delay_seconds,
            )

        indent = 2 if args.pretty else None
        print(json.dumps(data, indent=indent))
        return 0

    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        msg = f"HTTP Error {e.code}: {e.reason}"
        if body:
            msg += f"\n{body}"
        print(msg, file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
