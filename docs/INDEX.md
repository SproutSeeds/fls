# Docs Index

Start here if you're new to FLS:

- `INSTALL.md` — installation options and verification steps.
- `USAGE.md` — the main workflow (`--delta`, integrity checks, summarization).
- `docs/API_KEYS.md` — Semantic Scholar key + Unpaywall email setup (and `.env.local`).
- `docs/RAG.md` — local/offline RAG (index + query), plus OCR option for scanned PDFs.
- `docs/UNPAYWALL.md` — Unpaywall endpoint details and usage notes.
- `docs/CUSTOMIZATION.md` — tuning keywords/categories/research context.
- `docs/AGENT_INTEGRATION.md` — agent session protocol (model-agnostic) and templates.
- `templates/AGENT.template.md` — copy/paste protocol for any agent instructions file (model-agnostic).

Typical loop:

0. `fls.py` (optional convenience runner; confirms config then runs scan + index)
1. `literature_scan.py --delta` (fetch + download PDFs)
2. `rag_index.py` (build/update local index)
3. `rag_query.py` (retrieve evidence/snippets for synthesis)
4. `orchestrate_summarization.py` (agents read PDFs and store structured notes)
