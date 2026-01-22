#!/usr/bin/env python3
"""
FLS — Local RAG Index Builder (free + offline)

Builds/updates a local SQLite search index for:
  - Downloaded PDFs in `download_dir` (default: papers/)
  - World model (`world_model_file`)
  - Manifest (`manifest_file`)
  - Notes (`notes_file`)

Optionally, you can also index your whole repo (markdown/code/etc) for “repo-RAG”.

USAGE:
  python3 scripts/rag_index.py --config fls_config.json
  python3 scripts/rag_index.py --config fls_config.json --include-repo

OUTPUT:
  A SQLite DB (FTS5 when available) at `rag_index_db` (default: rag/rag_index.sqlite)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Iterable, Optional

from lib import dotenv, pdf_text, rag_db


DEFAULT_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    "node_modules",
    "dist",
    "build",
    "rag",
    "papers",  # handled separately (PDFs)
}

TEXT_EXTS = {
    ".md",
    ".txt",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
    ".bash",
}


def load_config(config_path: str) -> dict:
    path = Path(config_path)
    with open(path) as f:
        return json.load(f)


def chunk_text(text: str, *, chunk_chars: int, overlap_chars: int) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    if chunk_chars <= 0:
        return [text]
    overlap_chars = max(0, min(overlap_chars, chunk_chars - 1))

    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(n, start + chunk_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= n:
            break
        start = end - overlap_chars
    return chunks


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def iter_repo_files(root: Path, *, max_bytes: int) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORE_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() == ".pdf":
                continue
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            try:
                if p.stat().st_size > max_bytes:
                    continue
            except Exception:
                continue
            yield p


def read_text_file(path: Path) -> Optional[str]:
    suffix = path.suffix.lower()
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    if suffix == ".json":
        try:
            obj = json.loads(raw)
            return json.dumps(obj, indent=2, sort_keys=True)
        except Exception:
            return raw

    return raw


def index_text_document(
    conn,
    *,
    root: Path,
    path: Path,
    doc_type: str,
    chunk_chars: int,
    overlap_chars: int,
):
    rel = safe_relpath(path, root)
    stat = path.stat()

    existing = rag_db.get_doc(conn, rel)
    if existing and int(existing.get("mtime_ns", -1)) == int(stat.st_mtime_ns) and int(existing.get("size", -1)) == int(
        stat.st_size
    ):
        return "skipped"

    text = read_text_file(path)
    if not text:
        return "empty"

    rag_db.delete_chunks(conn, rel)

    chunks = chunk_text(text, chunk_chars=chunk_chars, overlap_chars=overlap_chars)
    for idx, chunk in enumerate(chunks):
        rag_db.insert_chunk(conn, path=rel, doc_type=doc_type, page=None, chunk_index=idx, content=chunk)

    rag_db.upsert_doc(conn, path=rel, doc_type=doc_type, mtime_ns=stat.st_mtime_ns, size=stat.st_size)
    conn.commit()
    return "indexed"


def index_pdf_document(
    conn,
    *,
    root: Path,
    path: Path,
    ocr_enabled: bool,
    ocr_languages: str,
    ocr_dpi: int,
    chunk_chars: int,
    overlap_chars: int,
):
    rel = safe_relpath(path, root)
    stat = path.stat()

    existing = rag_db.get_doc(conn, rel)
    if existing and int(existing.get("mtime_ns", -1)) == int(stat.st_mtime_ns) and int(existing.get("size", -1)) == int(
        stat.st_size
    ):
        return "skipped"

    pages = pdf_text.extract_pdf_pages_text(
        path,
        ocr_enabled=ocr_enabled,
        ocr_languages=ocr_languages,
        ocr_dpi=ocr_dpi,
    )
    if not pages:
        return "no_pdf_text"

    rag_db.delete_chunks(conn, rel)

    chunk_index = 0
    for page_num, page_text in enumerate(pages, start=1):
        for chunk in chunk_text(page_text, chunk_chars=chunk_chars, overlap_chars=overlap_chars):
            rag_db.insert_chunk(
                conn,
                path=rel,
                doc_type="pdf",
                page=page_num,
                chunk_index=chunk_index,
                content=chunk,
            )
            chunk_index += 1

    rag_db.upsert_doc(conn, path=rel, doc_type="pdf", mtime_ns=stat.st_mtime_ns, size=stat.st_size)
    conn.commit()
    return "indexed"


def main() -> int:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="FLS local RAG index builder (SQLite FTS)")
    parser.add_argument("--config", "-c", required=True, help="Path to config JSON file")
    parser.add_argument("--db", default="", help="Override DB path (default: config rag_index_db)")
    parser.add_argument("--include-repo", action="store_true", help="Also index text/code files in the repo")
    parser.add_argument("--prune", action="store_true", help="Remove indexed files that no longer exist")
    parser.add_argument("--max-text-bytes", type=int, default=2_000_000, help="Max size for repo text files")
    args = parser.parse_args()

    config = load_config(args.config)

    root = Path.cwd()
    db_path = Path(args.db or config.get("rag_index_db", "rag/rag_index.sqlite"))
    chunk_chars = int(config.get("rag_chunk_chars", 1800))
    overlap_chars = int(config.get("rag_chunk_overlap_chars", 200))
    ocr_enabled = bool(config.get("rag_ocr_enabled", False))
    ocr_languages = str(config.get("rag_ocr_languages", "eng"))
    ocr_dpi = int(config.get("rag_ocr_dpi", 200))

    conn = rag_db.connect(db_path)
    info = rag_db.ensure_schema(conn)

    targets: list[Path] = []

    # FLS output files (if present)
    for key, default in (
        ("world_model_file", "LITERATURE_WORLD_MODEL.md"),
        ("manifest_file", "papers/papers_manifest.json"),
        ("notes_file", "literature_notes.json"),
    ):
        p = Path(config.get(key, default))
        if p.exists() and p.is_file():
            targets.append(p)

    report = Path("LITERATURE_SCAN_REPORT.md")
    if report.exists() and report.is_file():
        targets.append(report)

    # PDFs
    download_dir = Path(config.get("download_dir", "papers"))
    if download_dir.exists():
        for p in download_dir.rglob("*.pdf"):
            if p.is_file():
                targets.append(p)

    # Optional: repo text/code files
    if args.include_repo:
        targets.extend(list(iter_repo_files(root, max_bytes=args.max_text_bytes)))

    # De-duplicate while preserving determinism
    seen = set()
    unique_targets: list[Path] = []
    for t in sorted(targets, key=lambda p: str(p)):
        try:
            k = str(t.resolve())
        except Exception:
            k = str(t)
        if k in seen:
            continue
        seen.add(k)
        unique_targets.append(t)

    counts = {"indexed": 0, "skipped": 0, "empty": 0, "no_pdf_text": 0, "error": 0}
    for p in unique_targets:
        try:
            if p.suffix.lower() == ".pdf":
                status = index_pdf_document(
                    conn,
                    root=root,
                    path=p,
                    ocr_enabled=ocr_enabled,
                    ocr_languages=ocr_languages,
                    ocr_dpi=ocr_dpi,
                    chunk_chars=chunk_chars,
                    overlap_chars=overlap_chars,
                )
            else:
                doc_type = p.suffix.lower().lstrip(".") or "text"
                status = index_text_document(
                    conn,
                    root=root,
                    path=p,
                    doc_type=doc_type,
                    chunk_chars=chunk_chars,
                    overlap_chars=overlap_chars,
                )
            counts[status] = counts.get(status, 0) + 1
        except Exception:
            counts["error"] += 1

    if args.prune:
        wanted = {safe_relpath(p, root) for p in unique_targets}
        indexed = [r["path"] for r in conn.execute("SELECT path FROM docs").fetchall()]
        for path in indexed:
            if path in wanted:
                continue
            full = (root / path)
            if full.exists():
                continue
            rag_db.delete_doc(conn, path)
        conn.commit()

    print("RAG index built.")
    print(f"  DB: {db_path}")
    print(f"  Backend: {info.get('backend')}")
    print(f"  PDF extraction: {pdf_text.extraction_backend()}")
    print(f"  Files: {len(unique_targets)} (indexed={counts['indexed']}, skipped={counts['skipped']}, errors={counts['error']})")
    if counts.get("no_pdf_text"):
        if ocr_enabled:
            print("  Note: Some PDFs had no extractable text even after OCR.")
        else:
            print("  Note: Some PDFs had no extractable text. Install `pypdf` and consider enabling OCR (rag_ocr_enabled).")

    return 0 if counts["error"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
