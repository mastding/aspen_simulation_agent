#!/usr/bin/env python3
"""
Apply schema_descriptions candidate to target file.

Default mode is dry-run. Use --apply to write target and create backup.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply schema candidate file")
    parser.add_argument("--candidate", required=True, help="Path to schema_descriptions candidate json")
    parser.add_argument(
        "--target",
        required=True,
        help="Path to target schema_descriptions json",
    )
    parser.add_argument("--apply", action="store_true", help="Write target file (default: dry-run)")
    return parser.parse_args()


def load_rows(path: Path) -> List[Dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"not a JSON list: {path}")
    return [row for row in data if isinstance(row, dict)]


def summarize_diff(target_rows: List[Dict[str, Any]], candidate_rows: List[Dict[str, Any]]) -> Dict[str, int]:
    target_keys = {(str(x.get("source", "")), str(x.get("path", "")), str(x.get("description", ""))) for x in target_rows}
    candidate_keys = {(str(x.get("source", "")), str(x.get("path", "")), str(x.get("description", ""))) for x in candidate_rows}
    return {
        "target_items": len(target_rows),
        "candidate_items": len(candidate_rows),
        "added_items": len(candidate_keys - target_keys),
        "removed_items": len(target_keys - candidate_keys),
    }


def main() -> None:
    args = parse_args()
    candidate_path = Path(args.candidate)
    target_path = Path(args.target)

    candidate_rows = load_rows(candidate_path)
    target_rows = load_rows(target_path) if target_path.exists() else []

    # Merge mode: candidate can be full rows or delta rows with change_type.
    target_map = {
        (str(x.get("source", "")), str(x.get("path", ""))): {
            "source": str(x.get("source", "")),
            "path": str(x.get("path", "")),
            "description": str(x.get("description", "")),
        }
        for x in target_rows
        if isinstance(x, dict)
    }

    before_map = dict(target_map)
    for row in candidate_rows:
        key = (str(row.get("source", "")), str(row.get("path", "")))
        target_map[key] = {
            "source": key[0],
            "path": key[1],
            "description": str(row.get("description", "")),
        }

    merged_rows = list(target_map.values())
    diff = summarize_diff(target_rows, merged_rows)

    if not args.apply:
        print(json.dumps({"mode": "dry-run", "target": str(target_path), "candidate_items": len(candidate_rows), **diff}, ensure_ascii=False))
        return

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if target_path.exists():
        backup_path = target_path.with_name(f"{target_path.name}.bak_{stamp}")
        backup_path.write_text(target_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"backup: {backup_path}")
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(json.dumps(merged_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"mode": "apply", "target": str(target_path), "candidate_items": len(candidate_rows), **diff}, ensure_ascii=False))


if __name__ == "__main__":
    main()
