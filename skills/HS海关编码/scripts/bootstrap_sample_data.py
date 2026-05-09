#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

from common import dump_json, knowledge_root, load_json


def ensure_records(target_dir: Path) -> None:
    records = target_dir / "records.json"
    sample = target_dir / "sample.json"
    if not records.exists() and sample.exists():
        dump_json(records, load_json(sample, []))


def main() -> int:
    ensure_records(knowledge_root() / "synced_hs_rules")
    ensure_records(knowledge_root() / "synced_rebate_rates")
    ensure_records(knowledge_root() / "synced_supervision_conditions")
    ensure_records(knowledge_root() / "synced_cn_id_mapping")
    cache = knowledge_root() / "cache_store" / "records.json"
    if not cache.exists():
        dump_json(cache, [])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
