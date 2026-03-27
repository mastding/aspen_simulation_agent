#!/usr/bin/env python3
"""Apply prompt candidate increments into backend prompt files.

This script does NOT run automatically. Use --apply to write changes.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def extract_increment(candidate_text: str) -> str:
    # Find the training increment marker.
    marker = "\u8bad\u7ec3\u540e"
    idx = candidate_text.find(marker)
    if idx == -1:
        return ""
    line_start = candidate_text.rfind("\n", 0, idx)
    if line_start == -1:
        line_start = 0
    return candidate_text[line_start:].strip()


def _parse_zone_bullets(increment: str) -> dict[str, list[str]]:
    """Parse increment text into {zone_name: [bullet1, bullet2, ...]}."""
    zone_bullets: dict[str, list[str]] = {}
    for line in increment.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Match lines like: - [字段完整性检查] 当blocks_Sep_data配置写入失败时...
        m = re.match(r'^-\s*\[([^\]]+)\]\s*(.+)$', line)
        if m:
            zone_name = m.group(1).strip()
            bullet_text = m.group(2).strip()
            zone_bullets.setdefault(zone_name, []).append(bullet_text)
    return zone_bullets


def _inject_into_zones(target_text: str, zone_bullets: dict[str, list[str]]) -> str:
    """Inject bullets into their corresponding OPTIMIZATION_ZONE areas."""
    result = target_text
    for zone_name, bullets in zone_bullets.items():
        if not bullets:
            continue

        # Build numbered list content
        numbered_items = []
        for i, bullet in enumerate(bullets, 1):
            numbered_items.append(f"{i}. {bullet}")
        new_content = "\n".join(numbered_items)

        # Find the zone and replace its content
        pattern = re.compile(
            rf'(<!-- OPTIMIZATION_ZONE_START: {re.escape(zone_name)} -->)\s*'
            rf'(.*?)\s*'
            rf'(<!-- OPTIMIZATION_ZONE_END: {re.escape(zone_name)} -->)',
            re.DOTALL
        )
        match = pattern.search(result)
        if match:
            existing_content = match.group(2).strip()
            # If zone already has content (not just comments), merge
            if existing_content and not existing_content.startswith('<!--'):
                # Extract existing numbered items
                existing_items = re.findall(r'^\s*\d+\.\s*(.+?)$', existing_content, re.MULTILINE)
                existing_normalized = {item.strip().lower() for item in existing_items}
                # Only add new bullets that don't already exist
                new_bullets = []
                for bullet in bullets:
                    if bullet.strip().lower() not in existing_normalized:
                        new_bullets.append(bullet)
                if not new_bullets:
                    continue
                # Renumber all items
                all_items = existing_items + new_bullets
                numbered_items = [f"{i}. {item}" for i, item in enumerate(all_items, 1)]
                new_content = "\n".join(numbered_items)

            replacement = f"{match.group(1)}\n{new_content}\n{match.group(3)}"
            result = result[:match.start()] + replacement + result[match.end():]
        else:
            # Zone not found, skip (don't append randomly)
            print(f"  Warning: OPTIMIZATION_ZONE '{zone_name}' not found in target file")

    return result


def inject_increment(target_text: str, var_name: str, increment: str) -> str:
    if not increment:
        return target_text
    # Skip only when exactly same increment block already exists.
    if increment.strip() and increment.strip() in target_text:
        return target_text

    # Try zone-based injection first
    zone_bullets = _parse_zone_bullets(increment)
    if zone_bullets:
        return _inject_into_zones(target_text, zone_bullets)

    # Fallback: legacy append mode (for old-format increments without zone tags)
    pattern = re.compile(rf"({var_name}\s*=\s*f?\"\"\".*?)(\"\"\")", re.S)
    m = pattern.search(target_text)
    if not m:
        raise RuntimeError(f"prompt variable not found: {var_name}")

    before = m.group(1)
    after = m.group(2)
    new_body = before.rstrip() + "\n\n" + increment + "\n"
    return target_text[: m.start()] + new_body + after + target_text[m.end() :]


def backup_file(path: Path) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = path.with_suffix(path.suffix + f".bak_{stamp}")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return bak


def resolve_candidate_path(run_dir: Path, base_name: str, legacy_names: list[str]) -> Path | None:
    # New naming: <base_name>-run_xxx.txt
    direct = run_dir / f"{base_name}-{run_dir.name}.txt"
    if direct.exists() and direct.is_file():
        return direct

    # Fallback: any run-suffixed candidate, newest first.
    candidates = sorted(run_dir.glob(f"{base_name}-run_*.txt"), key=lambda p: p.stat().st_mtime, reverse=True)
    for p in candidates:
        if p.exists() and p.is_file():
            return p

    # Backward compatibility: legacy names.
    for name in legacy_names:
        p = run_dir / name
        if p.exists() and p.is_file():
            return p
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, help="training run dir with *-run_<run_id>.txt or legacy *_0211.txt")
    ap.add_argument("--prompt-dir", default="/run/code/dinglei/aspen_simulation_n../prompt")
    ap.add_argument("--apply", action="store_true", help="write changes; otherwise dry run")
    ap.add_argument("--only", default="", help="comma-separated candidate base names to apply")
    ap.add_argument("--emit-json", action="store_true", help="print machine-readable JSON output")
    args = ap.parse_args()

    run_dir = Path(args.run_dir)
    prompt_dir = Path(args.prompt_dir)

    mapping = [
        ("system_prompt_candidate", ["system_prompt_candidate_0211.txt", "system_prompt_candidate.txt"], prompt_dir / "llm_prompt.py", "system_prompt"),
        ("schema_check_prompt_candidate", ["schema_check_prompt_candidate_0211.txt", "schema_check_prompt_candidate.txt"], prompt_dir / "schema_check.py", "schema_check_prompt"),
        ("thought_process_prompt_candidate", ["thought_process_prompt_candidate_0211.txt", "thought_process_prompt_candidate.txt"], prompt_dir / "thought_process.py", "thought_process_prompt"),
    ]

    only_set = {x.strip() for x in str(args.only or "").split(",") if x.strip()}
    if only_set:
        mapping = [m for m in mapping if m[0] in only_set]

    details = []
    changes = []
    processed = []
    skipped_missing = []

    for base_name, legacy_names, target_path, var_name in mapping:
        cand_path = resolve_candidate_path(run_dir, base_name, legacy_names)
        if cand_path is None:
            skipped_missing.append(base_name)
            details.append({
                "base_name": base_name,
                "candidate_file": None,
                "target_path": str(target_path),
                "changed": False,
                "status": "missing_candidate",
                "content_after": read_text(target_path),
            })
            continue

        processed.append((base_name, cand_path.name))
        increment = extract_increment(read_text(cand_path))
        target_text = read_text(target_path)

        if not increment.strip():
            details.append({
                "base_name": base_name,
                "candidate_file": cand_path.name,
                "target_path": str(target_path),
                "changed": False,
                "status": "empty_increment",
                "content_after": target_text,
            })
            continue

        new_text = inject_increment(target_text, var_name, increment)
        changed = new_text != target_text
        details.append({
            "base_name": base_name,
            "candidate_file": cand_path.name,
            "target_path": str(target_path),
            "changed": changed,
            "status": "changed" if changed else "no_change",
            "content_after": new_text,
        })
        if changed:
            changes.append((target_path, new_text))

    if not processed and not details:
        result = {
            "ok": True,
            "mode": "apply" if args.apply else "dry-run",
            "message": "no prompt candidates found in run dir",
            "processed": [],
            "skipped_missing": skipped_missing,
            "details": details,
            "updated_files": [],
        }
        if args.emit_json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print("no prompt candidates found in run dir")
        return

    updated_files = []
    if args.apply:
        for p, new_text in changes:
            bak = backup_file(p)
            p.write_text(new_text, encoding="utf-8")
            updated_files.append({"path": str(p), "backup": str(bak)})

    result = {
        "ok": True,
        "mode": "apply" if args.apply else "dry-run",
        "processed": [{"base_name": a, "candidate_file": b} for a, b in processed],
        "skipped_missing": skipped_missing,
        "details": details,
        "updated_files": updated_files,
    }

    if args.emit_json:
        print(json.dumps(result, ensure_ascii=False))
        return

    if not changes:
        print("no changes needed")
        if skipped_missing:
            print("skipped missing candidates:", ",".join(skipped_missing))
        return

    if not args.apply:
        print("dry run: changes pending")
        print("processed candidates:", ", ".join([f"{a}:{b}" for a,b in processed]))
        for p, _ in changes:
            print(f"  would update: {p}")
        return

    print("processed candidates:", ", ".join([f"{a}:{b}" for a,b in processed]))
    for item in updated_files:
        print(f"updated: {item['path']} (backup: {item['backup']})")


if __name__ == "__main__":
    main()
