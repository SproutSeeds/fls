# FLS Integration (Model-Agnostic Agent Instructions)

Paste this section into **whatever instruction file your agent uses**, for example:

- `CLAUDE.md` (Claude Code)
- `AGENTS.md` (Codex CLI)
- any other “agent rules / project context” Markdown file your tooling reads

This template is **model-agnostic**: it only defines the FLS protocol and commands.

---

## Frontier Literature Search Protocol (FLS)

### When to Run FLS (Agent Triggers)

- Session start if last scan is stale (see `freshness_hours` in config)
- User asks for “latest papers”, “recent research”, “what’s new”
- Before making strong “state of the art” / novelty claims
- When switching approaches or entering a new “cone of vision”
- When stuck: literature may contain the missing technique

### Agent Commands (Copy/Paste)

- Safe default (agent-friendly; avoids unnecessary network calls):  
  `python3 {{FLS_PATH}}/scripts/fls.py --config {{CONFIG_FILE}} --yes`
- Force a delta scan now (use sparingly / when user requests):  
  `python3 {{FLS_PATH}}/scripts/fls.py --config {{CONFIG_FILE}} --yes --delta`
- Enable repo-RAG (also index repo markdown/code):  
  `python3 {{FLS_PATH}}/scripts/fls.py --config {{CONFIG_FILE}} --yes --include-repo`

### One-Time Setup Checklist

- [ ] Ensure `fls_config.json` exists and is configured (keywords + paths).
- [ ] Ensure `fls_state.json` exists (created by init script, or generated on first delta scan).
- [ ] Ensure `papers/` exists (PDF download directory).
- [ ] Create `.env.local` (git-ignored) if using optional services:
  - [ ] `FLS_SEMANTIC_SCHOLAR_API_KEY` (optional; improves rate limits)
  - [ ] `FLS_UNPAYWALL_EMAIL` (required for Unpaywall requests; no API key)
- [ ] (Optional) Install PDF extraction deps for local RAG indexing:
  - [ ] `pip install -r {{FLS_PATH}}/requirements.txt` (if FLS is vendored as `./fls`)
  - [ ] `pip install -r requirements.txt` (if running inside the FLS repo)

### Command Prefix

Set `{{FLS_PATH}}` to where FLS lives **relative to your project root**:

- If you installed into a project via `./scripts/fls-init.sh`: `{{FLS_PATH}} = fls`
- If you’re running directly inside the FLS repo: `{{FLS_PATH}} = .`

---

## Session Start Routine (Agent MUST Do)

- [ ] Preferred (single command): run the pipeline runner non-interactively:
  - `python3 {{FLS_PATH}}/scripts/fls.py --config {{CONFIG_FILE}} --yes`
  - Note: in `--yes` mode, the default scan behavior is **delta-if-stale** (avoids unnecessary network calls). Use `--delta` to force a scan now.
- [ ] If the runner prints **ACTION REQUIRED** and exits non-zero:
  - [ ] Ask the user the listed questions (keywords, context, optional API settings).
  - [ ] Update `{{CONFIG_FILE}}` / `.env.local`, then re-run the command.
- [ ] Or do it step-by-step:
- [ ] Check literature freshness:
  - Command: `grep "last_scan_utc" {{STATE_FILE}}`
  - If last scan is older than `{{FRESHNESS_HOURS}}` hours → run a delta scan.
- [ ] Run delta scan when stale (downloads new OA PDFs + appends world model):
  - `python3 {{FLS_PATH}}/scripts/literature_scan.py --config {{CONFIG_FILE}} --delta`
- [ ] Refresh local RAG index (offline retrieval over PDFs + notes/world model):
  - `python3 {{FLS_PATH}}/scripts/rag_index.py --config {{CONFIG_FILE}}`
- [ ] Read the newest entries at the bottom of `{{WORLD_MODEL_FILE}}` and report anything relevant.

---

## During Work (Agent SHOULD Do)

- When you need supporting context/citations from local artifacts:
  - `python3 {{FLS_PATH}}/scripts/rag_query.py --config {{CONFIG_FILE}} "your query"`
- Before making “state of the art” claims or deciding on a new approach:
  - Run the freshness check and delta scan if stale.

---

## Deep Reading (Optional, Agentic)

FLS can orchestrate parallel “read the PDF” summaries. Your agent(s) can use any model/tooling; FLS just stores/merges JSON.

- Status: `python3 {{FLS_PATH}}/scripts/orchestrate_summarization.py --config {{CONFIG_FILE}} status`
- Generate prompts: `python3 {{FLS_PATH}}/scripts/orchestrate_summarization.py --config {{CONFIG_FILE}} run`
- Merge results: `python3 {{FLS_PATH}}/scripts/orchestrate_summarization.py --config {{CONFIG_FILE}} finalize`

---

## Maintenance (Optional)

- Integrity check (manifest vs PDFs): `python3 {{FLS_PATH}}/scripts/literature_scan.py --config {{CONFIG_FILE}} --check`
- Smoke tests:
  - Live APIs (optional): `python3 {{FLS_PATH}}/scripts/smoke_test_apis.py`
  - Local RAG (no network): `python3 {{FLS_PATH}}/scripts/smoke_test_rag.py`

---

## Template Variables

Replace these placeholders with your actual paths:

| Variable | Description | Common default |
|----------|-------------|----------------|
| `{{FLS_PATH}}` | Path to FLS directory | `fls` |
| `{{CONFIG_FILE}}` | Config file path | `fls_config.json` |
| `{{STATE_FILE}}` | State file path | `fls_state.json` |
| `{{WORLD_MODEL_FILE}}` | World model path | `LITERATURE_WORLD_MODEL.md` |
| `{{FRESHNESS_HOURS}}` | Scan frequency | `6` |
