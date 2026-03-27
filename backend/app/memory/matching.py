from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Set, Tuple

_METHOD_KEYWORDS = [
    "CHAO-SEA",
    "UNIQUAC",
    "NRTL",
    "PENG-ROB",
    "RK-SOAVE",
    "IAPWS-95",
]

_EQUIPMENT_KEYWORDS = {
    "mixer": ["mixer", "\u6df7\u5408\u5668"],
    "sep": ["sep", "separation", "separator", "\u5206\u79bb\u5668"],
    "sep2": ["sep2", "\u5206\u79bb\u56682"],
    "distl": ["distl", "\u7cbe\u998f\u5854", "\u84b8\u998f\u5854", "distillation column"],
    "radfrac": ["radfrac", "column", "tower", "\u7cbe\u998f\u5854", "\u84b8\u998f\u5854"],
    "flash": ["flash", "\u95ea\u84b8"],
    "flash3": ["flash3", "\u4e09\u76f8\u95ea\u84b8"],
    "heatx": ["heatx", "heater", "cooler", "\u6362\u70ed\u5668", "\u52a0\u70ed\u5668", "\u51b7\u5374\u5668"],
    "valve": ["valve", "\u9600", "\u9600\u95e8"],
    "pump": ["pump", "\u6cf5"],
    "compr": ["compr", "compressor", "\u538b\u7f29\u673a"],
    "mcompr": ["mcompr", "multi-stage compressor", "\u591a\u7ea7\u538b\u7f29\u673a"],
    "rstoic": ["rstoic", "stoic reactor", "\u53cd\u5e94\u5668", "\u5316\u5b66\u53cd\u5e94\u5668"],
    "rcstr": ["rcstr", "cstr", "\u53cd\u5e94\u5668", "\u5168\u6df7\u91dc"],
    "rplug": ["rplug", "pfr", "\u53cd\u5e94\u5668", "\u5e73\u63a8\u6d41"],
    "fsplit": ["fsplit", "\u5206\u6d41\u5668"],
    "extract": ["extract", "\u8403\u53d6\u5854"],
    "decanter": ["decanter", "\u503e\u6790\u5668"],
    "dupl": ["dupl", "\u5854\u5668"],
    "dstwu": ["dstwu", "\u7cbe\u998f\u5854\u8bbe\u8ba1"],
}

_FLOW_VERBS = [
    "\u6df7\u5408",
    "\u5206\u79bb",
    "\u8fdb\u5165",
    "\u4ea7\u51fa",
    "\u751f\u6210",
    "\u5854\u9876",
    "\u5854\u5e95",
    "\u56de\u6d41",
    "\u5faa\u73af",
    "\u51b7\u51dd",
    "\u95ea\u84b8",
    "\u6362\u70ed",
    "\u538b\u7f29",
    "\u5347\u538b",
    "\u964d\u538b",
]

_OP_KEYWORDS = [
    "\u8ba1\u7b97",
    "\u6c42",
    "\u5206\u79bb",
    "\u6df7\u5408",
    "\u95ea\u84b8",
    "\u7cbe\u998f",
    "\u6362\u70ed",
    "\u538b\u7f29",
    "\u53cd\u5e94",
    "\u6e29\u5ea6",
    "\u538b\u529b",
    "\u6d41\u91cf",
    "\u7ec4\u6210",
    "\u6469\u5c14\u5206\u6570",
    "\u7eaf\u5ea6",
    "\u67e5\u770b",
    "\u67e5\u8be2",
    "\u4fee\u6539",
    "\u8bbe\u7f6e",
    "\u8fd0\u884c",
    "\u6a21\u62df",
    "calculate",
    "query",
    "modify",
    "set",
]

_COMPONENT_ALIASES = {
    "\u4e19\u70f7": "C3",
    "\u6b63\u4e01\u70f7": "NC4",
    "\u6b63\u620a\u70f7": "NC5",
    "\u6b63\u5df1\u70f7": "NC6",
    "\u7532\u70f7": "CH4",
    "\u4e59\u70f7": "C2H6",
    "\u4e59\u70ef": "C2H4",
    "\u4e19\u70ef": "C3H6",
    "\u82ef": "BENZENE",
    "\u4e59\u82ef": "ETHYLBENZENE",
    "\u82ef\u4e59\u70ef": "STYRENE",
    "\u7532\u9187": "CH3OH",
    "\u4e59\u9187": "C2H5OH",
    "\u6c34": "H2O",
    "\u6c22\u6c14": "H2",
    "\u7532\u82ef": "C7H8",
    "\u73af\u5df1\u70f7": "C6H12",
}

_ACTION_PATTERNS = {
    "mix_streams": ["\u6df7\u5408", "mix", "mixer", "\u6df7\u5408\u5668"],
    "separate_streams": ["\u5206\u79bb", "separation", "separator", "sep"],
    "run_simulation": ["\u8fd0\u884c\u6a21\u62df", "\u91cd\u65b0\u8fd0\u884c", "run simulation", "simulate"],
    "query_results": ["\u67e5\u770b", "\u67e5\u8be2", "\u83b7\u53d6\u7ed3\u679c", "get_result", "query", "check", "view"],
    "modify_conditions": ["\u4fee\u6539", "\u8bbe\u7f6e", "\u8c03\u5230", "\u8c03\u6574", "modify", "set"],
    "calculate_product_conditions": ["\u8ba1\u7b97", "\u6c42", "\u6e29\u5ea6", "\u538b\u529b", "\u7ec4\u6210", "\u6d41\u91cf", "\u6469\u5c14\u5206\u6570", "calculate"],
}

_EXPECTED_OUTPUT_PATTERNS = {
    "product_temperature": ["\u4ea7\u54c1\u6e29\u5ea6", "\u51fa\u53e3\u6e29\u5ea6", "temperature"],
    "product_pressure": ["\u4ea7\u54c1\u538b\u529b", "\u51fa\u53e3\u538b\u529b", "pressure"],
    "component_flowrates": ["\u7ec4\u5206\u6d41\u91cf", "\u5404\u7ec4\u5206\u6d41\u91cf", "flowrate"],
    "component_composition": ["\u7ec4\u6210", "\u6469\u5c14\u5206\u6570", "\u7eaf\u5ea6", "composition"],
    "simulation_status": ["\u8fd0\u884c\u6a21\u62df", "simulate", "simulation result"],
}

_STREAM_OUTPUT_ALIASES = {
    "PRODUCT": ["PRODUCT", "\u4ea7\u54c1\u7269\u6d41", "\u4ea7\u54c1\u6d41\u80a1", "\u51fa\u53e3\u7269\u6d41", "\u51fa\u53e3\u6d41\u80a1"],
    "RECYCLE": ["RECYCLE", "\u5faa\u73af\u7269\u6d41", "\u56de\u6d41\u7269\u6d41", "\u5faa\u73af\u6d41\u80a1"],
    "ORG": ["ORG", "\u6709\u673a\u76f8"],
    "AQ": ["AQ", "\u6c34\u76f8"],
}

_SPECIAL_NON_COMPONENT_TOKENS = {"FEED", "PRODUCT", "RECYCLE", "CONFIG", "JSON", "PATH"}
_NON_COMPONENT_NORMALIZED_VALUES = {"MIXER", "SEP", "SEP2", "FLASH", "FLASH3", "HEATX", "PUMP", "COMPR", "MCOMPR", "RADFRAC", "DISTL", "DSTWU", "VALVE", "RSTOIC", "RCSTR", "RPLUG"}
_EQUIPMENT_ID_RE = re.compile(r"\b[A-Z][A-Z0-9]{1,15}-\d{1,4}\b")
_COMPONENT_FORMULA_PATTERNS = [
    re.compile(r"(?:^|[、,，和及\s])([一-鿿]{1,16})\s*[（(]([A-Za-z][A-Za-z0-9\-]{1,15})[)）]"),
]

_METHOD_CONTEXT_PATTERNS = [
    re.compile(r"(?:\u7269\u6027\u65b9\u6cd5|\u70ed\u529b\u5b66\u65b9\u6cd5|\u7269\u6027\u5305|property method|thermo method)\s*(?:\u91c7\u7528|\u4e3a|\u7528|=|:|\uff1a)?\s*([A-Za-z][A-Za-z0-9\-_/ ]{1,40})", re.IGNORECASE),
    re.compile(r"(?:\u91c7\u7528|\u4f7f\u7528|\u7528)\s*([A-Za-z][A-Za-z0-9\-_/ ]{1,30})\s*(?:\u7269\u6027\u65b9\u6cd5|\u70ed\u529b\u5b66\u65b9\u6cd5|\u7269\u6027\u5305)", re.IGNORECASE),
]


def _contains_any(text: str, patterns: List[str]) -> bool:
    lowered = text.lower()
    return any(str(p).lower() in lowered for p in patterns if p)


def _sorted_unique(items: List[str]) -> List[str]:
    return sorted({str(item).strip() for item in items if str(item).strip()})


def extract_methods(text: str, dynamic_methods: Optional[List[str]] = None) -> List[str]:
    working_text = str(text or "").upper()
    method_keywords = sorted(
        set(_METHOD_KEYWORDS) | {str(m).strip().upper() for m in (dynamic_methods or []) if str(m).strip()},
        key=lambda item: (-len(item), item),
    )
    hits = set()
    for method in method_keywords:
        pattern = re.compile(rf"(?<![A-Z0-9]){re.escape(method.upper())}(?![A-Z0-9])")
        matched = False
        while True:
            m = pattern.search(working_text)
            if not m:
                break
            matched = True
            start, end = m.span()
            working_text = working_text[:start] + (" " * max(1, end - start)) + working_text[end:]
        if matched:
            hits.add(method)
    return sorted(hits)


def normalize_method_name(raw: str) -> str:
    text = re.sub(r"\s+", "-", str(raw or "").strip().upper())
    text = text.replace("_", "-").replace("/", "-")
    text = re.sub(r"[^A-Z0-9\-]", "", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text


def extract_method_candidates(text: str, dynamic_methods: Optional[List[str]] = None) -> List[Dict[str, Any]]:
    raw = str(text or "")
    known_methods = set(_METHOD_KEYWORDS) | {str(m).strip().upper() for m in (dynamic_methods or []) if str(m).strip()}
    candidates: Dict[str, Dict[str, Any]] = {}
    for pattern in _METHOD_CONTEXT_PATTERNS:
        for match in pattern.finditer(raw):
            method_raw = str(match.group(1) or "").strip().strip("\uff0c,\u3002\uff1b;:\uff1a")
            normalized = normalize_method_name(method_raw)
            if not normalized or normalized in known_methods:
                continue
            existing = candidates.get(method_raw)
            payload = {
                "raw_text": method_raw,
                "normalized_value": normalized,
                "confidence": 0.96,
                "source": "rule_context",
            }
            if existing is None or float(payload["confidence"]) > float(existing.get("confidence", 0.0) or 0.0):
                candidates[method_raw] = payload
    return list(candidates.values())


def extract_equipment(text: str) -> List[str]:
    raw = text or ""
    hits: List[str] = []
    for eq_key, patterns in _EQUIPMENT_KEYWORDS.items():
        if _contains_any(raw, patterns):
            hits.append(eq_key)
    return sorted(set(hits))


def extract_equipment_ids(text: str) -> List[str]:
    raw = text or ""
    hits: List[str] = []
    for token in _EQUIPMENT_ID_RE.findall(raw.upper()):
        if token.startswith("FEED"):
            continue
        if token in {"PRODUCT-1", "RECYCLE-1"}:
            continue
        hits.append(token)
    return _sorted_unique(hits)


def extract_stream_tokens(text: str) -> List[str]:
    raw = text or ""
    tokens = set()
    for m in re.findall(r"\bFEED\d+\b", raw, flags=re.IGNORECASE):
        tokens.add(m.upper())
    for m in re.findall(r"\b(PRODUCT|RECYCLE|ORG|AQ)\b", raw, flags=re.IGNORECASE):
        tokens.add(m.upper())
    for canon, aliases in _STREAM_OUTPUT_ALIASES.items():
        if any(alias.lower() in raw.lower() for alias in aliases):
            tokens.add(canon)
    return sorted(tokens)


def extract_flow_verbs(text: str) -> List[str]:
    raw = text or ""
    return sorted({v for v in _FLOW_VERBS if v in raw})


def extract_ops(text: str) -> List[str]:
    raw = text or ""
    return sorted({v for v in _OP_KEYWORDS if v in raw})


def clean_component_candidate(raw: str) -> str:
    value = str(raw or "").strip()
    value = re.sub(r"^(?:\u7ec4\u5206\u4e3a|\u8fdb\u6599\u4e2d|\u539f\u6599\u4e2d|\u542b\u6709|\u5305\u542b|\u5c06)+", "", value)
    value = value.strip(" \u3001,\uff0c\u548c\u53ca")
    return value


def normalize_component_name(raw: str, formula: str = "") -> str:
    if formula:
        return str(formula or "").strip().upper()
    text = str(raw or "").strip()
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9\-]{0,15}", text):
        return text.upper()
    return text


def extract_component_candidates(
    text: str,
    dynamic_component_aliases: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    raw = str(text or "")
    known_aliases = dict(_COMPONENT_ALIASES)
    for key, value in (dynamic_component_aliases or {}).items():
        k = str(key or "").strip()
        v = str(value or "").strip()
        if k and v:
            known_aliases[k] = v
    known_values = {str(v).strip().upper() for v in known_aliases.values() if str(v).strip()}
    candidates: Dict[str, Dict[str, Any]] = {}
    for pattern in _COMPONENT_FORMULA_PATTERNS:
        for match in pattern.finditer(raw):
            component_raw = clean_component_candidate(str(match.group(1) or "").strip())
            formula = str(match.group(2) or "").strip().upper()
            normalized = normalize_component_name(component_raw, formula)
            if not component_raw or not normalized:
                continue
            lowered_raw = component_raw.lower()
            if any(term in lowered_raw for term in ["mixer", "separator", "reactor", "pump", "compressor", "column", "tower"]):
                continue
            if any(term in component_raw for term in ["???", "???", "???", "???", "?", "?"]):
                continue
            if normalized in _NON_COMPONENT_NORMALIZED_VALUES:
                continue
            # Reject stream-role phrases such as product stream (PROD-1) / feed stream (FEED1)
            if any(term in component_raw for term in ["物流", "流股", "产品", "进料", "顶部", "底部", "出口", "入口"]):
                continue
            if normalized in _SPECIAL_NON_COMPONENT_TOKENS:
                continue
            if normalized.startswith("FEED") or normalized.startswith("PROD") or normalized.startswith("PRODUCT") or normalized.startswith("RECYCLE"):
                continue
            if re.fullmatch(r"[A-Z][A-Z0-9]{1,15}-\d{1,4}", normalized):
                continue
            if component_raw in known_aliases or normalized in known_values:
                continue
            existing = candidates.get(component_raw)
            payload = {
                "raw_text": component_raw,
                "normalized_value": normalized,
                "confidence": 0.99,
                "source": "rule_parenthetical",
            }
            if existing is None or float(payload["confidence"]) > float(existing.get("confidence", 0.0) or 0.0):
                candidates[component_raw] = payload
    return list(candidates.values())


def extract_components(text: str, dynamic_component_aliases: Optional[Dict[str, str]] = None) -> List[str]:
    raw = text or ""
    hits: List[str] = []
    equipment_ids = set(extract_equipment_ids(raw))
    component_aliases = dict(_COMPONENT_ALIASES)
    for key, value in (dynamic_component_aliases or {}).items():
        k = str(key or "").strip()
        v = str(value or "").strip()
        if k and v:
            component_aliases[k] = v
    normalized_values = {str(v).strip().upper() for v in component_aliases.values() if str(v).strip()}
    for name, norm in component_aliases.items():
        if name in raw or norm.lower() in raw.lower():
            hits.append(norm)
    for token in re.findall(r"\b[A-Z][A-Z0-9\-]{1,12}\b", raw.upper()):
        if token in _SPECIAL_NON_COMPONENT_TOKENS:
            continue
        if token.startswith("FEED"):
            continue
        if token in equipment_ids:
            continue
        if any(ch.isdigit() for ch in token) or token in normalized_values:
            hits.append(token)
    return sorted(set(hits))


def extract_actions(text: str) -> List[str]:
    raw = text or ""
    hits: List[str] = []
    for action, patterns in _ACTION_PATTERNS.items():
        if _contains_any(raw, patterns):
            hits.append(action)
    return _sorted_unique(hits)


def extract_expected_outputs(text: str) -> List[str]:
    raw = text or ""
    hits: List[str] = []
    for output_name, patterns in _EXPECTED_OUTPUT_PATTERNS.items():
        if _contains_any(raw, patterns):
            hits.append(output_name)
    return _sorted_unique(hits)


def extract_match_fields(
    texts: List[str],
    *,
    dynamic_methods: Optional[List[str]] = None,
    dynamic_component_aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, List[str]]:
    merged = "\n".join([t for t in texts if t])
    return {
        "methods": extract_methods(merged, dynamic_methods=dynamic_methods),
        "equipment": extract_equipment(merged),
        "equipment_ids": extract_equipment_ids(merged),
        "streams": extract_stream_tokens(merged),
        "ops": extract_ops(merged),
        "flow": extract_flow_verbs(merged),
        "components": extract_components(merged, dynamic_component_aliases=dynamic_component_aliases),
    }


def match_required_fields(query_fields: Dict[str, List[str]], mem_fields: Dict[str, List[str]]) -> Tuple[bool, Dict[str, Any]]:
    details: Dict[str, Any] = {
        "mode": "layered",
        "checks": {},
        "missing": [],
        "must_passed": True,
        "anchor_passed": True,
        "ranking_score": 0.0,
    }

    must_keys = ["equipment_ids"]
    anchor_keys = ["equipment", "streams"]
    should_keys = ["ops", "components", "flow", "methods"]

    def _ratio(q_vals: Set[str], m_vals: Set[str]) -> Tuple[float, List[str], List[str]]:
        if not q_vals:
            return 0.0, [], []
        hits = sorted(list(q_vals & m_vals))
        missing = sorted(list(q_vals - m_vals))
        return (len(hits) / max(1, len(q_vals))), hits, missing

    must_failures = 0
    for key in must_keys:
        q = set(query_fields.get(key, []))
        m = set(mem_fields.get(key, []))
        if not q:
            details["checks"][key] = {"tier": "must", "required": False, "ok": True, "hits": [], "missing": [], "ratio": 0.0}
            continue
        ratio, hits, missing = _ratio(q, m)
        passed = len(missing) == 0
        details["checks"][key] = {"tier": "must", "required": True, "ok": passed, "hits": hits, "missing": missing, "ratio": ratio}
        if not passed:
            must_failures += 1
            details["missing"].append({key: missing})
    details["must_passed"] = must_failures == 0

    anchor_required = False
    anchor_hits = 0
    anchor_score = 0.0
    for key in anchor_keys:
        q = set(query_fields.get(key, []))
        m = set(mem_fields.get(key, []))
        if not q:
            details["checks"][key] = {"tier": "anchor", "required": False, "ok": True, "hits": [], "missing": [], "ratio": 0.0}
            continue
        anchor_required = True
        ratio, hits, missing = _ratio(q, m)
        passed = ratio > 0.0
        if passed:
            anchor_hits += 1
        anchor_score += ratio
        details["checks"][key] = {"tier": "anchor", "required": True, "ok": passed, "hits": hits, "missing": missing, "ratio": ratio}
        if not passed:
            details["missing"].append({key: missing})
    details["anchor_passed"] = (anchor_hits >= 1) if anchor_required else True

    should_required = False
    should_ratios: List[float] = []
    should_hit_fields = 0
    for key in should_keys:
        q = set(query_fields.get(key, []))
        m = set(mem_fields.get(key, []))
        if not q:
            details["checks"][key] = {"tier": "should", "required": False, "ok": True, "hits": [], "missing": [], "ratio": 0.0}
            continue
        should_required = True
        ratio, hits, missing = _ratio(q, m)
        if ratio > 0.0:
            should_hit_fields += 1
        should_ratios.append(ratio)
        details["checks"][key] = {"tier": "should", "required": True, "ok": ratio >= 0.34, "hits": hits, "missing": missing, "ratio": ratio}

    avg_should_ratio = (sum(should_ratios) / len(should_ratios)) if should_ratios else 0.0
    details["should_score"] = round(avg_should_ratio, 4)
    details["anchor_score"] = round(anchor_score, 4)
    details["should_hit_fields"] = int(should_hit_fields)
    details["ranking_score"] = round(anchor_score * 1.2 + avg_should_ratio * 1.0 + should_hit_fields * 0.15, 4)

    ok = details["must_passed"]
    if ok and anchor_required:
        ok = details["anchor_passed"]
    if ok and (not anchor_required) and should_required:
        ok = avg_should_ratio >= 0.2 or should_hit_fields >= 1

    details["filter_ok"] = bool(ok)
    return ok, details


def extract_schema_hash_from_config(config_snippet: str) -> str:
    text = str(config_snippet or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()[:24]


def _infer_task_family(*, task_type: str, equipment_types: List[str], actions: List[str]) -> str:
    action_set = set(actions)
    equipment_set = set(equipment_types)
    if "mix_streams" in action_set or "mixer" in equipment_set:
        return "mixing_calculation"
    if "separate_streams" in action_set or equipment_set & {"sep", "sep2", "flash", "flash3", "extract", "decanter"}:
        return "separation_task"
    if equipment_set & {"distl", "radfrac", "dstwu"}:
        return "distillation_task"
    if equipment_set & {"heatx"}:
        return "heat_exchange_task"
    if equipment_set & {"pump", "compr", "mcompr", "valve"}:
        return "pressure_adjustment_task"
    if equipment_set & {"rstoic", "rcstr", "rplug"}:
        return "reaction_task"
    if task_type == "process":
        return "process_optimization"
    return "general_simulation"


def _build_query_expansion_terms(profile: Dict[str, Any]) -> List[str]:
    entities = profile.get("entities", {}) if isinstance(profile, dict) else {}
    terms: List[str] = []
    for equipment_type in entities.get("equipment_types", []):
        terms.extend(_EQUIPMENT_KEYWORDS.get(str(equipment_type), []))
    for output_name in profile.get("expected_outputs", []):
        terms.extend(_EXPECTED_OUTPUT_PATTERNS.get(str(output_name), []))
    for action_name in profile.get("actions", []):
        terms.extend(_ACTION_PATTERNS.get(str(action_name), []))
    for stream_name in entities.get("stream_outputs", []):
        terms.extend(_STREAM_OUTPUT_ALIASES.get(str(stream_name), []))
    terms.extend(entities.get("components", []))
    terms.extend(entities.get("thermo_methods", []))
    return _sorted_unique(terms)


def _build_task_title(text: str, actions: List[str], equipment_types: List[str]) -> str:
    raw = str(text or "").strip()
    if raw:
        line = re.split(r"[\r\n\u3002\uff1b;]", raw, maxsplit=1)[0].strip()
        if line:
            return line[:80]
    if actions or equipment_types:
        return " / ".join((actions + equipment_types)[:3])
    return "general_task"


def build_semantic_profile(
    texts: List[str],
    *,
    task_type: str = "",
    dynamic_methods: Optional[List[str]] = None,
    dynamic_component_aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    merged = "\n".join([str(t or "") for t in texts if str(t or "").strip()])
    match_fields = extract_match_fields(
        [merged],
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )
    actions = extract_actions(merged)
    expected_outputs = extract_expected_outputs(merged)
    control_variables = _sorted_unique([
        x for x in match_fields.get("ops", []) if x in {"\u6e29\u5ea6", "\u538b\u529b", "\u6d41\u91cf", "\u7ec4\u6210", "\u6469\u5c14\u5206\u6570", "\u7eaf\u5ea6"}
    ])
    stream_inputs = _sorted_unique([s for s in match_fields.get("streams", []) if s.startswith("FEED")])
    stream_outputs = _sorted_unique([s for s in match_fields.get("streams", []) if not s.startswith("FEED")])
    effective_task_type = str(task_type or "").strip().lower()
    if effective_task_type not in {"unit", "process"}:
        effective_task_type = "process" if any(eq in match_fields.get("equipment", []) for eq in ["distl", "radfrac", "dstwu"]) else "unit"
    profile = {
        "version": "v1",
        "task_title": _build_task_title(merged, actions, match_fields.get("equipment", [])),
        "task_type": effective_task_type,
        "task_family": _infer_task_family(
            task_type=effective_task_type,
            equipment_types=match_fields.get("equipment", []),
            actions=actions,
        ),
        "goal": merged[:300],
        "entities": {
            "equipment_types": match_fields.get("equipment", []),
            "equipment_ids": match_fields.get("equipment_ids", []),
            "stream_inputs": stream_inputs,
            "stream_outputs": stream_outputs,
            "components": match_fields.get("components", []),
            "thermo_methods": match_fields.get("methods", []),
        },
        "actions": actions,
        "control_variables": control_variables,
        "expected_outputs": expected_outputs,
        "constraints": _sorted_unique(match_fields.get("flow", []) + match_fields.get("methods", [])),
        "query_expansion_terms": [],
        "risk_tags": [],
        "summary_text": merged[:500],
    }
    profile["query_expansion_terms"] = _build_query_expansion_terms(profile)
    return profile


def _overlap_ratio(query_items: List[str], memory_items: List[str]) -> Tuple[float, List[str]]:
    q_set: Set[str] = {str(item).strip() for item in query_items if str(item).strip()}
    m_set: Set[str] = {str(item).strip() for item in memory_items if str(item).strip()}
    if not q_set:
        return 0.0, []
    hits = sorted(list(q_set & m_set))
    return (len(hits) / max(1, len(q_set))), hits


def score_semantic_similarity(query_profile: Dict[str, Any], memory_profile: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    q_entities = query_profile.get("entities", {}) if isinstance(query_profile, dict) else {}
    m_entities = memory_profile.get("entities", {}) if isinstance(memory_profile, dict) else {}
    score = 0.0
    details: Dict[str, Any] = {"hits": {}}

    q_family = str(query_profile.get("task_family", "")).strip()
    m_family = str(memory_profile.get("task_family", "")).strip()
    if q_family and q_family == m_family:
        score += 0.8
        details["hits"]["task_family"] = q_family

    q_task_type = str(query_profile.get("task_type", "")).strip()
    m_task_type = str(memory_profile.get("task_type", "")).strip()
    if q_task_type and q_task_type == m_task_type:
        score += 0.4
        details["hits"]["task_type"] = q_task_type

    weighted_fields = [
        ("equipment_ids", 1.4, q_entities.get("equipment_ids", []), m_entities.get("equipment_ids", [])),
        ("equipment_types", 1.1, q_entities.get("equipment_types", []), m_entities.get("equipment_types", [])),
        ("stream_inputs", 0.7, q_entities.get("stream_inputs", []), m_entities.get("stream_inputs", [])),
        ("stream_outputs", 0.6, q_entities.get("stream_outputs", []), m_entities.get("stream_outputs", [])),
        ("components", 0.9, q_entities.get("components", []), m_entities.get("components", [])),
        ("thermo_methods", 0.8, q_entities.get("thermo_methods", []), m_entities.get("thermo_methods", [])),
        ("actions", 1.0, query_profile.get("actions", []), memory_profile.get("actions", [])),
        ("control_variables", 0.7, query_profile.get("control_variables", []), memory_profile.get("control_variables", [])),
        ("expected_outputs", 0.7, query_profile.get("expected_outputs", []), memory_profile.get("expected_outputs", [])),
        ("query_expansion_terms", 0.4, query_profile.get("query_expansion_terms", []), memory_profile.get("query_expansion_terms", [])),
    ]
    for field_name, weight, q_items, m_items in weighted_fields:
        ratio, hits = _overlap_ratio(q_items, m_items)
        if ratio > 0:
            score += weight * ratio
            details["hits"][field_name] = hits

    details["score"] = round(score, 4)
    return round(score, 4), details


def build_memory_features(
    task_text: str,
    strategy_text: str,
    config_snippet: str,
    *,
    task_type: str = "",
    dynamic_methods: Optional[List[str]] = None,
    dynamic_component_aliases: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    fields = extract_match_fields(
        [task_text or "", strategy_text or "", config_snippet or ""],
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )
    semantic_profile = build_semantic_profile(
        [task_text or "", strategy_text or "", config_snippet or ""],
        task_type=task_type,
        dynamic_methods=dynamic_methods,
        dynamic_component_aliases=dynamic_component_aliases,
    )
    return {
        **fields,
        "match_fields": fields,
        "semantic_profile": semantic_profile,
        "schema_hash": extract_schema_hash_from_config(config_snippet),
    }
