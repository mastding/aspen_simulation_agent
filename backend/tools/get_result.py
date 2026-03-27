from typing import Dict, Any
import os
import json
from datetime import datetime

import requests
import urllib3
from dotenv import load_dotenv

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def _error(message: str, file_path: str, extra: Dict[str, Any] | None = None) -> str:
    payload: Dict[str, Any] = {
        "error": message,
        "file_path": file_path,
        "timestamp": datetime.now().isoformat(),
    }
    if extra:
        payload.update(extra)
    return json.dumps(payload, ensure_ascii=False, default=str)


async def get_result(file_path: str) -> str:
    """
    通过 Aspen 服务器远程读取结果文件。

    - Aspen 服务地址来自环境变量 ASPEN_SIMULATOR_URL
    - 调用 GET /get-aspen-result?file_path=...
    """
    try:
        base_url = os.getenv("ASPEN_SIMULATOR_URL", "").strip()
        if not base_url:
            return _error("未配置 ASPEN_SIMULATOR_URL", file_path)

        url = base_url.rstrip("/") + "/get-aspen-result"

        response = requests.get(
            url,
            params={"file_path": file_path},
            timeout=40,
            verify=False,
        )

        content_type = response.headers.get("Content-Type", "")

        if response.status_code != 200:
            body_preview = response.text[:1000] if response.text else ""
            return _error(
                f"远程读取结果失败，HTTP {response.status_code}",
                file_path,
                {
                    "url": url,
                    "response_content_type": content_type,
                    "response_body": body_preview,
                },
            )

        # 统一返回 JSON 字符串
        try:
            data = response.json()
            return json.dumps(data, ensure_ascii=False, default=str)
        except Exception:
            # 如果服务端未返回合法 JSON，按错误返回
            return _error(
                "远程服务返回了非 JSON 响应",
                file_path,
                {
                    "url": url,
                    "response_content_type": content_type,
                    "response_body": response.text[:1000],
                },
            )

    except requests.exceptions.RequestException as e:
        return _error(f"连接 Aspen 服务器失败: {str(e)}", file_path)
    except Exception as e:
        return _error(f"读取结果失败: {str(e)}", file_path)
