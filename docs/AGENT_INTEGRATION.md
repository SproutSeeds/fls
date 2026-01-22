# Agent Integration Guide (Model-Agnostic)

FLS is designed to be driven by **any** agent or agentic workflow. The only requirement is that your tooling supports a “project instructions” Markdown file that the agent reads (the filename varies by tool).

This doc explains:

1. What to paste into your agent instructions file
2. The “checklist + routine” an agent should follow to fully use FLS (scan → local RAG → optional deep reading)

---

## 1) Copy/Paste Template (Recommended)

Use the model-agnostic template:

- `templates/AGENT.template.md`

Paste it into **whatever instruction file your agent uses**, then replace the placeholders (`{{FLS_PATH}}`, `{{CONFIG_FILE}}`, etc.).

If you use Claude Code specifically, `templates/CLAUDE.template.md` is a Claude-oriented variant with the same core protocol.

---

## 2) What the Agent Should Do (Protocol)

### Session Start (must-do)

1. Check freshness (`last_scan_utc` in the state file).
2. If stale, run a delta scan to fetch new open-access PDFs and append new world-model entries.
3. Refresh the local RAG index (offline) so retrieval includes the newest PDFs and notes.
4. Read the newest entries in the world model and report any relevant changes/risks/opportunities.

Tip: you can do (2) + (3) via the single runner command:

- If FLS is installed under `./fls`: `python3 fls/scripts/fls.py --config fls_config.json --yes`
- If running inside the FLS repo: `python3 scripts/fls.py --config fls_config.json --yes`

In `--yes` mode, the default scan behavior is **delta-if-stale**. Use `--delta` to force a scan now.

If the runner prints **ACTION REQUIRED** and exits non-zero, treat that output as the agent’s “questions to ask the user” to finish configuration. Update `fls_config.json` / `.env.local`, then re-run.

### During work (should-do)

- Use local RAG queries whenever you need citations/snippets from PDFs, notes, or the world model during synthesis.
- Before making “state of the art” or novelty claims, re-check freshness and scan if stale.

### Optional deep reading

If a subset of papers are important, use the summarization orchestrator to coordinate full-PDF reading and structured JSON summaries.

---

## 3) Trigger Conditions (when to scan)

Good default triggers:

- Session start if last scan is older than `freshness_hours` (default: 6).
- User asks “what’s new”, “latest papers”, “recent research”.
- Starting a new approach/angle.
- Before publishing or making strong claims.
- When stuck: new literature may contain the missing technique.

---

## 4) Outputs the Agent Should Know

The key artifacts for agent context are:

- `LITERATURE_WORLD_MODEL.md` — primary structured summary feed
- `papers/` — downloaded PDFs
- `papers/papers_manifest.json` — paper metadata
- `literature_notes.json` — deep summaries (merged results)
- `fls_state.json` — scan state and freshness (`last_scan_utc`)
- `rag/rag_index.sqlite` — local/offline retrieval index
