#!/usr/bin/env python3
"""
FLS — Interactive Pipeline Runner (single entrypoint)

This is a convenience wrapper that:
  - confirms your config
  - then runs the chosen steps (scan, local RAG indexing, etc.)

It is designed for first-time users and model-agnostic agent workflows.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from lib import dotenv, pdf_text


LAST_CONFIG_FILE = ".fls_last_config"


def _is_interactive() -> bool:
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _prompt_bool(question: str, *, default: bool = True) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    while True:
        ans = input(question + suffix).strip().lower()
        if not ans:
            return default
        if ans in {"y", "yes"}:
            return True
        if ans in {"n", "no"}:
            return False
        print("Please answer y or n.")


def _prompt_str(question: str, *, default: str = "") -> str:
    suffix = f" [{default}] " if default else " "
    ans = input(question + suffix).strip()
    return ans or default


def _prompt_int(question: str, *, default: int) -> int:
    while True:
        ans = input(f"{question} [{default}] ").strip()
        if not ans:
            return default
        try:
            return int(ans.replace("_", ""))
        except ValueError:
            print("Please enter a whole number.")


def _prompt_choice(question: str, choices: list[str], *, default: str) -> str:
    normalized = [c.strip().lower() for c in choices]
    default = default.strip().lower()
    opts = "/".join(normalized)
    while True:
        ans = input(f"{question} ({opts}) [{default}] ").strip().lower()
        if not ans:
            ans = default
        if ans in normalized:
            return ans
        print(f"Please enter one of: {opts}")


def _prompt_list(question: str, *, default: list[str], min_items: int = 0) -> list[str]:
    default_str = ", ".join(default) if default else ""
    while True:
        ans = input(f"{question} [{default_str}] ").strip()
        items: list[str]
        if not ans:
            items = list(default)
        else:
            parts = [p.strip() for p in ans.split(",")]
            items = [p for p in parts if p]
        if len(items) < min_items:
            print(f"Please provide at least {min_items} item(s).")
            continue
        return items


def _run_config_wizard(config_path: str, config: dict) -> dict:
    print("")
    print("CONFIG WIZARD")
    print("-" * 60)

    def is_placeholder_text(s: str) -> bool:
        return "describe your research focus here" in (s or "").lower()

    raw_primary = config.get("primary_keywords") if isinstance(config.get("primary_keywords"), list) else []
    raw_secondary = config.get("secondary_keywords") if isinstance(config.get("secondary_keywords"), list) else []
    raw_categories = config.get("arxiv_categories") if isinstance(config.get("arxiv_categories"), list) else []
    raw_context = str(config.get("research_context", "") or "").strip()

    primary_default = [] if _looks_like_template(config) else [str(x) for x in raw_primary if str(x).strip()]
    secondary_default = [] if _looks_like_template(config) else [str(x) for x in raw_secondary if str(x).strip()]
    categories_default = [str(x) for x in raw_categories if str(x).strip()]
    context_default = "" if is_placeholder_text(raw_context) else raw_context

    primary = _prompt_list("Primary keywords (comma-separated)", default=primary_default, min_items=1)
    secondary = _prompt_list("Secondary keywords (comma-separated)", default=secondary_default, min_items=0)
    categories = _prompt_list("arXiv categories (comma-separated)", default=categories_default, min_items=0)
    context = _prompt_str("Research context (1–3 sentences)", default=context_default)

    config["primary_keywords"] = primary
    config["secondary_keywords"] = secondary
    if categories:
        config["arxiv_categories"] = categories
    config["research_context"] = context

    Path(config_path).write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    print(f"Updated: {config_path}")
    return config


def _read_last_config_path() -> str:
    try:
        p = Path(LAST_CONFIG_FILE)
        if p.exists():
            return p.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return ""


def _write_last_config_path(config_path: str) -> None:
    try:
        Path(LAST_CONFIG_FILE).write_text((config_path or "").strip() + "\n", encoding="utf-8")
    except Exception:
        pass


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _looks_like_template(config: dict) -> bool:
    primary = config.get("primary_keywords") or []
    if isinstance(primary, list):
        joined = " ".join(str(x) for x in primary).lower()
        if "your-main-keyword" in joined or "another-required-term" in joined:
            return True
    return False


def _mask_value(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return "not set"
    # Avoid printing personal data; just indicate presence.
    return "set"


def _fmt_list(values: object, *, max_items: int = 8) -> str:
    if not isinstance(values, list):
        return "[]"
    items = [str(v) for v in values if str(v).strip()]
    if not items:
        return "[]"
    shown = items[:max_items]
    more = len(items) - len(shown)
    s = ", ".join(shown)
    if more > 0:
        s += f", ... (+{more})"
    return s


def _fmt_str(value: object, *, max_len: int = 120) -> str:
    s = str(value or "").strip().replace("\n", " ")
    if len(s) <= max_len:
        return s
    return s[: max_len - 3] + "..."


def _config_summary(config_path: str, config: dict) -> str:
    sources = config.get("sources") or {}
    primary = config.get("primary_keywords") or []
    secondary = config.get("secondary_keywords") or []

    categories = config.get("arxiv_categories") or []

    state_file = str(config.get("state_file", "fls_state.json"))
    world_model = str(config.get("world_model_file", "LITERATURE_WORLD_MODEL.md"))
    manifest = str(config.get("manifest_file", "papers/papers_manifest.json"))
    notes = str(config.get("notes_file", "literature_notes.json"))
    download_dir = str(config.get("download_dir", "papers"))

    open_access_only = bool(config.get("open_access_only", True))
    try:
        freshness_hours = float(config.get("freshness_hours", 6))
    except Exception:
        freshness_hours = 6.0
    max_new = int(config.get("max_new_papers_per_run", 10))
    max_results = int(config.get("max_results_per_source", 50))

    rag_db = str(config.get("rag_index_db", "rag/rag_index.sqlite"))
    rag_chunk = int(config.get("rag_chunk_chars", 1800))
    rag_overlap = int(config.get("rag_chunk_overlap_chars", 200))
    rag_ocr = bool(config.get("rag_ocr_enabled", False))

    arxiv_delay = float(config.get("arxiv_delay_seconds", 3))
    s2_delay = float(config.get("s2_delay_seconds", 1.0))
    oeis_delay = float(config.get("oeis_delay_seconds", 1.5))
    unpaywall_delay = float(config.get("unpaywall_delay_seconds", 1.0))

    unpaywall_email = (
        str(config.get("unpaywall_email", "")).strip() or os.environ.get("FLS_UNPAYWALL_EMAIL", "") or ""
    )
    s2_key = os.environ.get("FLS_SEMANTIC_SCHOLAR_API_KEY", "")

    lines = [
        f"Config: {config_path}",
        "",
        f"Primary keywords: {_fmt_list(primary)}",
        f"  - min hits: {int(config.get('min_primary_hits', 1))}",
        f"Secondary keywords: {_fmt_list(secondary)}",
        f"arXiv categories: {_fmt_list(categories)}",
        f"Research context: {_fmt_str(config.get('research_context', ''))}",
        "",
        "Sources:",
        f"  - arXiv: {bool(sources.get('arxiv', True))}",
        f"  - Semantic Scholar: {bool(sources.get('semantic_scholar', True))}",
        f"  - OEIS: {bool(sources.get('oeis', False))}",
        "",
        "Limits / policy:",
        f"  - open_access_only: {open_access_only}",
        f"  - freshness_hours: {freshness_hours}",
        f"  - max_new_papers_per_run: {max_new}",
        f"  - max_results_per_source: {max_results}",
        "",
        "Delays (rate limiting):",
        f"  - arxiv_delay_seconds: {arxiv_delay}",
        f"  - s2_delay_seconds: {s2_delay}",
        f"  - oeis_delay_seconds: {oeis_delay}",
        f"  - unpaywall_delay_seconds: {unpaywall_delay}",
        "",
        "Paths:",
        f"  - download_dir: {download_dir}",
        f"  - world_model_file: {world_model}",
        f"  - manifest_file: {manifest}",
        f"  - notes_file: {notes}",
        f"  - state_file: {state_file}",
        "",
        "Local RAG:",
        f"  - rag_index_db: {rag_db}",
        f"  - PDF extraction backend: {pdf_text.extraction_backend()}",
        f"  - chunking: {rag_chunk} chars (overlap {rag_overlap})",
        f"  - OCR enabled: {rag_ocr}",
        "",
        "Optional credentials:",
        f"  - Unpaywall email: {_mask_value(unpaywall_email)}",
        f"  - Semantic Scholar key: {_mask_value(s2_key)}",
    ]
    return "\n".join(lines)


def _detect_first_run(config: dict) -> tuple[bool, str]:
    state_path = Path(str(config.get("state_file", "fls_state.json")))
    if not state_path.exists():
        return True, f"State file not found ({state_path})"
    try:
        state = _load_json(state_path)
        last_scan = str(state.get("last_scan_utc", "1970-01-01T00:00:00Z"))
        if last_scan.startswith("1970-01-01"):
            return True, f"State file exists, but last_scan_utc={last_scan}"
        return False, f"last_scan_utc={last_scan}"
    except Exception:
        return True, f"State file exists but could not be parsed ({state_path})"


def _parse_last_scan_utc(value: str) -> Optional[datetime]:
    value = (value or "").strip()
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _freshness_status(config: dict) -> tuple[bool, str]:
    """Return (is_stale, human-readable reason)."""
    try:
        freshness_hours = float(config.get("freshness_hours", 6))
    except Exception:
        freshness_hours = 6.0

    state_path = Path(str(config.get("state_file", "fls_state.json")))
    if not state_path.exists():
        return True, f"state missing ({state_path}); threshold={freshness_hours}h"

    try:
        state = _load_json(state_path)
    except Exception:
        return True, f"state unreadable ({state_path}); threshold={freshness_hours}h"

    last_scan_raw = str(state.get("last_scan_utc", "") or "").strip()
    last_dt = _parse_last_scan_utc(last_scan_raw)
    if not last_dt:
        return True, f"last_scan_utc missing/invalid ({last_scan_raw!r}); threshold={freshness_hours}h"

    age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600.0
    stale = age_hours >= freshness_hours
    return stale, f"last_scan_utc={last_scan_raw} age_hours={age_hours:.1f} threshold={freshness_hours}h stale={stale}"

def _create_config_from_template(*, target_path: Path) -> str:
    fls_root = Path(__file__).resolve().parents[1]
    template = fls_root / "templates" / "config.template.json"
    if template.exists():
        target_path.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")
        return "Created fls_config.json from template."

    # Fallback: create a minimal config (still requires user editing keywords).
    minimal = {
        "primary_keywords": ["your-main-keyword"],
        "secondary_keywords": [],
        "min_primary_hits": 1,
        "arxiv_categories": ["math.CO"],
        "sources": {"arxiv": True, "semantic_scholar": True, "oeis": False},
        "research_context": "Research literature monitoring.",
        "download_dir": "papers",
        "state_file": "fls_state.json",
        "manifest_file": "papers/papers_manifest.json",
        "world_model_file": "LITERATURE_WORLD_MODEL.md",
        "notes_file": "literature_notes.json",
        "rag_index_db": "rag/rag_index.sqlite",
    }
    target_path.write_text(json.dumps(minimal, indent=2) + "\n", encoding="utf-8")
    return "Created fls_config.json (minimal)."


def _ensure_config_exists(config_path: str, *, yes: bool, auto_create_default: bool) -> str:
    if config_path:
        if Path(config_path).exists():
            return config_path
        raise FileNotFoundError(f"Config file not found: {config_path}")

    # Try defaults
    if Path("fls_config.json").exists():
        return "fls_config.json"

    last = _read_last_config_path()
    if last and Path(last).exists():
        if yes or not _is_interactive():
            return last
        if _prompt_bool(f"Found last-used config at {last}. Use it?", default=True):
            return last

    # No config found
    if yes or not _is_interactive():
        if auto_create_default:
            msg = _create_config_from_template(target_path=Path("fls_config.json"))
            print(msg)
            return "fls_config.json"
        raise FileNotFoundError("No config found (expected fls_config.json). Pass --config or create one from template.")

    print("No config file found.")
    if _prompt_bool("Create fls_config.json from the template now?", default=True):
        msg = _create_config_from_template(target_path=Path("fls_config.json"))
        print(msg)
        return "fls_config.json"

    raise FileNotFoundError("Config file not found.")


def _run_cmd(cmd: list[str], *, dry_run: bool) -> int:
    printable = " ".join(cmd)
    print(f"\n→ {printable}")
    if dry_run:
        return 0
    proc = subprocess.run(cmd)
    return int(proc.returncode)


def _preflight_questions(
    config_path: str,
    config: dict,
    *,
    scan_mode: str,
    do_rag: bool,
    include_repo: bool,
    prune: bool,
) -> tuple[list[str], list[str]]:
    required: list[str] = []
    recommended: list[str] = []

    sources = config.get("sources") or {}
    s2_enabled = bool(sources.get("semantic_scholar", True))

    primary = config.get("primary_keywords") or []
    primary_count = len(primary) if isinstance(primary, list) else 0

    research_context = str(config.get("research_context", "") or "").strip()

    open_access_only = bool(config.get("open_access_only", True))
    unpaywall_email = str(config.get("unpaywall_email", "") or "").strip() or os.environ.get("FLS_UNPAYWALL_EMAIL", "")
    s2_key = os.environ.get("FLS_SEMANTIC_SCHOLAR_API_KEY", "")

    if scan_mode != "skip":
        if primary_count == 0:
            required.append(
                f"What primary keywords should we track for your domain? (Edit primary_keywords in {config_path}.)"
            )
        if _looks_like_template(config):
            required.append(
                f"Replace the template placeholder keywords in {config_path} with your real research terms (primary_keywords)."
            )

        if not research_context or "describe your research focus here" in research_context.lower():
            recommended.append(
                f"What is your research context (1–3 sentences) so agents can judge relevance? (Edit research_context in {config_path}.)"
            )

        if s2_enabled and not s2_key:
            recommended.append(
                "Do you want to add a Semantic Scholar API key to avoid rate limits (HTTP 429)? If yes, set FLS_SEMANTIC_SCHOLAR_API_KEY in .env.local."
            )

        if open_access_only and not unpaywall_email:
            recommended.append(
                "Do you want DOI open-access fallback via Unpaywall? If yes, set FLS_UNPAYWALL_EMAIL in .env.local (no API key required)."
            )

    if do_rag:
        backend = pdf_text.extraction_backend()
        if backend == "none":
            recommended.append(
                "Local RAG can’t extract PDF text yet. Install `pypdf` or `pdfplumber` (pip), or `pdftotext` (Poppler) for better indexing."
            )
        if not include_repo:
            recommended.append(
                "Do you want repo-RAG (index repo markdown/code too)? If yes, re-run with --include-repo."
            )
        if include_repo:
            recommended.append(
                "Do you want repo-RAG enabled? If yes, confirm you’re okay indexing repo text/code (and consider adjusting --max-text-bytes)."
            )
        if prune:
            recommended.append("Prune is enabled; confirm you’re okay removing index entries for deleted/moved files.")

    return required, recommended


def main() -> int:
    dotenv.load_dotenv()

    parser = argparse.ArgumentParser(
        description="FLS pipeline runner (interactive)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  # Interactive (recommended)\n"
            "  python3 scripts/fls.py --config fls_config.json\n"
            "\n"
            "  # Agent / non-interactive (delta-if-stale default)\n"
            "  python3 scripts/fls.py --config fls_config.json --yes\n"
            "\n"
            "  # Force delta scan now\n"
            "  python3 scripts/fls.py --config fls_config.json --yes --delta\n"
            "\n"
            "  # Preview configuration (no execution)\n"
            "  python3 scripts/fls.py --config fls_config.json --print-config\n"
            "\n"
            "  # Preview commands (no execution)\n"
            "  python3 scripts/fls.py --config fls_config.json --yes --dry-run\n"
            "\n"
            "  # Repo-RAG (also index repo markdown/code)\n"
            "  python3 scripts/fls.py --config fls_config.json --yes --include-repo\n"
        ),
    )
    parser.add_argument("--config", "-c", default="", help="Config path (default: fls_config.json)")
    parser.add_argument("--yes", action="store_true", help="Run non-interactively with defaults (no prompts)")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run, but do not execute")
    parser.add_argument("--print-config", action="store_true", help="Print config summary and exit")

    scan_group = parser.add_mutually_exclusive_group()
    scan_group.add_argument("--delta", action="store_true", help="Run delta scan (download new papers)")
    scan_group.add_argument("--full", action="store_true", help="Run full scan report (no downloads)")
    scan_group.add_argument("--no-scan", action="store_true", help="Skip scanning")
    parser.add_argument(
        "--if-stale",
        action="store_true",
        help="If running a delta scan, only run it when stale (per freshness_hours in config)",
    )

    rag_group = parser.add_mutually_exclusive_group()
    rag_group.add_argument("--rag", action="store_true", help="Build/update local RAG index")
    rag_group.add_argument("--no-rag", action="store_true", help="Skip local RAG indexing")

    parser.add_argument("--include-repo", action="store_true", help="Also index repo text/code files (repo-RAG)")
    parser.add_argument("--prune", action="store_true", help="Prune indexed files that no longer exist")
    parser.add_argument("--max-text-bytes", type=int, default=2_000_000, help="Max size for repo text files")

    args = parser.parse_args()

    interactive = _is_interactive()
    assume_yes = bool(args.yes) or bool(args.dry_run)

    if not assume_yes and not interactive and not args.print_config:
        print("ERROR: Non-interactive mode detected. Re-run with --yes (or use --print-config / --dry-run).", file=sys.stderr)
        return 2

    try:
        config_path = _ensure_config_exists(args.config, yes=assume_yes, auto_create_default=bool(args.yes))
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    _write_last_config_path(config_path)

    try:
        config = _load_json(Path(config_path))
    except Exception as e:
        print(f"ERROR: Could not parse config JSON: {config_path}\n{e}", file=sys.stderr)
        return 2

    while True:
        print("=" * 60)
        print("FLS PIPELINE RUNNER")
        print("=" * 60)
        print(_config_summary(config_path, config))

        first_run, first_run_reason = _detect_first_run(config)
        print("")
        print(f"First run: {first_run} ({first_run_reason})")

        stale, stale_reason = _freshness_status(config)
        print(f"Freshness: {stale_reason}")

        if _looks_like_template(config):
            print("")
            print("WARN: Your config looks like the template. You probably want to edit primary_keywords before scanning.")

        if args.print_config:
            # Show what an agent/human should fix before running with default behavior.
            scan_mode = "skip" if args.no_scan else ("full" if args.full else ("delta" if args.delta else "delta"))
            do_rag = False if args.no_rag else (True if args.rag else True)
            required, recommended = _preflight_questions(
                config_path,
                config,
                scan_mode=scan_mode,
                do_rag=do_rag,
                include_repo=bool(args.include_repo),
                prune=bool(args.prune),
            )
            if required or recommended:
                print("")
                print("Preflight (agent questions):")
                if required:
                    print("  ACTION REQUIRED:")
                    for q in required:
                        print(f"   - {q}")
                if recommended:
                    print("  RECOMMENDED:")
                    for q in recommended:
                        print(f"   - {q}")
            return 0

        if assume_yes:
            break

        print("")
        print(f"Config file: {config_path}")
        if _prompt_bool("Proceed with this configuration?", default=True):
            break

        next_path = _prompt_str("Enter another config path (or leave blank to abort):", default="")
        if not next_path:
            print("Aborted.")
            return 0
        if not Path(next_path).exists():
            print(f"Config file not found: {next_path}")
            continue
        try:
            config_path = next_path
            _write_last_config_path(config_path)
            config = _load_json(Path(config_path))
        except Exception as e:
            print(f"ERROR: Could not parse config JSON: {config_path}\n{e}")
            continue

    # Decide scan mode
    scan_mode: str
    if args.no_scan:
        scan_mode = "skip"
    elif args.full:
        scan_mode = "full"
    elif args.delta:
        scan_mode = "delta_if_stale" if args.if_stale else "delta"
    elif args.if_stale:
        scan_mode = "delta_if_stale"
    else:
        if assume_yes:
            # Agent-friendly default: avoid unnecessary network calls.
            scan_mode = "delta_if_stale"
        else:
            choice = _prompt_choice("Scan mode", ["delta-if-stale", "delta", "full", "skip"], default="delta-if-stale")
            scan_mode = choice.replace("-", "_")

    # Decide RAG indexing
    do_rag: bool
    if args.no_rag:
        do_rag = False
    elif args.rag:
        do_rag = True
    else:
        do_rag = True if assume_yes else _prompt_bool("Build/refresh local RAG index after scan?", default=True)

    include_repo = bool(args.include_repo)
    prune = bool(args.prune)
    max_text_bytes = int(args.max_text_bytes)

    if do_rag and (not assume_yes):
        if not args.include_repo:
            include_repo = _prompt_bool("Also index repo markdown/code files (repo-RAG)?", default=False)
        if include_repo and not args.include_repo:
            max_text_bytes = _prompt_int("Max size for repo text/code files (bytes)", default=max_text_bytes)
        if not args.prune:
            prune = _prompt_bool("Prune missing files from the RAG index?", default=False)

    required, recommended = _preflight_questions(
        config_path,
        config,
        scan_mode=scan_mode,
        do_rag=do_rag,
        include_repo=include_repo,
        prune=prune,
    )
    if required or recommended:
        print("")
        print("Preflight (agent questions):")
        if required:
            print("  ACTION REQUIRED:")
            for q in required:
                print(f"   - {q}")
        if recommended:
            print("  RECOMMENDED:")
            for q in recommended:
                print(f"   - {q}")

    exit_code = 0
    if required:
        if args.dry_run:
            exit_code = 2
        elif assume_yes:
            print("\nRefusing to run in --yes mode until ACTION REQUIRED items are addressed.")
            return 2
        else:
            if _prompt_bool("Run the config wizard now to address ACTION REQUIRED items?", default=True):
                try:
                    config = _run_config_wizard(config_path, config)
                except KeyboardInterrupt:
                    print("\nAborted.")
                    return 0

                print("")
                print("Updated config summary:")
                print(_config_summary(config_path, config))

                required2, recommended2 = _preflight_questions(
                    config_path,
                    config,
                    scan_mode=scan_mode,
                    do_rag=do_rag,
                    include_repo=include_repo,
                    prune=prune,
                )
                if required2 or recommended2:
                    print("")
                    print("Preflight (agent questions):")
                    if required2:
                        print("  ACTION REQUIRED:")
                        for q in required2:
                            print(f"   - {q}")
                    if recommended2:
                        print("  RECOMMENDED:")
                        for q in recommended2:
                            print(f"   - {q}")
                if required2:
                    print("")
                    print("Edit your config, then re-run this command.")
                    if _prompt_bool("Abort now?", default=True):
                        return 0
            else:
                print("")
                print("Edit your config, then re-run this command.")
                if _prompt_bool("Abort now?", default=True):
                    return 0

    # Final confirmation
    if not assume_yes:
        print("")
        print("Planned steps:")
        print(f"  - scan: {scan_mode}")
        print(f"  - rag_index: {do_rag} (include_repo={include_repo}, prune={prune})")
        if not _prompt_bool("Run these steps now?", default=True):
            print("Aborted.")
            return 0

    script_dir = Path(__file__).resolve().parent
    scan_script = script_dir / "literature_scan.py"
    rag_script = script_dir / "rag_index.py"

    cmds: list[list[str]] = []
    if scan_mode == "delta":
        cmds.append([sys.executable, str(scan_script), "--config", config_path, "--delta"])
    elif scan_mode == "delta_if_stale":
        stale, stale_reason = _freshness_status(config)
        print(f"\nFreshness check: {stale_reason}")
        if stale:
            cmds.append([sys.executable, str(scan_script), "--config", config_path, "--delta"])
        else:
            print("Skipping delta scan (fresh).")
    elif scan_mode == "full":
        cmds.append([sys.executable, str(scan_script), "--config", config_path])

    if do_rag:
        cmd = [sys.executable, str(rag_script), "--config", config_path]
        if include_repo:
            cmd.append("--include-repo")
            cmd.extend(["--max-text-bytes", str(int(max_text_bytes))])
        if prune:
            cmd.append("--prune")
        cmds.append(cmd)

    for cmd in cmds:
        rc = _run_cmd(cmd, dry_run=bool(args.dry_run))
        if rc != 0:
            return rc

    print("\nDone.")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
