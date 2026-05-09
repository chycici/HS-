#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import dump_json, knowledge_root, load_json, normalize_hs_code, normalize_key, now_iso


def merge_records(existing: list[dict], incoming: list[dict]) -> list[dict]:
    index = {}
    for record in existing:
        key = (normalize_key(record.get("query_key", "")), record.get("query_type", ""))
        index[key] = record

    for record in incoming:
        if record.get("source_type") == "manual_confirmed":
            continue
        record.setdefault("fetched_at", now_iso())
        # 写入缓存前统一 HS 编码格式
        if record.get("hs_code_cn"):
            record["hs_code_cn"] = normalize_hs_code(record["hs_code_cn"])
        key = (normalize_key(record.get("query_key", "")), record.get("query_type", ""))
        current = index.get(key)
        if current and current.get("source_type") == "manual_confirmed":
            continue
        index[key] = record

    return sorted(index.values(), key=lambda item: (item.get("query_type", ""), item.get("query_key", "")))


def main() -> int:
    parser = argparse.ArgumentParser(description="Write live lookup results into cache_store.")
    parser.add_argument("--input", required=True, help="Input JSON array path")
    parser.add_argument(
        "--cache-file",
        default=str(knowledge_root() / "cache_store" / "records.json"),
        help="Cache JSON file path",
    )
    args = parser.parse_args()

    incoming = load_json(Path(args.input), [])
    existing = load_json(Path(args.cache_file), [])
    merged = merge_records(existing, incoming)
    dump_json(Path(args.cache_file), merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
