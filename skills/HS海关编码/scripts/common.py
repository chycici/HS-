#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# 缓存 TTL（天）：不同字段时效不同，超期视为过期需重新补查
# ---------------------------------------------------------------------------
CACHE_TTL_DAYS: dict[str, int] = {
    "product": 90,      # HS 编码归类变化较少
    "rebate": 30,       # 退税率政策调整频繁
    "supervision": 60,  # 监管条件中等频率变化
    "cn_id_mapping": 60,
}


def skill_root() -> Path:
    return Path(__file__).resolve().parent.parent


def knowledge_root() -> Path:
    return skill_root() / "knowledge"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def normalize_key(value: str) -> str:
    return "".join(value.lower().split())


def normalize_hs_code(code: str) -> str:
    """将 HS 编码统一为纯数字字符串（去掉小数点/空格，补零至 10 位）。

    合法输入示例：'84716072.00' → '8471607200'，'8507600090' → '8507600090'。
    无法识别的格式原样返回。
    """
    if not code:
        return code
    cleaned = re.sub(r"[\s.]", "", str(code))
    if re.fullmatch(r"\d{8,10}", cleaned):
        return cleaned.zfill(10)
    return code


def is_record_expired(record: dict, query_type: str) -> bool:
    """判断缓存记录是否已超过 TTL。manual_confirmed 记录永不过期。"""
    if record.get("source_type") == "manual_confirmed":
        return False
    fetched_at = record.get("fetched_at")
    if not fetched_at:
        return False
    try:
        dt = datetime.fromisoformat(fetched_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ttl_days = CACHE_TTL_DAYS.get(query_type, 60)
        return datetime.now(tz=timezone.utc) - dt > timedelta(days=ttl_days)
    except Exception:
        return False


def keys_match(query_key: str, item_key: str, min_coverage: float = 0.5) -> bool:
    """改进的模糊键匹配：要求较短串至少覆盖较长串长度的 min_coverage 比例。

    解决原始双向 `in` 匹配过于宽松的问题（如 "电池" 误匹配 "锂离子蓄电池组"）。
    精确匹配直接返回 True。
    """
    if not query_key or not item_key:
        return False
    if query_key == item_key:
        return True
    if item_key in query_key:
        coverage = len(item_key) / len(query_key)
        return coverage >= min_coverage
    if query_key in item_key:
        coverage = len(query_key) / len(item_key)
        return coverage >= min_coverage
    return False


def load_openclaw_config() -> dict[str, Any]:
    config_path = Path.home() / ".openclaw" / "openclaw.json"
    return load_json(config_path, {})


def get_provider_api_key(provider: str) -> str | None:
    env_candidates = {
        "deepseek": ["DEEPSEEK_API_KEY"],
        "google": ["GOOGLE_API_KEY", "GOOGLE_GENAI_API_KEY", "GEMINI_API_KEY"],
        "tavily": ["TAVILY_API_KEY"],
    }
    for name in env_candidates.get(provider, []):
        value = os.environ.get(name)
        if value:
            return value.strip()

    env_path = Path.home() / ".openclaw" / ".env"
    if env_path.exists():
        txt = env_path.read_text(encoding="utf-8", errors="ignore")
        for name in env_candidates.get(provider, []):
            match = re.search(rf"^\s*{re.escape(name)}\s*=\s*(.+?)\s*$", txt, re.M)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value:
                    return value

    config = load_openclaw_config()
    return (
        config.get("models", {})
        .get("providers", {})
        .get(provider, {})
        .get("apiKey")
    )


def http_get(url: str, headers: dict[str, str] | None = None, timeout: int = 30) -> str:
    req = urllib.request.Request(
        url,
        headers=headers
        or {
            "User-Agent": "Mozilla/5.0 (compatible; OpenClaw-HSLookup/1.0)",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_post_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers=headers
        or {
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    return json.loads(text)
