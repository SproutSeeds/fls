# Local RAG (Free + Offline)

FLS includes a **fully local** retrieval layer (“repo-RAG”) built on **SQLite**:

- `scripts/rag_index.py` builds/updates an index over your downloaded papers + notes/world model.
- `scripts/rag_query.py` queries that index for fast, offline retrieval.

No embeddings, no external services, no paid APIs.

---

## Quick Start

From your project root:

```bash
# Build/update the index
python3 fls/scripts/rag_index.py --config fls_config.json

# Query it
python3 fls/scripts/rag_query.py --config fls_config.json "your question or keyword"
```

The index is stored at `rag_index_db` (default: `rag/rag_index.sqlite`).

---

## What Gets Indexed

By default:

- PDFs under `download_dir/` (default: `papers/`)
- `world_model_file` (default: `LITERATURE_WORLD_MODEL.md`)
- `manifest_file` (default: `papers/papers_manifest.json`)
- `notes_file` (default: `literature_notes.json`)

Optional repo-RAG:

```bash
python3 fls/scripts/rag_index.py --config fls_config.json --include-repo
```

This adds markdown/code/config files from the repository (skipping common heavy directories like `node_modules/`, `.git/`, and `rag/`).

---

## PDF Text Extraction (Local, Optional)

Indexing PDFs depends on extracting text. For best results, install the optional deps:

```bash
pip install -r requirements.txt  # if you're in the FLS repo
# or
pip install -r fls/requirements.txt  # if FLS lives under ./fls in your project
```

If `pypdf` isn’t available, FLS will try `pdfplumber` (if installed), or `pdftotext` (if present on your system).

### OCR for Scanned PDFs (Optional)

Some research PDFs are scanned images (no embedded text). To index those, enable OCR in your config:

```json
{
  "rag_ocr_enabled": true,
  "rag_ocr_languages": "eng",
  "rag_ocr_dpi": 200
}
```

OCR stays fully local/free, but requires system tools:

- macOS (Homebrew): `brew install tesseract poppler`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr poppler-utils`

---

## Agentic Flow Pattern

A typical agent session:

1. Run `literature_scan.py --delta` to fetch new papers.
2. Run `rag_index.py` to refresh the local index.
3. Use `rag_query.py` whenever you need citations or supporting context during synthesis.
