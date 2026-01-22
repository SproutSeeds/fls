# FLS Usage Guide

## Commands Overview

| Command | Purpose |
|---------|---------|
| `fls.py` | Interactive pipeline runner (config confirmation + scan + local RAG) |
| `literature_scan.py` | Full novelty report (what exists) |
| `literature_scan.py --delta` | **Primary** - fetch new papers, update world model |
| `literature_scan.py --check` | Integrity verification |
| `orchestrate_summarization.py --config fls_config.json run` | Generate AI summarization prompts |
| `orchestrate_summarization.py --config fls_config.json finalize` | Merge summaries into notes |
| `orchestrate_summarization.py --config fls_config.json status` | Show summarization status |
| `unpaywall_query.py doi/search` | Unpaywall helper (OA lookup + title search) |
| `rag_index.py --config fls_config.json` | Build/update local RAG index (offline) |
| `rag_query.py --config fls_config.json "query"` | Search local RAG index (offline) |

## Recommended: One-Command Runner

If you want the “easy button”, use the interactive runner (confirms config, then runs scan + local RAG indexing):

```bash
python3 scripts/fls.py --config fls_config.json
```

If it prints **ACTION REQUIRED**, either:
- run the built-in config wizard (interactive prompt), or
- edit `fls_config.json` / `.env.local` as indicated, then re-run.

Agent/non-interactive mode (default scan behavior is **delta-if-stale**):

```bash
python3 scripts/fls.py --config fls_config.json --yes
```

Force a delta scan now:

```bash
python3 scripts/fls.py --config fls_config.json --yes --delta
```

Preview-only modes:

```bash
python3 scripts/fls.py --config fls_config.json --print-config
python3 scripts/fls.py --config fls_config.json --dry-run
```

## Basic Workflow

### 1. Initial Scan

Run a full scan to see what's out there:

```bash
python3 scripts/literature_scan.py --config fls_config.json
```

This generates a novelty report showing:
- Papers found across all sources
- Keyword matches
- Relevance assessment

### 2. Delta Scan (Primary Command)

Fetch new papers since last scan:

```bash
python3 scripts/literature_scan.py --config fls_config.json --delta
```

This will:
- Query all sources for papers since last scan
- Filter by your keywords
- Download open-access PDFs
- Auto-fill World Model entries
- Update state file

### 3. Check World Model

After a delta scan, review new entries:

```bash
cat LITERATURE_WORLD_MODEL.md
```

Look for entries at the bottom under "Delta Scan Entries".

### 3b. Build Local RAG Index (Optional, Offline)

Build a local SQLite index over your downloaded papers + notes/world model:

```bash
python3 scripts/rag_index.py --config fls_config.json
```

Then query it locally (no network):

```bash
python3 scripts/rag_query.py --config fls_config.json "sunflower bound"
```

For “repo-RAG” (also index your repo’s markdown/code):

```bash
python3 scripts/rag_index.py --config fls_config.json --include-repo
```

Note: PDF text extraction works best if you install `pypdf` (optional, free).

### 4. Deep Summarization (Optional)

For papers you want analyzed in depth:

```bash
# See what needs summarization
python3 scripts/orchestrate_summarization.py --config fls_config.json status

# Generate prompts for AI agents
python3 scripts/orchestrate_summarization.py --config fls_config.json run

# After agents complete, merge results
python3 scripts/orchestrate_summarization.py --config fls_config.json finalize
```

## Scan Frequency

### Recommended: Every 6 Hours

For active frontier research, scan frequently:

```bash
# Check when last scan ran
grep "last_scan_utc" fls_state.json

# If > 6 hours ago, run delta
python3 scripts/literature_scan.py --config fls_config.json --delta
```

### Automated via Cron

```bash
# Edit crontab
crontab -e

# Add (runs every 6 hours)
0 */6 * * * cd /path/to/project && python3 fls/scripts/literature_scan.py --config fls_config.json --delta >> fls_scan.log 2>&1
```

## Configuration Deep Dive

### Keywords

```json
{
  "primary_keywords": ["sunflower", "delta-system"],
  "secondary_keywords": ["Erdos-Rado", "polynomial method"],
  "min_primary_hits": 1
}
```

- **primary_keywords**: Paper must contain at least `min_primary_hits` of these
- **secondary_keywords**: Nice-to-have, used for relevance scoring

### Sources

```json
{
  "sources": {
    "arxiv": true,
    "semantic_scholar": true,
    "oeis": true
  }
}
```

Disable sources you don't need.

### Rate Limiting

```json
{
  "arxiv_delay_seconds": 3,
  "s2_delay_seconds": 1.0,
  "oeis_delay_seconds": 1.5
}
```

Increase if you're getting rate limited (429 errors).

### Filtering

```json
{
  "open_access_only": true,
  "lookback_days_default": 14,
  "max_new_papers_per_run": 10
}
```

- **open_access_only**: Skip paywalled papers
- **lookback_days_default**: How far back to look on delta scans
- **max_new_papers_per_run**: Limit papers per scan (prevents overwhelming)

## Output Files

### World Model (`LITERATURE_WORLD_MODEL.md`)

Structured paper summaries:

```markdown
## [arXiv:1606.09575] Upper bounds for sunflower-free sets (2016)
- **Summary:** First sub-2^n upper bound using polynomial method
- **Method:** polynomial, slice_rank
- **Data:** Asymptotic bound only
- **Gap:** No weak-formulation computations
- **Actionable:** Compare to our computed values
```

### Papers Manifest (`papers_manifest.json`)

```json
[
  {
    "arxiv_id": "1606.09575",
    "title": "Upper bounds for sunflower-free sets",
    "authors": ["Eric Naslund", "William F. Sawin"],
    "year": "2016",
    "local_file": "2016-NaslundSawin-UpperBounds.pdf",
    "url": "https://arxiv.org/abs/1606.09575"
  }
]
```

### State File (`fls_state.json`)

```json
{
  "last_scan_utc": "2026-01-21T14:20:00Z",
  "seen_arxiv_ids": ["1606.09575", "1908.08483"],
  "seen_semantic_scholar_ids": [],
  "keywords_hash": "abc123..."
}
```

## Advanced Usage

### Manual Paper Addition

There is no one-off helper script yet. If you want to add a paper manually:

1. Put the PDF into your `download_dir/` (default: `papers/`)
2. Add a corresponding entry to your `manifest_file` (default: `papers/papers_manifest.json`)
3. Optionally add a structured entry to your world model (`world_model_file`)

### Integrity Check

Verify all files are consistent:

```bash
python3 scripts/literature_scan.py --config fls_config.json --check
```

Checks:
- Manifest entries have corresponding PDFs
- No orphaned PDFs
- World model references valid papers

### Reset State

Start fresh (keeps config, removes state):

```bash
rm fls_state.json
python3 scripts/literature_scan.py --config fls_config.json --delta
```

### Custom Research Context

For AI summarization, set your research context in config:

```json
{
  "research_context": "We're studying the weak sunflower conjecture, focusing on exact values of m(n,3) for small n and polynomial vs exponential growth patterns."
}
```

This context is injected into AI prompts for better relevance assessment.

## Troubleshooting

### No papers found

- Check your keywords aren't too restrictive
- Verify arxiv_categories includes relevant areas
- Try a longer lookback_days

### Too many irrelevant papers

- Add more specific primary_keywords
- Increase min_primary_hits
- Review and tune secondary_keywords

### PDFs not downloading

- Check `open_access_only` setting
- Verify internet connectivity
- Some papers are genuinely paywalled

### World model not updating

- Ensure `auto_world_model: true` in config
- Check file permissions on output directory
- Verify config paths are correct
