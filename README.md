# FLS — Frontier Literature Scanner

**Automated literature monitoring for frontier research.**

FLS is a **project-agnostic pipeline** for staying current with research literature. It provides:

- Multi-source paper discovery (arXiv, Semantic Scholar, OEIS)
- Keyword-based relevance filtering
- Automatic PDF downloading (open-access)
- AI-ready structured output (World Model with Methods/Data/Gap/Actionable)
- Incremental delta scanning (only fetch what's new)
- Agent integration templates for Claude Code and similar tools

**Target audience:** Researchers attacking frontier problems (mathematics, theoretical CS, physics) who want automated literature monitoring with structured output for AI-assisted decision-making.

---

## Quick Start

Pick a setup mode:

### Option A (Recommended): Install FLS into an Existing Project

```bash
git clone https://github.com/SproutSeeds/fls.git
cd fls

# Install FLS into your project/repo
./scripts/fls-init.sh /path/to/your/project

cd /path/to/your/project

# (Optional) install PDF extraction deps for local RAG indexing
pip install -r fls/requirements.txt

# Create a local env file (git-ignored) for keys/email
cp .env.example .env.local
nano .env.local

# Configure your research keywords
nano fls_config.json

# Run the interactive pipeline runner (recommended)
# (confirms config, then runs scan + local RAG indexing)
python3 fls/scripts/fls.py --config fls_config.json

# Or run steps individually:
# python3 fls/scripts/literature_scan.py --config fls_config.json --delta
# python3 fls/scripts/rag_index.py --config fls_config.json
# python3 fls/scripts/rag_query.py --config fls_config.json "your query"
```

### Option B: Run Directly from This Repo (Quick Trial)

```bash
git clone https://github.com/SproutSeeds/fls.git
cd fls

# (Optional) install PDF extraction deps for local RAG indexing
pip install -r requirements.txt

cp templates/config.template.json fls_config.json
cp .env.example .env.local

nano fls_config.json
nano .env.local

# Interactive runner (recommended)
python3 scripts/fls.py --config fls_config.json

# Or run steps individually:
# python3 scripts/literature_scan.py --config fls_config.json --delta
# python3 scripts/rag_index.py --config fls_config.json
# python3 scripts/rag_query.py --config fls_config.json "your query"
```

See [docs/INDEX.md](docs/INDEX.md) for the full docs map (including API keys and Unpaywall).

---

## Agent Setup (Model-Agnostic)

FLS is designed to be driven by **any** agent workflow. The only difference between tools is *which Markdown file they read for project instructions*.

To set up your agent:

1. Open `templates/AGENT.template.md`.
2. Paste it into your agent’s instruction file (examples: `CLAUDE.md`, `AGENTS.md`, etc.).
3. Replace the template variables (`{{FLS_PATH}}`, `{{CONFIG_FILE}}`, …).
4. Use the included checklist + “session start routine” so the agent runs: freshness check → delta scan → local RAG indexing.
5. If `fls.py` prints **ACTION REQUIRED**, the agent should ask the user those questions, update config/env, then re-run.
6. In `--yes` mode, the default scan behavior is **delta-if-stale**. Use `--delta` to force a scan now.

If you use Claude Code specifically, you can also start from `templates/CLAUDE.template.md`.

---

## What's in This Repo

```
fls/
├── README.md                    # This file
├── INSTALL.md                   # Detailed setup instructions
├── USAGE.md                     # Full usage guide
├── LICENSE                      # MIT License
├── .env.example                 # Example env vars (copy to .env.local; git-ignored)
├── requirements.txt             # Optional deps for PDF extraction (RAG)
│
├── scripts/
│   ├── literature_scan.py       # Core scanner
│   ├── orchestrate_summarization.py  # Parallel AI summarization
│   ├── lib/                     # Shared API helpers
│   ├── unpaywall_query.py       # Unpaywall helper CLI (optional)
│   ├── fls.py                   # Interactive pipeline runner (single entrypoint)
│   ├── rag_index.py             # Local RAG index builder (SQLite)
│   ├── rag_query.py             # Local RAG query (offline search)
│   ├── smoke_test_apis.py        # Live API smoke tests (optional)
│   ├── smoke_test_rag.py         # Local RAG smoke test (no network)
│   └── fls-init.sh              # Project setup helper
│
├── templates/
│   ├── config.template.json     # Configuration template
│   ├── state.template.json      # Initial state template
│   ├── WORLD_MODEL.template.md  # World model structure
│   ├── CLAUDE.template.md       # Claude Code instructions snippet
│   └── AGENT.template.md        # Model-agnostic agent instructions template
│
├── examples/
│   └── sunflower-conjecture/    # Complete working example
│
 └── docs/
     ├── INDEX.md                 # Docs map (start here)
     ├── API_KEYS.md              # API key setup
     ├── UNPAYWALL.md             # Unpaywall API (OA lookup + title search notes)
     ├── RAG.md                   # Local RAG (offline indexing + query)
     ├── CUSTOMIZATION.md         # Domain-specific tuning
     └── AGENT_INTEGRATION.md     # Agent protocol (model-agnostic)
```

Extending/automation tip: the source clients live in `scripts/lib/` (e.g. `lib/arxiv.py`, `lib/semantic_scholar.py`, `lib/oeis.py`, `lib/unpaywall.py`) so you can write new scripts under `scripts/` that reuse them.

---

## Pipeline Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         FLS PIPELINE                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  1. DISCOVERY (--delta scan)                                            │
│     ├── Query arXiv API (configurable categories)                       │
│     ├── Query Semantic Scholar (citation tracking)                      │
│     ├── Query OEIS (integer sequences, optional)                        │
│     └── Filter by primary/secondary keywords                            │
│                                                                         │
│  2. DOWNLOAD                                                            │
│     ├── Fetch open-access PDFs                                          │
│     ├── Validate PDF integrity                                          │
│     └── Update manifest                                                 │
│                                                                         │
│  3. TRIAGE (automatic)                                                  │
│     ├── Analyze abstract for Methods/Data/Gap                           │
│     ├── Generate actionable insights                                    │
│     └── Append to World Model                                           │
│                                                                         │
│  4. SUMMARIZATION (optional, for priority papers)                       │
│     ├── Generate prompts for AI agents                                  │
│     ├── Agents read full PDFs                                           │
│     └── Merge detailed summaries into notes                             │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## World Model Output

Each paper gets a structured entry:

```markdown
## [arXiv:XXXX.XXXXX] Paper Title (Year)
- **Summary:** One-line description of main contribution
- **Method:** polynomial, entropy, construction, etc.
- **Data:** What concrete data/values does it provide?
- **Gap:** What doesn't it address that we care about?
- **Actionable:** What can we do with this for our research?
```

This format is designed for:
- Quick human scanning
- AI agent context injection
- Fine-tuning research decision-making

---

## Agent Integration

FLS is designed to work with AI coding assistants. Add this to your project's `CLAUDE.md`:

```markdown
## Literature Pipeline

Check literature freshness at session start:
- If last scan > 6 hours ago → Run delta scan
- Command: `python3 scripts/literature_scan.py --config fls_config.json --delta`
- Check World Model for new papers that affect current work
```

See [docs/AGENT_INTEGRATION.md](docs/AGENT_INTEGRATION.md) for full integration templates.

---

## Examples

### Sunflower Conjecture (Frontier Mathematics)

A complete working example for Erdős Problem #857:

```bash
cd examples/sunflower-conjecture
python3 ../../scripts/literature_scan.py --config config.json --delta
```

See [examples/sunflower-conjecture/](examples/sunflower-conjecture/) for the full setup.

---

## Requirements

- Python 3.8+
- No external dependencies for basic scanning
- Recommended: `pip install -r requirements.txt` for robust PDF text extraction + local RAG indexing
- Optional: Semantic Scholar API key for higher rate limits

---

## Contributing

Contributions welcome! Please:
1. Fork the repo
2. Create a feature branch
3. Submit a PR with clear description

---

## License

MIT License. See [LICENSE](LICENSE).

---

## Acknowledgments

Inspired by the need to stay current with rapidly evolving frontier mathematics research while working with AI assistants.
