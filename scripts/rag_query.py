#!/usr/bin/env python3
"""
FLS — Local RAG Query (free + offline)

Queries the local SQLite index created by `scripts/rag_index.py`.

USAGE:
  python3 scripts/rag_query.py --config fls_config.json "sunflower bound"
  python3 scripts/rag_query.py --config fls_config.json --type pdf "Naslund Sawin"
  python3 scripts/rag_query.py --config fls_config.json --json "delta-system"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lib import dotenv, rag_db


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    with open(path) as f:
        return json.load(f)


def format_hit(hit: dict) -> str:
    path = hit.get("path", "?")
    doc_type = hit.get("doc_type", "?")
    page = hit.get("page")
    chunk = hit.get("chunk_index")
    rank = hit.get("rank")
    snippet = hit.get("snippet", "")

    loc = f"{path}"
    if page is not None:
        loc += f":p{page}"
    if chunk is not None:
        loc += f":c{chunk}"

    return f"- ({doc_type}) {loc}  rank={rank:.4f}\n  {snippet}"


def main() -> int:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="FLS local RAG query (SQLite FTS)")
    parser.add_argument("--config", "-c", required=True, help="Path to config JSON file")
    parser.add_argument("--db", default="", help="Override DB path (default: config rag_index_db)")
    parser.add_argument("--top-k", type=int, default=8, help="Number of results to return")
    parser.add_argument("--type", default="", help="Filter by doc type (pdf, md, json, py, ...)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--content", action="store_true", help="Include full chunk content (JSON output only)")
    parser.add_argument("query", help="Search query (FTS syntax when available)")
    args = parser.parse_args()

    config = load_config(args.config)
    db_path = Path(args.db or config.get("rag_index_db", "rag/rag_index.sqlite"))
    if not db_path.exists():
        print(f"ERROR: RAG index DB not found: {db_path}")
        print("Run: python3 scripts/rag_index.py --config fls_config.json")
        return 2

    conn = rag_db.connect(db_path)
    rag_db.ensure_schema(conn)

    hits = rag_db.search(
        conn,
        args.query,
        limit=args.top_k,
        doc_type=args.type,
        include_content=args.content,
    )

    if args.json:
        out = {"query": args.query, "db": str(db_path), "results": hits}
        print(json.dumps(out, indent=2))
        return 0

    print(f"Query: {args.query}")
    print(f"DB: {db_path}")
    if args.type:
        print(f"Filter: doc_type={args.type}")
    print(f"Results: {len(hits)}")
    for h in hits:
        print(format_hit(h))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

