# FLS Integration for CLAUDE.md

Add this section to your project's `CLAUDE.md` to enable automatic literature monitoring.

---

## Literature Pipeline (FLS)

We maintain an automated pipeline to stay current with research literature. **New papers can invalidate assumptions or provide breakthrough techniques.**

### When to Run the Literature Scan

```
┌─────────────────────────────────────────────────────────────┐
│              LITERATURE SCAN TRIGGERS                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  AUTOMATIC TRIGGERS (agent should initiate):                │
│  ├── Session start if last scan > {{FRESHNESS_HOURS}} hours │
│  ├── User mentions "new papers" / "recent research"         │
│  ├── Starting a new research angle or approach              │
│  ├── Before making claims about "state of the art"          │
│  └── When stuck - new papers may have solutions             │
│                                                             │
│  USER-REQUESTED TRIGGERS:                                   │
│  ├── User explicitly asks for literature update             │
│  └── User asks "what's new in [research area]"              │
│                                                             │
│  FRESHNESS THRESHOLD: {{FRESHNESS_HOURS}} hours             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### How to Check if Scan is Needed

```bash
# Check when last literature scan ran
grep "last_scan_utc" {{STATE_FILE}}
```

If more than {{FRESHNESS_HOURS}} hours old, run a delta scan.

### Pipeline Commands

```bash
# Single runner (recommended)
python3 {{FLS_PATH}}/scripts/fls.py --config {{CONFIG_FILE}} --yes

# Note: in --yes mode, the default scan behavior is delta-if-stale (avoids unnecessary network calls).
# Use --delta to force a scan now.

# If the runner prints ACTION REQUIRED and exits non-zero:
# - Ask the user the listed questions and update config/env, then re-run.

# PRIMARY COMMAND - Run this to fetch new papers
python3 {{FLS_PATH}}/scripts/literature_scan.py --config {{CONFIG_FILE}} --delta
# → Downloads new PDFs
# → Auto-fills World Model with Methods/Data/Gap/Actionable

# Check what papers we have
python3 {{FLS_PATH}}/scripts/orchestrate_summarization.py --config {{CONFIG_FILE}} status

# Build/update local RAG index (offline search over PDFs + notes)
python3 {{FLS_PATH}}/scripts/rag_index.py --config {{CONFIG_FILE}}

# Query local RAG index
python3 {{FLS_PATH}}/scripts/rag_query.py --config {{CONFIG_FILE}} "your query"

# Integrity check
python3 {{FLS_PATH}}/scripts/literature_scan.py --config {{CONFIG_FILE}} --check

# Full novelty report (what's out there, doesn't download)
python3 {{FLS_PATH}}/scripts/literature_scan.py --config {{CONFIG_FILE}}
```

### Where Papers Live

| File | Purpose |
|------|---------|
| `{{WORLD_MODEL_FILE}}` | **Primary reference** - auto-triaged papers |
| `{{DOWNLOAD_DIR}}/` | Downloaded PDFs |
| `{{MANIFEST_FILE}}` | Paper metadata |
| `{{NOTES_FILE}}` | Deep summaries |
| `{{STATE_FILE}}` | Scan state (last run, seen IDs) |
| `{{RAG_INDEX_DB}}` | Local RAG index (SQLite) |

### After Running a Scan

1. **Check World Model** for new entries at the bottom
2. **Evaluate if new papers affect current work:**
   - Do they invalidate any of our assumptions?
   - Do they provide techniques we could use?
   - Do they already solve something we're working on?
3. **Update project docs** if priorities change
4. **Inform user** of any significant new findings

---

## Session Start Protocol Addition

Add this as Step 0 before other session start steps:

```markdown
### Step 0: Check Literature Freshness
\`\`\`bash
# Check when last literature scan ran
grep "last_scan_utc" {{STATE_FILE}}
\`\`\`
If more than **{{FRESHNESS_HOURS}} hours old** → Run delta scan before proceeding.
New papers may change priorities or provide solutions.
```

---

## Template Variables

Replace these placeholders with your actual paths:

| Variable | Description | Example |
|----------|-------------|---------|
| `{{FLS_PATH}}` | Path to FLS scripts | `fls` or `./fls` |
| `{{CONFIG_FILE}}` | Your config file | `fls_config.json` |
| `{{STATE_FILE}}` | State file path | `fls_state.json` |
| `{{WORLD_MODEL_FILE}}` | World model path | `LITERATURE_WORLD_MODEL.md` |
| `{{DOWNLOAD_DIR}}` | PDF download dir | `papers` |
| `{{MANIFEST_FILE}}` | Manifest path | `papers/papers_manifest.json` |
| `{{NOTES_FILE}}` | Notes file path | `literature_notes.json` |
| `{{RAG_INDEX_DB}}` | RAG index DB path | `rag/rag_index.sqlite` |
| `{{FRESHNESS_HOURS}}` | Scan frequency | `6` |
