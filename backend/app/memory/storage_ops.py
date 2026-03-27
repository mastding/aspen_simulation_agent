from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any, Dict, List

from . import matching


def _list_validated_dynamic_methods(*, deps: Dict[str, Any]) -> List[str]:
    # DISABLED: dynamic method aliases feature removed
    return []
    loader = deps.get("list_validated_dynamic_methods_fn")
    if callable(loader):
        try:
            values = loader()
            if isinstance(values, list):
                return [str(v).strip().upper() for v in values if str(v).strip()]
        except Exception:
            return []
    return []


def _list_validated_dynamic_component_aliases(*, deps: Dict[str, Any]) -> Dict[str, str]:
    # Dynamic component aliases are disabled. Component discovery remains based
    # on the static alias list in matching.py.
    return {}


def _sync_dynamic_method_candidates(*, task_text: str, strategy_text: str, config_snippet: str, source_rollout_id: str, deps: Dict[str, Any]) -> None:
    # DISABLED: dynamic method aliases feature removed
    return
    if not callable(deps.get("db_connect_fn")):
        return
    merged = "\n".join([str(task_text or ""), str(strategy_text or ""), str(config_snippet or "")])
    known_methods = _list_validated_dynamic_methods(deps=deps)
    candidates = matching.extract_method_candidates(merged, dynamic_methods=known_methods)
    if not candidates:
        return
    now = time.time()
    insert_sql = """
        INSERT INTO dynamic_method_aliases(
            raw_text, normalized_value, source, confidence, seen_count, accepted_count,
            status, first_seen_rollout_id, example_text, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    update_sql = """
        UPDATE dynamic_method_aliases
        SET normalized_value=?, confidence=?, seen_count=?, accepted_count=?, status=?, updated_at=?, example_text=?
        WHERE raw_text=?
    """
    with deps["db_connect_fn"]() as conn:
        for item in candidates:
            raw_text = str(item.get("raw_text", "")).strip()
            normalized = str(item.get("normalized_value", "")).strip().upper()
            if not raw_text or not normalized:
                continue
            row = conn.execute(
                "SELECT seen_count, accepted_count, status, confidence FROM dynamic_method_aliases WHERE raw_text = ?",
                (raw_text,),
            ).fetchone()
            confidence = float(item.get("confidence", 0.0) or 0.0)
            if row is None:
                seen_count = 1
                accepted_count = 0
                status = "validated" if confidence >= 0.98 else "candidate"
                if status == "validated":
                    accepted_count = 1
                conn.execute(
                    insert_sql,
                    (
                        raw_text,
                        normalized,
                        str(item.get("source", "rule_context") or "rule_context"),
                        confidence,
                        seen_count,
                        accepted_count,
                        status,
                        str(source_rollout_id or ""),
                        merged[:500],
                        now,
                        now,
                    ),
                )
            else:
                seen_count = int(row["seen_count"] or 0) + 1
                old_conf = float(row["confidence"] or 0.0)
                accepted_count = int(row["accepted_count"] or 0)
                status = str(row["status"] or "candidate")
                new_conf = max(old_conf, confidence)
                if status != "validated" and (seen_count >= 2 or new_conf >= 0.98):
                    status = "validated"
                    accepted_count = max(1, accepted_count + 1)
                conn.execute(
                    update_sql,
                    (
                        normalized,
                        new_conf,
                        seen_count,
                        accepted_count,
                        status,
                        now,
                        merged[:500],
                        raw_text,
                    ),
                )
        conn.commit()


def _sync_dynamic_component_candidates(*, task_text: str, strategy_text: str, config_snippet: str, source_rollout_id: str, deps: Dict[str, Any]) -> None:
    return


def memory_tags(task_type: str, memory_kind: str, equipment_type: str = "") -> List[str]:
    tags = [str(task_type or "unknown"), f"kind:{memory_kind}"]
    if equipment_type:
        tags.append(f"equipment:{equipment_type}")
    return tags


def render_memory_markdown(
    *,
    memory_id: str,
    task_text: str,
    task_type: str,
    tags: List[str],
    reward: float,
    tool_call_count: int,
    strategy_text: str,
    config_snippet: str,
    pitfalls_text: str,
    failure_reason: str,
    fix_action: str,
    lesson: str,
    source_rollout_id: str,
    features: Dict[str, Any],
) -> str:
    lines: List[str] = []
    lines.append(f"# Aspen \u5386\u53f2\u7ecf\u9a8c: {memory_id}")
    lines.append("")
    lines.append("## \u5143\u4fe1\u606f")
    lines.append(f"- \u4efb\u52a1\u7c7b\u578b: {task_type or 'unknown'}")
    lines.append(f"- \u5956\u52b1\u503c: {round(float(reward or 0.0), 6)}")
    lines.append(f"- \u5de5\u5177\u8c03\u7528\u6b21\u6570: {int(tool_call_count or 0)}")
    lines.append(f"- \u6765\u6e90\u4efb\u52a1ID: {source_rollout_id}")
    lines.append(f"- Schema\u54c8\u5e0c: {features.get('schema_hash', '')}")
    lines.append(f"- \u6807\u7b7e: {', '.join([str(t) for t in tags if t])}")
    lines.append("")
    lines.append("## \u4efb\u52a1\u63cf\u8ff0")
    lines.append(task_text or "")
    lines.append("")
    lines.append("## \u7ecf\u9a8c\u6b65\u9aa4")
    lines.append(strategy_text or "")
    lines.append("")
    lines.append("## \u5173\u952e\u914d\u7f6e")
    lines.append("```json")
    lines.append((config_snippet or "").strip())
    lines.append("```")
    lines.append("")
    lines.append("## \u907f\u5751\u7ecf\u9a8c")
    if pitfalls_text:
        lines.append(pitfalls_text)
    if failure_reason:
        lines.append(f"- \u5931\u8d25\u539f\u56e0: {failure_reason}")
    if fix_action:
        lines.append(f"- \u4fee\u590d\u52a8\u4f5c: {fix_action}")
    if lesson:
        lines.append(f"- \u7ecf\u9a8c\u6559\u8bad: {lesson}")
    lines.append("")
    lines.append("## \u5339\u914d\u5b57\u6bb5")
    lines.append("```json")
    lines.append(json.dumps(features.get("match_fields", {}), ensure_ascii=False, indent=2))
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def write_memory_markdown_and_index(
    *,
    memory_id: str,
    task_hash: str,
    task_text: str,
    task_type: str,
    tags: List[str],
    reward: float,
    tool_call_count: int,
    strategy_text: str,
    config_snippet: str,
    pitfalls_text: str,
    failure_reason: str,
    fix_action: str,
    lesson: str,
    source_rollout_id: str,
    features: Dict[str, Any],
    deps: Dict[str, Any],
) -> str:
    now = time.time()
    memory_docs_dir: Path = deps["memory_docs_dir"]
    memory_docs_dir.mkdir(parents=True, exist_ok=True)

    md_rel = f"memory_docs/{memory_id}.md"
    final_abs = memory_docs_dir / f"{memory_id}.md"

    content = render_memory_markdown(
        memory_id=memory_id,
        task_text=task_text,
        task_type=task_type,
        tags=tags,
        reward=reward,
        tool_call_count=tool_call_count,
        strategy_text=strategy_text,
        config_snippet=config_snippet,
        pitfalls_text=pitfalls_text,
        failure_reason=failure_reason,
        fix_action=fix_action,
        lesson=lesson,
        source_rollout_id=source_rollout_id,
        features=features,
    )
    final_abs.write_text(content, encoding="utf-8")
    md_sha1 = hashlib.sha1(content.encode("utf-8")).hexdigest()

    with deps["db_connect_fn"]() as conn:
        conn.execute(
            """
            INSERT INTO memory_documents(memory_id, task_hash, md_path, md_sha1, features_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(memory_id) DO UPDATE SET
                task_hash=excluded.task_hash,
                md_path=excluded.md_path,
                md_sha1=excluded.md_sha1,
                features_json=excluded.features_json,
                updated_at=excluded.updated_at
            """,
            (
                memory_id,
                task_hash,
                str(md_rel),
                str(md_sha1),
                deps["json_dumps_fn"](features),
                now,
                now,
            ),
        )
        conn.execute(
            "UPDATE memory_cases SET md_path = ?, features_json = ?, updated_at = ? WHERE memory_id = ?",
            (str(md_rel), deps["json_dumps_fn"](features), now, memory_id),
        )
        conn.commit()
    return str(md_rel)


def upsert_memory_case(
    *,
    task_text: str,
    task_type: str,
    tags: List[str],
    strategy_text: str,
    config_snippet: str,
    pitfalls_text: str,
    failure_reason: str,
    fix_action: str,
    lesson: str,
    source_rollout_id: str,
    reward: float,
    tool_call_count: int,
    memory_kind: str = "success",
    task_hash_salt: str = "",
    deps: Dict[str, Any],
) -> None:
    now = time.time()
    normalize_text = deps["normalize_text_fn"]
    hash_input = f"{normalize_text(task_text)}|{normalize_text(memory_kind)}|{normalize_text(task_hash_salt)}"
    task_hash = hashlib.sha1(hash_input.encode("utf-8")).hexdigest()
    memory_id = f"mem-{task_hash[:16]}"
    _sync_dynamic_method_candidates(
        task_text=task_text,
        strategy_text=strategy_text,
        config_snippet=config_snippet,
        source_rollout_id=source_rollout_id,
        deps=deps,
    )
    dynamic_methods = _list_validated_dynamic_methods(deps=deps)
    features = matching.build_memory_features(
        task_text,
        strategy_text,
        config_snippet,
        task_type=task_type,
        dynamic_methods=dynamic_methods,
    )

    with deps["db_connect_fn"]() as conn:
        row = conn.execute(
            "SELECT reward FROM memory_cases WHERE task_hash = ?",
            (task_hash,),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO memory_cases(
                    memory_id, task_hash, task_text, task_type, tags_json, strategy_text,
                    config_snippet, pitfalls_text, failure_reason, fix_action, lesson,
                    source_rollout_id, reward, tool_call_count, features_json,
                    success, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                """,
                (
                    memory_id,
                    task_hash,
                    task_text,
                    task_type,
                    deps["json_dumps_fn"](tags),
                    strategy_text,
                    config_snippet,
                    pitfalls_text,
                    failure_reason,
                    fix_action,
                    lesson,
                    source_rollout_id,
                    float(reward),
                    int(tool_call_count),
                    deps["json_dumps_fn"](features),
                    now,
                    now,
                ),
            )
            should_update = True
        else:
            old_reward = float(row["reward"] or 0.0)
            should_update = float(reward) >= old_reward
            if should_update:
                conn.execute(
                    """
                    UPDATE memory_cases
                    SET task_text=?, task_type=?, tags_json=?, strategy_text=?, config_snippet=?,
                        pitfalls_text=?, failure_reason=?, fix_action=?, lesson=?, source_rollout_id=?,
                        reward=?, tool_call_count=?, features_json=?, updated_at=?
                    WHERE task_hash=?
                    """,
                    (
                        task_text,
                        task_type,
                        deps["json_dumps_fn"](tags),
                        strategy_text,
                        config_snippet,
                        pitfalls_text,
                        failure_reason,
                        fix_action,
                        lesson,
                        source_rollout_id,
                        float(reward),
                        int(tool_call_count),
                        deps["json_dumps_fn"](features),
                        now,
                        task_hash,
                    ),
                )
        conn.commit()

    if should_update:
        write_memory_markdown_and_index(
            memory_id=memory_id,
            task_hash=task_hash,
            task_text=task_text,
            task_type=task_type,
            tags=tags,
            reward=float(reward),
            tool_call_count=int(tool_call_count),
            strategy_text=strategy_text,
            config_snippet=config_snippet,
            pitfalls_text=pitfalls_text,
            failure_reason=failure_reason,
            fix_action=fix_action,
            lesson=lesson,
            source_rollout_id=source_rollout_id,
            features=features,
            deps=deps,
        )


def backfill_memory_documents(*, limit: int = 1000, deps: Dict[str, Any]) -> Dict[str, Any]:
    rows_count = 0
    written = 0
    normalize_text = deps["normalize_text_fn"]
    with deps["db_connect_fn"]() as conn:
        rows = conn.execute(
            """
            SELECT memory_id, task_hash, task_text, task_type, tags_json, strategy_text, config_snippet,
                   pitfalls_text, failure_reason, fix_action, lesson, source_rollout_id,
                   reward, tool_call_count, features_json, md_path
            FROM memory_cases
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (max(1, min(int(limit), 10000)),),
        ).fetchall()
    for row in rows:
        rows_count += 1
        memory_id = str(row["memory_id"] or "").strip()
        if not memory_id:
            continue
        task_hash = str(row["task_hash"] or "").strip()
        if not task_hash:
            task_hash = hashlib.sha1(normalize_text(str(row["task_text"] or "")).encode("utf-8")).hexdigest()
        features = deps["json_loads_or_default_fn"](row["features_json"], {})
        if not isinstance(features, dict) or not features:
            features = matching.build_memory_features(
                str(row["task_text"] or ""),
                str(row["strategy_text"] or ""),
                str(row["config_snippet"] or ""),
                dynamic_methods=_list_validated_dynamic_methods(deps=deps),
            )
        md_current = str(row["md_path"] or "").strip()
        md_abs = deps["memory_docs_dir"] / f"{memory_id}.md"
        if md_current and md_abs.exists() and features:
            continue
        tags = deps["json_loads_or_default_fn"](row["tags_json"], [])
        if not isinstance(tags, list):
            tags = []
        write_memory_markdown_and_index(
            memory_id=memory_id,
            task_hash=task_hash,
            task_text=str(row["task_text"] or ""),
            task_type=str(row["task_type"] or ""),
            tags=[str(t) for t in tags],
            reward=float(row["reward"] or 0.0),
            tool_call_count=int(row["tool_call_count"] or 0),
            strategy_text=str(row["strategy_text"] or ""),
            config_snippet=str(row["config_snippet"] or ""),
            pitfalls_text=str(row["pitfalls_text"] or ""),
            failure_reason=str(row["failure_reason"] or ""),
            fix_action=str(row["fix_action"] or ""),
            lesson=str(row["lesson"] or ""),
            source_rollout_id=str(row["source_rollout_id"] or ""),
            features=features,
            deps=deps,
        )
        written += 1
    return {"scanned": rows_count, "written": written}
