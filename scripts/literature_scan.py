#!/usr/bin/env python3
"""
FLS — Frontier Literature Scanner

A project-agnostic pipeline for staying current with research literature.
Scans arXiv, Semantic Scholar, and OEIS for papers matching your keywords.

USAGE:
    # Full scan (generates novelty report)
    python3 literature_scan.py --config config.json

    # Delta/incremental scan (downloads new papers, updates world model)
    python3 literature_scan.py --config config.json --delta

    # Run integrity checks
    python3 literature_scan.py --config config.json --check

    # List unsummarized papers
    python3 literature_scan.py --config config.json --list-unsummarized

ENVIRONMENT VARIABLES:
    FLS_SEMANTIC_SCHOLAR_API_KEY - Optional API key for higher rate limits
    FLS_UNPAYWALL_EMAIL - Optional email for Unpaywall API (OA PDF lookup)

Authors: Cody Mitchell, Claude (Opus)
License: MIT
"""

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

from lib import arxiv, dotenv, oeis, semantic_scholar, unpaywall


# ============================================================================
# CONFIGURATION LOADING
# ============================================================================

def load_config(config_path: str) -> dict:
    """Load configuration from JSON file."""
    path = Path(config_path)
    if not path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        sys.exit(1)

    with open(path) as f:
        config = json.load(f)

    # Set defaults
    defaults = {
        "primary_keywords": [],
        "secondary_keywords": [],
        "min_primary_hits": 1,
        "arxiv_categories": ["math.CO"],
        "sources": {"arxiv": True, "semantic_scholar": True, "oeis": False},
        "max_results_per_source": 50,
        "max_new_papers_per_run": 10,
        "download_dir": "papers",
        "state_file": "fls_state.json",
        "world_model_file": "LITERATURE_WORLD_MODEL.md",
        "manifest_file": "papers/papers_manifest.json",
        "auto_world_model": True,
        "open_access_only": True,
        "lookback_days_default": 14,
        "arxiv_delay_seconds": 3,
        "s2_delay_seconds": 1.0,
        "oeis_delay_seconds": 1.5,
        "max_queue_size": 200,
        "recheck_irrelevant_on_keyword_change": True,
        "irrelevant_recheck_days": 180,
        "research_context": "Research literature monitoring.",
        "oeis_sequences": [],
        "unpaywall_email": "",
        "unpaywall_delay_seconds": 1.0,
    }

    for key, value in defaults.items():
        if key not in config:
            config[key] = value

    return config


def load_state(config: dict) -> dict:
    """Load scan state from file."""
    state_path = Path(config.get("state_file", "fls_state.json"))

    if state_path.exists():
        with open(state_path) as f:
            return json.load(f)

    return {
        "last_scan_utc": "1970-01-01T00:00:00Z",
        "keywords_hash": "",
        "seen_arxiv_ids": [],
        "seen_semantic_scholar_ids": [],
        "seen_oeis_ids": [],
        "reviewed_irrelevant_arxiv_ids": [],
        "pending_queue": [],
    }


def save_state(state: dict, config: dict):
    """Save scan state to file."""
    state_path = Path(config.get("state_file", "fls_state.json"))
    with open(state_path, "w") as f:
        json.dump(state, f, indent=2)


def compute_keywords_hash(config: dict) -> str:
    """Compute hash of keywords for change detection."""
    keywords = sorted(config.get("primary_keywords", []) + config.get("secondary_keywords", []))
    return hashlib.md5(json.dumps(keywords).encode()).hexdigest()


# ============================================================================
# KEYWORD FILTERING
# ============================================================================

def matches_keywords(paper: dict, config: dict) -> bool:
    """Check if paper matches keyword criteria."""
    primary = config.get("primary_keywords", [])
    min_hits = config.get("min_primary_hits", 1)

    if not primary:
        return True  # No keywords configured, accept all

    text = (paper.get("title", "") + " " + paper.get("abstract", "")).lower()

    hits = sum(1 for kw in primary if kw.lower() in text)
    return hits >= min_hits


# ============================================================================
# WORLD MODEL GENERATION
# ============================================================================

def generate_world_model_entry(paper: dict, config: dict) -> str:
    """Generate a world model entry for a paper."""
    title = paper.get("title", "Unknown")
    year = paper.get("published", paper.get("year", ""))[:4] or "????"
    abstract = paper.get("abstract", "").lower()

    # Detect method from abstract
    methods = []
    if "polynomial" in abstract:
        methods.append("polynomial")
    if "entropy" in abstract:
        methods.append("entropy")
    if "probabilistic" in abstract or "random" in abstract:
        methods.append("probabilistic")
    if "construct" in abstract:
        methods.append("construction")
    if "algorithm" in abstract or "comput" in abstract:
        methods.append("computation")

    method_str = ", ".join(methods) if methods else "TBD"

    # Generate paper ID
    arxiv_id = paper.get("arxiv_id", "")
    s2_id = paper.get("s2_id", "")
    if arxiv_id:
        paper_id = f"arXiv:{arxiv_id}"
    elif s2_id:
        paper_id = f"S2:{s2_id[:8]}"
    else:
        paper_id = "Unknown"

    # Check for data
    has_data = any(w in abstract for w in ["exact", "compute", "value", "bound"])
    data_str = "Check for explicit values" if has_data else "No explicit data mentioned"

    # Gap and actionable
    gap_str = "TBD - review needed"

    if "bound" in abstract:
        nugget = "Compare bounds to known values"
    elif "construct" in abstract:
        nugget = "Review construction techniques"
    elif "algorithm" in abstract:
        nugget = "Review computational approach"
    else:
        nugget = "Review for applicable techniques"

    entry = f"""
## [{paper_id}] {title} ({year})
- **Summary:** {title[:100]}...
- **Method:** {method_str}
- **Data:** {data_str}
- **Gap:** {gap_str}
- **Actionable:** {nugget}
"""
    return entry


def append_world_model(entries: list, config: dict):
    """Append entries to the world model file."""
    world_model_path = Path(config.get("world_model_file", "LITERATURE_WORLD_MODEL.md"))

    if not world_model_path.exists():
        header = f"""# Literature World-Model Map

This document tracks papers discovered through FLS scans, with structured summaries for quick reference.

> **Research Context:** {config.get('research_context', 'Research literature monitoring.')}

---

## Papers

"""
        world_model_path.parent.mkdir(parents=True, exist_ok=True)
        world_model_path.write_text(header)

    current = world_model_path.read_text().rstrip()
    world_model_path.write_text(current + "\n" + "\n".join(entries) + "\n")


# ============================================================================
# PDF DOWNLOAD
# ============================================================================

def download_pdf(paper: dict, config: dict) -> Optional[str]:
    """Download PDF for a paper. Returns filename if successful."""
    download_dir = Path(config.get("download_dir", "papers"))
    download_dir.mkdir(parents=True, exist_ok=True)

    arxiv_id = paper.get("arxiv_id", "")
    doi = (paper.get("doi") or "").strip()
    unpaywall_email = unpaywall.resolve_email(config=config)

    if arxiv_id:
        # arXiv PDF URL
        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
        year = paper.get("published", "")[:4] or "unknown"
        authors = paper.get("authors", ["Unknown"])
        first_author = authors[0].split()[-1] if authors else "Unknown"
        filename = f"{year}-{first_author}-{arxiv_id.replace('/', '-')}.pdf"
    elif paper.get("open_access_pdf"):
        pdf_url = paper["open_access_pdf"]
        filename = f"{paper.get('s2_id', 'unknown')[:16]}.pdf"
    elif doi and unpaywall_email:
        year = (paper.get("published", paper.get("year", "")) or "")[:4] or "unknown"
        authors = paper.get("authors", ["Unknown"])
        first_author = authors[0].split()[-1] if authors else "Unknown"

        try:
            doi_obj = unpaywall.doi_lookup(
                doi,
                unpaywall_email,
                delay_seconds=float(config.get("unpaywall_delay_seconds", 1.0)),
            )
            pdf_url = unpaywall.select_best_pdf_url(doi_obj) if doi_obj else None
            if not pdf_url:
                return None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            print(f"    Unpaywall lookup failed: HTTP Error {e.code}: {e.reason}")
            return None
        except Exception as e:
            print(f"    Unpaywall lookup failed: {e}")
            return None

        doi_slug = re.sub(r"[^A-Za-z0-9._-]+", "-", doi).strip("-")
        if len(doi_slug) > 80:
            doi_slug = doi_slug[:80] + "-" + hashlib.md5(doi.encode()).hexdigest()[:8]
        filename = f"{year}-{first_author}-{doi_slug}.pdf"
    else:
        return None

    filepath = download_dir / filename

    if filepath.exists():
        return filename  # Already downloaded

    try:
        time.sleep(1)  # Rate limiting
        urllib.request.urlretrieve(pdf_url, filepath)

        # Validate PDF
        with open(filepath, "rb") as f:
            magic = f.read(4)
        if magic != b"%PDF":
            filepath.unlink()
            return None

        return filename

    except Exception as e:
        print(f"    Download failed: {e}")
        if filepath.exists():
            filepath.unlink()
        return None


# ============================================================================
# MANIFEST MANAGEMENT
# ============================================================================

def load_manifest(config: dict) -> list:
    """Load papers manifest."""
    manifest_path = Path(config.get("manifest_file", "papers/papers_manifest.json"))
    if manifest_path.exists():
        with open(manifest_path) as f:
            return json.load(f)
    return []


def save_manifest(manifest: list, config: dict):
    """Save papers manifest."""
    manifest_path = Path(config.get("manifest_file", "papers/papers_manifest.json"))
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)


def load_notes(config: dict) -> dict:
    """Load literature notes file (summaries)."""
    notes_path = Path(config.get("notes_file", "literature_notes.json"))
    if notes_path.exists():
        with open(notes_path) as f:
            return json.load(f)
    return {"schema_version": 1, "notes": {}}


def add_to_manifest(paper: dict, local_file: str, config: dict):
    """Add a paper to the manifest."""
    manifest = load_manifest(config)

    arxiv_id = paper.get("arxiv_id", "")
    s2_id = paper.get("s2_id", "")
    doi = (paper.get("doi") or "").strip()

    # Check if already exists
    for entry in manifest:
        if arxiv_id and entry.get("arxiv_id") == arxiv_id:
            return
        if s2_id and entry.get("s2_id") == s2_id:
            return

    url = ""
    if arxiv_id:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    elif doi:
        url = f"https://doi.org/{doi}"
    elif paper.get("s2_url"):
        url = paper.get("s2_url", "")

    entry = {
        "arxiv_id": arxiv_id,
        "s2_id": s2_id,
        "doi": doi,
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "year": paper.get("published", paper.get("year", ""))[:4],
        "local_file": local_file,
        "url": url,
    }

    manifest.append(entry)
    save_manifest(manifest, config)


# ============================================================================
# DELTA SCAN
# ============================================================================

def run_delta_scan(config: dict):
    """Run incremental scan for new papers."""
    print("=" * 60)
    print("DELTA SCAN MODE")
    print("=" * 60)

    state = load_state(config)

    last_scan = state.get("last_scan_utc", "1970-01-01T00:00:00Z")
    print(f"\nLast scan: {last_scan}")

    lookback = config.get("lookback_days_default", 14)
    print(f"Lookback window: {lookback} days")

    # Check for keyword changes
    current_hash = compute_keywords_hash(config)
    if state.get("keywords_hash") != current_hash:
        print("\nKeywords changed - rechecking previously irrelevant papers...")
        state["keywords_hash"] = current_hash

    # Scan sources
    all_papers = []
    sources = config.get("sources", {})

    if sources.get("arxiv", True):
        print("\nScanning arXiv...")
        arxiv_papers = arxiv.query_all(config)
        all_papers.extend(arxiv_papers)

    if sources.get("semantic_scholar", True):
        print("\nScanning Semantic Scholar...")
        s2_papers = semantic_scholar.query_all(config)
        all_papers.extend(s2_papers)

    # Filter new papers
    seen_arxiv = set(state.get("seen_arxiv_ids", []))
    seen_s2 = set(state.get("seen_semantic_scholar_ids", []))

    new_papers = []
    for paper in all_papers:
        arxiv_id = paper.get("arxiv_id", "")
        s2_id = paper.get("s2_id", "")

        if arxiv_id and arxiv_id in seen_arxiv:
            continue
        if s2_id and s2_id in seen_s2:
            continue

        if not matches_keywords(paper, config):
            print(f"  Filtered out (no primary keyword): {paper.get('title', '')[:50]}...")
            if arxiv_id:
                state.setdefault("reviewed_irrelevant_arxiv_ids", []).append(arxiv_id)
            continue

        new_papers.append(paper)

    print(f"\nNew papers matching keywords: {len(new_papers)}")

    # Process new papers
    max_per_run = config.get("max_new_papers_per_run", 10)
    to_process = new_papers[:max_per_run]

    downloaded = 0
    world_model_entries = []
    unpaywall_email = unpaywall.resolve_email(config=config)

    for paper in to_process:
        arxiv_id = paper.get("arxiv_id", "")
        s2_id = paper.get("s2_id", "")

        print(f"  Processing: {paper.get('title', '')[:50]}...")

        # Download PDF
        local_file = None
        if config.get("open_access_only", True):
            if arxiv_id or paper.get("is_open_access") or (paper.get("doi") and unpaywall_email):
                local_file = download_pdf(paper, config)
                if local_file:
                    downloaded += 1
                    add_to_manifest(paper, local_file, config)

        # Generate world model entry
        if config.get("auto_world_model", True):
            entry = generate_world_model_entry(paper, config)
            world_model_entries.append(entry)

        # Mark as seen
        if arxiv_id:
            state.setdefault("seen_arxiv_ids", []).append(arxiv_id)
        if s2_id:
            state.setdefault("seen_semantic_scholar_ids", []).append(s2_id)

    # Update world model
    if world_model_entries:
        print(f"\nAdding {len(world_model_entries)} entries to world model...")
        append_world_model(world_model_entries, config)

    # Update state
    state["last_scan_utc"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_state(state, config)

    print("\n" + "=" * 60)
    print("DELTA SCAN SUMMARY")
    print("=" * 60)
    print(f"  New papers found:       {len(new_papers)}")
    print(f"  Papers processed:       {len(to_process)}")
    print(f"  PDFs downloaded:        {downloaded}")
    print(f"  World model entries:    {len(world_model_entries)}")

    world_model_path = config.get("world_model_file", "LITERATURE_WORLD_MODEL.md")
    print(f"\nState saved. World model: {world_model_path}")


# ============================================================================
# FULL SCAN (NOVELTY REPORT)
# ============================================================================

def run_full_scan(config: dict):
    """Run full scan and generate novelty report."""
    print("=" * 60)
    print("FULL LITERATURE SCAN")
    print("=" * 60)

    all_papers = []
    sources = config.get("sources", {})

    if sources.get("arxiv", True):
        print("\nScanning arXiv...")
        arxiv_papers = arxiv.query_all(config)
        all_papers.extend(arxiv_papers)

    if sources.get("semantic_scholar", True):
        print("\nScanning Semantic Scholar...")
        s2_papers = semantic_scholar.query_all(config)
        all_papers.extend(s2_papers)

    if sources.get("oeis", False):
        sequences = config.get("oeis_sequences", [])
        if sequences:
            print("\nScanning OEIS...")
            for seq in sequences:
                print(f"  Searching: {seq}")
                results = oeis.query(seq, config.get("oeis_delay_seconds", 1.5))
                all_papers.extend(results)

    # Generate report
    print("\nGenerating report...")

    report = f"""# Literature Scan Report

**Generated:** {datetime.now().strftime("%Y-%m-%d %H:%M")}
**Research Context:** {config.get('research_context', 'N/A')}

---

## Summary

- **arXiv papers found:** {len([p for p in all_papers if p.get('source') == 'arxiv'])}
- **Semantic Scholar papers:** {len([p for p in all_papers if p.get('source') == 'semantic_scholar'])}
- **OEIS sequences:** {len([p for p in all_papers if p.get('source') == 'oeis'])}

---

## Papers

"""

    for i, paper in enumerate(all_papers[:50], 1):  # Limit to 50
        title = paper.get("title", paper.get("name", "Unknown"))
        arxiv_id = paper.get("arxiv_id", "")
        s2_id = paper.get("s2_id", "")
        authors = ", ".join(paper.get("authors", [])[:3])
        year = paper.get("published", paper.get("year", ""))[:4]

        if arxiv_id:
            report += f"{i}. **{title}**\n   - {authors} ({year})\n   - arXiv: [{arxiv_id}](https://arxiv.org/abs/{arxiv_id})\n\n"
        elif s2_id:
            report += f"{i}. **{title}**\n   - {authors} ({year})\n   - S2: {s2_id[:8]}...\n\n"
        else:
            report += f"{i}. **{title}**\n\n"

    # Save report
    report_path = Path("LITERATURE_SCAN_REPORT.md")
    report_path.write_text(report)

    print(f"\nReport saved to: {report_path}")
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Total papers found: {len(all_papers)}")


# ============================================================================
# INTEGRITY CHECK
# ============================================================================

def run_integrity_check(config: dict):
    """Check integrity of manifest, PDFs, and world model."""
    print("Running integrity check...")

    manifest = load_manifest(config)
    download_dir = Path(config.get("download_dir", "papers"))

    errors = []

    # Check manifest entries have PDFs
    for entry in manifest:
        local_file = entry.get("local_file", "")
        if local_file and not (download_dir / local_file).exists():
            errors.append(f"Missing PDF: {local_file}")

    # Check for orphan PDFs
    if download_dir.exists():
        manifest_files = {e.get("local_file") for e in manifest if e.get("local_file")}
        for pdf in download_dir.glob("*.pdf"):
            if pdf.name not in manifest_files:
                errors.append(f"Orphan PDF: {pdf.name}")

    print(f"\nIntegrity check complete.")
    print(f"  Manifest entries: {len(manifest)}")
    print(f"  Errors: {len(errors)}")

    for err in errors:
        print(f"  - {err}")


# ============================================================================
# MAIN
# ============================================================================

def main():
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="FLS — Frontier Literature Scanner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    parser.add_argument(
        "--config", "-c",
        required=True,
        help="Path to configuration JSON file"
    )
    parser.add_argument(
        "--delta",
        action="store_true",
        help="Run incremental scan (download new papers)"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Run integrity check"
    )
    parser.add_argument(
        "--list-unsummarized",
        action="store_true",
        help="List papers that need summarization"
    )

    args = parser.parse_args()

    config = load_config(args.config)

    if args.check:
        run_integrity_check(config)
    elif args.delta:
        run_delta_scan(config)
    elif args.list_unsummarized:
        manifest = load_manifest(config)
        notes = load_notes(config)
        summarized_ids = set((notes.get("notes") or {}).keys())

        unsummarized = []
        for paper in manifest:
            paper_id = paper.get("arxiv_id") or paper.get("s2_id") or ""
            if paper_id and paper_id not in summarized_ids:
                unsummarized.append(paper)

        print(f"Papers in manifest: {len(manifest)}")
        print(f"Unsummarized: {len(unsummarized)}")

        for paper in unsummarized[:50]:
            paper_id = paper.get("arxiv_id") or paper.get("s2_id") or "?"
            title = paper.get("title", "")
            year = paper.get("year", "")
            print(f"- {paper_id} ({year}): {title}")

        if len(unsummarized) > 50:
            print(f"...and {len(unsummarized) - 50} more")
    else:
        run_full_scan(config)


if __name__ == "__main__":
    main()
