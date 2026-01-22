#!/usr/bin/env python3
"""
Smoke-test the local RAG index/query flow (no network calls).

This creates a temporary project workspace with:
  - fls_config.json
  - LITERATURE_WORLD_MODEL.md
  - literature_notes.json
  - papers/papers_manifest.json

Then runs:
  - scripts/rag_index.py
  - scripts/rag_query.py (JSON output)
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    rag_index = repo_root / "scripts" / "rag_index.py"
    rag_query = repo_root / "scripts" / "rag_query.py"

    needle = "Frontier Research is possible at any given moment."

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "papers").mkdir(parents=True, exist_ok=True)
        (root / "rag").mkdir(parents=True, exist_ok=True)

        (root / "LITERATURE_WORLD_MODEL.md").write_text(f"# WM\n\n{needle}\n", encoding="utf-8")
        (root / "literature_notes.json").write_text(
            json.dumps({"schema_version": 1, "notes": {"X": {"summary": needle}}}, indent=2),
            encoding="utf-8",
        )
        (root / "papers" / "papers_manifest.json").write_text("[]\n", encoding="utf-8")

        config = {
            "download_dir": "papers",
            "manifest_file": "papers/papers_manifest.json",
            "world_model_file": "LITERATURE_WORLD_MODEL.md",
            "notes_file": "literature_notes.json",
            "rag_index_db": "rag/rag_index.sqlite",
            "rag_chunk_chars": 500,
            "rag_chunk_overlap_chars": 50,
            "sources": {"arxiv": False, "semantic_scholar": False, "oeis": False},
        }
        (root / "fls_config.json").write_text(json.dumps(config, indent=2), encoding="utf-8")

        p1 = run([sys.executable, str(rag_index), "--config", "fls_config.json"], cwd=root)
        if p1.returncode != 0:
            print("FAIL rag_index.py")
            print(p1.stdout)
            print(p1.stderr, file=sys.stderr)
            return 1

        p2 = run([sys.executable, str(rag_query), "--config", "fls_config.json", "--json", "Frontier Research"], cwd=root)
        if p2.returncode != 0:
            print("FAIL rag_query.py")
            print(p2.stdout)
            print(p2.stderr, file=sys.stderr)
            return 1

        try:
            data = json.loads(p2.stdout)
        except Exception as e:
            print("FAIL rag_query.py JSON parse")
            print(e)
            print(p2.stdout)
            return 1

        results = data.get("results") or []
        if not results:
            print("FAIL no results")
            print(p2.stdout)
            return 1

        joined = "\n".join([(r.get("snippet") or "") + "\n" + (r.get("content") or "") for r in results])
        if "Frontier" not in joined:
            print("FAIL expected text not found in results")
            print(p2.stdout)
            return 1

        print("OK RAG smoke test passed")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

