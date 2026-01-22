"""
OEIS query helper.

This is a lightweight JSON search wrapper (no API key required).
"""

from __future__ import annotations

import json
import time
import urllib.request


def query(sequence: list, delay_seconds: float = 1.5, raise_on_error: bool = False) -> list:
    """Query OEIS for a sequence (list of integers)."""
    seq_str = ",".join(str(x) for x in sequence)
    url = f"https://oeis.org/search?fmt=json&q={seq_str}"

    try:
        time.sleep(delay_seconds)
        with urllib.request.urlopen(url, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        results = []
        entries = []
        if isinstance(data, dict):
            entries = data.get("results", []) or []
        elif isinstance(data, list):
            entries = data

        for entry in entries:
            results.append(
                {
                    "oeis_id": f"A{entry.get('number', '')}",
                    "name": entry.get("name", ""),
                    "sequence": entry.get("data", ""),
                    "source": "oeis",
                }
            )

        return results

    except Exception as e:
        if raise_on_error:
            raise
        print(f"  OEIS query failed: {e}")
        return []
