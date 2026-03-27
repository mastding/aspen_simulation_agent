from typing import List, Optional, Union
import json
import logging
import os
import sys

import requests
import urllib3
from dotenv import load_dotenv


load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("app.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def _normalize_block_types(block_types: Optional[List[str] | str]) -> List[str]:
    """Normalize model-generated args, including stringified JSON arrays."""
    if block_types is None:
        return []
    if isinstance(block_types, list):
        return [str(item).strip() for item in block_types if str(item).strip()]
    if isinstance(block_types, str):
        raw = block_types.strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except Exception:
            pass
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            if not inner:
                return []
            return [item.strip().strip('"').strip("'") for item in inner.split(",") if item.strip()]
        return [raw]
    return []


def _schema_request_types(block_types: List[str]) -> str:
    """Keep compatibility with the old local behavior: always include base schema."""
    ordered: List[str] = []
    for item in ["base", *block_types]:
        key = str(item).strip()
        if key and key not in ordered:
            ordered.append(key)
    return ",".join(ordered) if ordered else "base"


def _merge_remote_schema_payload(data: object) -> object:
    """Normalize remote /api/schema response back to the legacy merged schema shape."""
    if not isinstance(data, dict):
        return data

    schemas = data.get("schemas")
    if not isinstance(schemas, dict):
        return data

    base_schema = schemas.get("base")
    if not isinstance(base_schema, dict):
        return data

    merged = json.loads(json.dumps(base_schema, ensure_ascii=False))
    merged.setdefault("properties", {})

    for schema_type, schema_value in schemas.items():
        if schema_type == "base" or not isinstance(schema_value, dict):
            continue
        for key, value in schema_value.items():
            if key.startswith("blocks_"):
                merged["properties"][key] = value

    return merged


async def get_schema(block_types: Optional[Union[List[str], str]] = None) -> str:
    """
    通过 Aspen 服务器远程获取 JSON Schema。

    - 服务地址来自环境变量 ASPEN_SIMULATOR_URL
    - 调用 GET /api/schema?types=...&format=json
    - 为兼容旧逻辑，请求时总会附带 base
    """
    try:
        base_url = os.getenv("ASPEN_SIMULATOR_URL", "").strip()
        if not base_url:
            return json.dumps({"error": "未配置 ASPEN_SIMULATOR_URL"}, ensure_ascii=False)

        normalized_types = _normalize_block_types(block_types)
        query_types = _schema_request_types(normalized_types)
        url = base_url.rstrip("/") + "/api/schema"
        params = {
            "types": query_types,
            "format": "json",
        }

        logger.info(
            "远程获取Schema: url=%s types=%s raw=%s",
            url,
            query_types,
            block_types,
        )

        response = requests.get(
            url,
            params=params,
            timeout=60,
            verify=False,
        )

        if response.status_code != 200:
            body_preview = (response.text or "")[:1000]
            return json.dumps(
                {
                    "error": f"远程获取Schema失败，HTTP {response.status_code}",
                    "url": url,
                    "params": params,
                    "response_body": body_preview,
                },
                ensure_ascii=False,
            )

        try:
            data = response.json()
        except Exception:
            return json.dumps(
                {
                    "error": "远程Schema接口返回了非 JSON 响应",
                    "url": url,
                    "params": params,
                    "response_body": (response.text or "")[:1000],
                },
                ensure_ascii=False,
            )

        normalized = _merge_remote_schema_payload(data)
        return json.dumps(normalized, ensure_ascii=False)
    except requests.exceptions.RequestException as exc:
        logger.error("连接远程Schema服务失败: %s", exc)
        return json.dumps({"error": f"连接远程Schema服务失败: {str(exc)}"}, ensure_ascii=False)
    except Exception as exc:
        logger.error("远程获取Schema失败: %s", exc)
        return json.dumps({"error": f"远程获取Schema失败: {str(exc)}"}, ensure_ascii=False)
