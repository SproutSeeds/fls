"""
Local RAG storage using SQLite.

- Uses FTS5 when available for fast lexical retrieval (BM25 ranking).
- Falls back to a plain table + LIKE search if FTS5 is unavailable.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Optional


SCHEMA_VERSION = 1


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _fts5_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS __fts5_probe USING fts5(x)")
        conn.execute("DROP TABLE IF EXISTS __fts5_probe")
        return True
    except sqlite3.OperationalError:
        return False


def ensure_schema(conn: sqlite3.Connection) -> dict:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
          key TEXT PRIMARY KEY,
          value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docs (
          path TEXT PRIMARY KEY,
          doc_type TEXT NOT NULL,
          mtime_ns INTEGER NOT NULL,
          size INTEGER NOT NULL,
          extra_json TEXT DEFAULT ''
        )
        """
    )

    if _fts5_available(conn):
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING fts5(
              content,
              path UNINDEXED,
              doc_type UNINDEXED,
              page UNINDEXED,
              chunk_index UNINDEXED,
              tokenize = 'porter'
            )
            """
        )
        backend = "fts5"
    else:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chunks_plain (
              content TEXT NOT NULL,
              path TEXT NOT NULL,
              doc_type TEXT NOT NULL,
              page INTEGER,
              chunk_index INTEGER
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_plain_path ON chunks_plain(path)")
        backend = "plain"

    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.execute(
        "INSERT OR REPLACE INTO meta(key, value) VALUES(?, ?)",
        ("backend", backend),
    )
    conn.commit()
    return {"schema_version": SCHEMA_VERSION, "backend": backend}


def get_backend(conn: sqlite3.Connection) -> str:
    row = conn.execute("SELECT value FROM meta WHERE key='backend'").fetchone()
    return row["value"] if row else "plain"


def get_doc(conn: sqlite3.Connection, path: str) -> Optional[dict]:
    row = conn.execute("SELECT path, doc_type, mtime_ns, size FROM docs WHERE path=?", (path,)).fetchone()
    return dict(row) if row else None


def upsert_doc(conn: sqlite3.Connection, *, path: str, doc_type: str, mtime_ns: int, size: int):
    conn.execute(
        """
        INSERT INTO docs(path, doc_type, mtime_ns, size)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
          doc_type=excluded.doc_type,
          mtime_ns=excluded.mtime_ns,
          size=excluded.size
        """,
        (path, doc_type, int(mtime_ns), int(size)),
    )


def delete_doc(conn: sqlite3.Connection, path: str):
    backend = get_backend(conn)
    if backend == "fts5":
        conn.execute("DELETE FROM chunks WHERE path=?", (path,))
    else:
        conn.execute("DELETE FROM chunks_plain WHERE path=?", (path,))
    conn.execute("DELETE FROM docs WHERE path=?", (path,))


def delete_chunks(conn: sqlite3.Connection, path: str):
    backend = get_backend(conn)
    if backend == "fts5":
        conn.execute("DELETE FROM chunks WHERE path=?", (path,))
    else:
        conn.execute("DELETE FROM chunks_plain WHERE path=?", (path,))


def insert_chunk(
    conn: sqlite3.Connection,
    *,
    path: str,
    doc_type: str,
    page: Optional[int],
    chunk_index: int,
    content: str,
):
    backend = get_backend(conn)
    if backend == "fts5":
        conn.execute(
            "INSERT INTO chunks(content, path, doc_type, page, chunk_index) VALUES(?, ?, ?, ?, ?)",
            (content, path, doc_type, page, int(chunk_index)),
        )
    else:
        conn.execute(
            "INSERT INTO chunks_plain(content, path, doc_type, page, chunk_index) VALUES(?, ?, ?, ?, ?)",
            (content, path, doc_type, page, int(chunk_index)),
        )


def search(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 8,
    doc_type: str = "",
    include_content: bool = False,
) -> list[dict[str, Any]]:
    backend = get_backend(conn)

    if backend == "fts5":
        where = "chunks MATCH ?"
        params: list[Any] = [query]
        if doc_type:
            where += " AND doc_type=?"
            params.append(doc_type)

        if include_content:
            sql = f"""
              SELECT
                path, doc_type, page, chunk_index,
                bm25(chunks) AS rank,
                content AS content,
                snippet(chunks, 0, '[', ']', '…', 12) AS snippet
              FROM chunks
              WHERE {where}
              ORDER BY rank
              LIMIT ?
            """
        else:
            sql = f"""
              SELECT
                path, doc_type, page, chunk_index,
                bm25(chunks) AS rank,
                snippet(chunks, 0, '[', ']', '…', 12) AS snippet
              FROM chunks
              WHERE {where}
              ORDER BY rank
              LIMIT ?
            """
        params.append(int(limit))
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    # Fallback: plain LIKE search
    like = f"%{query}%"
    params2: list[Any] = [like]
    where2 = "content LIKE ?"
    if doc_type:
        where2 += " AND doc_type=?"
        params2.append(doc_type)
    sql2 = f"""
      SELECT path, doc_type, page, chunk_index, 0.0 AS rank, content
      FROM chunks_plain
      WHERE {where2}
      LIMIT ?
    """
    params2.append(int(limit))
    rows = conn.execute(sql2, params2).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if not include_content:
            text = d.get("content") or ""
            d["snippet"] = text[:240] + ("…" if len(text) > 240 else "")
            d.pop("content", None)
        out.append(d)
    return out

