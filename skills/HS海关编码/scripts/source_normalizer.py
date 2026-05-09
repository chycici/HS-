#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from common import dump_json, load_json, normalize_hs_code, now_iso


FIELD_MAP = {
    "税号": "hs_code_cn",
    "商品编号": "hs_code_cn",
    "hs_code": "hs_code_cn",
    "item_code": "hs_code_cn",
    "商品名称": "product_name_cn",
    "监管条件": "supervision_code",
    "退税率": "rebate_rate",
    "rebate": "rebate_rate",
    "supervision": "supervision_code",
}


def normalize_record(record: dict) -> dict:
    normalized = {}
    for key, value in record.items():
        normalized[FIELD_MAP.get(key, key)] = value
    normalized.setdefault("source_type", "synced")
    normalized.setdefault("source_reference", "unknown")
    normalized.setdefault("fetched_at", now_iso())
    normalized.setdefault("confidence", 0.7)
    # 标准化 HS 编码格式（去掉小数点，补零至 10 位）
    if normalized.get("hs_code_cn"):
        normalized["hs_code_cn"] = normalize_hs_code(normalized["hs_code_cn"])
    return normalized


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize imported customs records.")
    parser.add_argument("--input", required=True, help="Input JSON file")
    parser.add_argument("--output", required=True, help="Output JSON file")
    args = parser.parse_args()

    payload = load_json(Path(args.input), [])
    if not isinstance(payload, list):
        print("input must be a JSON array", file=sys.stderr)
        return 1

    dump_json(Path(args.output), [normalize_record(item) for item in payload])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
