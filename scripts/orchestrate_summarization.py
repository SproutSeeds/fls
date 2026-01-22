#!/usr/bin/env python3
"""
FLS — Orchestrate Parallel Literature Summarization

Coordinates parallel AI summarization of papers:
1. Identifies papers needing summarization
2. Generates prompts for parallel agents
3. Stores agent results
4. Merges results into notes file

USAGE:
    python3 orchestrate_summarization.py --config config.json run       # Full orchestration
    python3 orchestrate_summarization.py --config config.json prompts   # Just generate prompts
    python3 orchestrate_summarization.py --config config.json store ID  # Store a result
    python3 orchestrate_summarization.py --config config.json finalize  # Merge results
    python3 orchestrate_summarization.py --config config.json status    # Show status

License: MIT
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from lib import dotenv

MAX_PARALLEL_AGENTS = 10


def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)
    with open(path) as f:
        return json.load(f)


def load_manifest(config: dict) -> list:
    """Load papers manifest."""
    manifest_path = Path(config.get("manifest_file", "papers/papers_manifest.json"))
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return []


def load_notes(config: dict) -> dict:
    """Load literature notes."""
    notes_path = Path(config.get("notes_file", "literature_notes.json"))
    if notes_path.exists():
        with open(notes_path) as f:
            return json.load(f)
    return {"schema_version": 1, "notes": {}}


def save_notes(notes: dict, config: dict):
    """Save literature notes."""
    notes_path = Path(config.get("notes_file", "literature_notes.json"))
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    with open(notes_path, "w") as f:
        json.dump(notes, f, indent=2)


def get_unsummarized_papers(config: dict) -> list:
    """Get papers that haven't been summarized yet."""
    manifest = load_manifest(config)
    notes = load_notes(config)
    summarized_ids = set(notes.get("notes", {}).keys())

    download_dir = Path(config.get("download_dir", "papers"))

    unsummarized = []
    for paper in manifest:
        paper_id = paper.get("arxiv_id") or paper.get("s2_id", "")
        if paper_id and paper_id not in summarized_ids:
            local_file = paper.get("local_file", "")
            paper["pdf_path"] = str(download_dir / local_file) if local_file else ""
            unsummarized.append(paper)

    return unsummarized


def generate_prompt(paper: dict, config: dict) -> str:
    """Generate summarization prompt for a paper."""
    today = datetime.now().strftime("%Y-%m-%d")
    paper_id = paper.get("arxiv_id") or paper.get("s2_id", "unknown")
    title = paper.get("title", "Unknown")
    research_context = config.get("research_context", "Research literature analysis.")

    return f"""You are summarizing a research paper for the Frontier Literature Scanner.

**Paper to summarize:** {paper_id} - "{title}" ({paper.get('year', 'unknown')})

**PDF location:** {paper.get('pdf_path', 'N/A')}

**Research context:** {research_context}

**Your task:**
1. Read the PDF
2. Generate a summary in this exact JSON format:

```json
{{
  "paper_id": "{paper_id}",
  "title": "{title}",
  "status": "AUTO_SUMMARY",
  "relevance": <0-100 score>,
  "relevance_label": "<High if >=70, Medium if >=40, else Low>",
  "summary": "<2-4 sentence summary focusing on main results and techniques>",
  "transferable": [
    "<insight 1 that could help our research>",
    "<insight 2>",
    ...
  ],
  "not_relevant": [
    "<aspect 1 that doesn't help our specific problem>",
    ...
  ],
  "tags": ["<tag1>", "<tag2>", ...],
  "reviewed_by": "agent",
  "date_added": "{today}",
  "date_updated": "{today}"
}}
```

Output ONLY the JSON, no other text."""


def get_results_dir(config: dict) -> Path:
    """Get results directory."""
    return Path(config.get("download_dir", "papers")) / "summarization_results"


def store_result(paper_id: str, result_json: str, config: dict) -> bool:
    """Store a summarization result."""
    results_dir = get_results_dir(config)
    results_dir.mkdir(parents=True, exist_ok=True)

    try:
        data = json.loads(result_json)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON for {paper_id}: {e}")
        return False

    result_file = results_dir / f"{paper_id.replace('/', '-')}.json"
    with open(result_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Stored result: {result_file}")
    return True


def collect_results(config: dict) -> dict:
    """Collect all results from results directory."""
    results_dir = get_results_dir(config)
    if not results_dir.exists():
        return {}

    results = {}
    for f in results_dir.glob("*.json"):
        try:
            with open(f) as fp:
                data = json.load(fp)
            paper_id = data.get("paper_id", f.stem)
            results[paper_id] = data
        except Exception as e:
            print(f"Error reading {f}: {e}")

    return results


def merge_results(config: dict) -> int:
    """Merge collected results into notes file."""
    results = collect_results(config)

    if not results:
        print("No results to merge.")
        return 0

    notes = load_notes(config)
    merged = 0

    for paper_id, result in results.items():
        note = {
            "title": result.get("title", ""),
            "status": result.get("status", "AUTO_SUMMARY"),
            "relevance": result.get("relevance", 50),
            "relevance_label": result.get("relevance_label", "Medium"),
            "summary": result.get("summary", ""),
            "transferable": result.get("transferable", []),
            "not_relevant": result.get("not_relevant", []),
            "tags": result.get("tags", []),
            "reviewed_by": result.get("reviewed_by", "agent"),
            "date_added": result.get("date_added", datetime.now().strftime("%Y-%m-%d")),
            "date_updated": datetime.now().strftime("%Y-%m-%d")
        }
        notes["notes"][paper_id] = note
        merged += 1

    save_notes(notes, config)
    print(f"Merged {merged} results into notes file")
    return merged


def cleanup_results(config: dict):
    """Remove processed result files."""
    results_dir = get_results_dir(config)
    if not results_dir.exists():
        return

    count = 0
    for f in results_dir.glob("*.json"):
        f.unlink()
        count += 1

    print(f"Cleaned up {count} result files.")


def cmd_run(config: dict):
    """Full orchestration - output prompts for parallel agents."""
    papers = get_unsummarized_papers(config)

    if not papers:
        print("=" * 60)
        print("ALL PAPERS SUMMARIZED")
        print("=" * 60)
        return

    batch = papers[:MAX_PARALLEL_AGENTS]

    print("=" * 60)
    print(f"PARALLEL SUMMARIZATION: {len(batch)} papers")
    print("=" * 60)
    print(f"\nTotal unsummarized: {len(papers)}")
    print(f"This batch: {len(batch)} (max {MAX_PARALLEL_AGENTS})")
    print("\nPapers to summarize:")
    for i, p in enumerate(batch, 1):
        paper_id = p.get("arxiv_id") or p.get("s2_id", "?")
        print(f"  {i}. {paper_id}: {p.get('title', '')[:50]}...")

    print("\n" + "=" * 60)
    print("AGENT PROMPTS")
    print("=" * 60)

    for p in batch:
        paper_id = p.get("arxiv_id") or p.get("s2_id", "?")
        print(f"\n--- Paper: {paper_id} ---\n")
        print(generate_prompt(p, config))
        print("\n" + "-" * 40)


def cmd_status(config: dict):
    """Show current status."""
    papers = get_unsummarized_papers(config)
    results = collect_results(config)
    notes = load_notes(config)

    print("Summarization Status")
    print("=" * 40)
    print(f"Papers in manifest:     {len(load_manifest(config))}")
    print(f"Papers summarized:      {len(notes.get('notes', {}))}")
    print(f"Papers unsummarized:    {len(papers)}")
    print(f"Pending results:        {len(results)}")

    if papers:
        print("\nNext batch (up to 10):")
        for p in papers[:10]:
            paper_id = p.get("arxiv_id") or p.get("s2_id", "?")
            print(f"  {paper_id}: {p.get('title', '')[:45]}...")


def main():
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(description="FLS Summarization Orchestrator")
    parser.add_argument("--config", "-c", required=True, help="Path to config file")
    parser.add_argument("command", choices=["run", "prompts", "store", "finalize", "status"])
    parser.add_argument("paper_id", nargs="?", help="Paper ID for store command")

    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "run":
        cmd_run(config)
    elif args.command == "prompts":
        cmd_run(config)
    elif args.command == "store":
        if not args.paper_id:
            print("Usage: orchestrate_summarization.py --config X store <paper_id>")
            print("Then paste JSON and press Ctrl+D")
            return
        result_json = sys.stdin.read().strip()
        if result_json.startswith("```"):
            lines = [l for l in result_json.split("\n") if not l.startswith("```")]
            result_json = "\n".join(lines)
        store_result(args.paper_id, result_json, config)
    elif args.command == "finalize":
        merged = merge_results(config)
        if merged > 0:
            cleanup_results(config)
    elif args.command == "status":
        cmd_status(config)


if __name__ == "__main__":
    main()
