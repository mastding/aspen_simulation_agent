from __future__ import annotations

import json
import ntpath
import os
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

import requests
import urllib3
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


@dataclass
class AspenDownloadResult:
    file_path: str
    file_name: str
    content: bytes
    content_type: str


class AspenDownloadError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    base = os.getenv("ASPEN_SIMULATOR_URL", "").strip()
    if not base:
        raise AspenDownloadError("ASPEN_SIMULATOR_URL is not configured", status_code=500)
    return base.rstrip("/")


def _safe_name(file_path: str) -> str:
    name = ntpath.basename(str(file_path))
    return name or "download.bin"


def _extract_error_detail(resp: requests.Response) -> str:
    content_type = str(resp.headers.get("Content-Type", "")).lower()
    text = (resp.text or "").strip()
    if "application/json" in content_type:
        try:
            payload = resp.json()
            if isinstance(payload, dict):
                for key in ("error", "message", "detail"):
                    value = payload.get(key)
                    if value:
                        return str(value)
        except Exception:
            pass
    return text[:500]


def download_aspen_file(file_path: str, timeout: int = 90) -> AspenDownloadResult:
    """Download a single file from Aspen remote server."""
    if not file_path or not str(file_path).strip():
        raise AspenDownloadError("file_path is required", status_code=400)

    url = _base_url() + "/download"

    try:
        resp = requests.get(
            url,
            params={"file_path": file_path},
            timeout=timeout,
            verify=False,
        )
    except requests.exceptions.RequestException as exc:
        raise AspenDownloadError(f"Failed to connect Aspen download endpoint: {exc}", status_code=502) from exc

    if resp.status_code != 200:
        detail = _extract_error_detail(resp)
        raise AspenDownloadError(
            f"Aspen download failed HTTP {resp.status_code}: {detail}",
            status_code=resp.status_code,
        )

    content_type = resp.headers.get("Content-Type", "application/octet-stream")
    content = resp.content or b""

    # Guardrail: do not return empty file as a successful download.
    if len(content) == 0:
        raise AspenDownloadError(
            f"Aspen download returned empty content for: {file_path}",
            status_code=502,
        )

    # Some backends return JSON error with HTTP 200; detect and fail fast.
    if "application/json" in str(content_type).lower():
        try:
            payload = json.loads(content.decode("utf-8", errors="ignore"))
            if isinstance(payload, dict) and any(payload.get(k) for k in ("error", "detail", "message")):
                detail = str(payload.get("error") or payload.get("detail") or payload.get("message"))
                raise AspenDownloadError(f"Aspen download error payload: {detail}", status_code=502)
        except AspenDownloadError:
            raise
        except Exception:
            # JSON file itself is valid and should still be downloadable.
            pass

    return AspenDownloadResult(
        file_path=file_path,
        file_name=_safe_name(file_path),
        content=content,
        content_type=content_type,
    )


def download_aspen_files(file_paths: Iterable[str], timeout: int = 90) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for fp in file_paths:
        item = {"file_path": fp, "success": False}
        try:
            ret = download_aspen_file(fp, timeout=timeout)
            item.update(
                {
                    "success": True,
                    "file_name": ret.file_name,
                    "content_type": ret.content_type,
                    "size": len(ret.content),
                }
            )
        except Exception as exc:
            item["error"] = str(exc)
        results.append(item)
    return results
