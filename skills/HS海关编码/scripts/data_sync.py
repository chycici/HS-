#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from common import dump_json, knowledge_root, load_json, normalize_hs_code, now_iso


SYNC_TARGETS = {
    "hs": knowledge_root() / "synced_hs_rules" / "records.json",
    "rebate": knowledge_root() / "synced_rebate_rates" / "records.json",
    "supervision": knowledge_root() / "synced_supervision_conditions" / "records.json",
    "mapping": knowledge_root() / "synced_cn_id_mapping" / "records.json",
}


def upsert_records(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """以 hs_code_cn 为主键做增量合并，保留已有记录，只更新/新增传入条目。

    原来的 shutil.copyfile 全量覆盖会丢失之前所有已同步的数据；
    改为 upsert 后，每次同步只影响本次传入的编码行，其余保持不变。
    无 hs_code_cn 的记录用自增 id 追加，不参与 upsert。
    """
    index: dict[str, dict] = {}
    orphans: list[dict] = []

    for record in existing:
        code = normalize_hs_code(record.get("hs_code_cn", ""))
        if code:
            index[code] = record
        else:
            orphans.append(record)

    added = 0
    updated = 0
    for record in incoming:
        code = normalize_hs_code(record.get("hs_code_cn", ""))
        record_norm = dict(record)
        if code:
            record_norm["hs_code_cn"] = code
        if code and code in index:
            index[code] = record_norm
            updated += 1
        elif code:
            index[code] = record_norm
            added += 1
        else:
            orphans.append(record_norm)
            added += 1

    merged = sorted(index.values(), key=lambda r: r.get("hs_code_cn", "")) + orphans
    return merged, added, updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Import and normalize a customs public source into synced knowledge.")
    parser.add_argument("--source", required=True, help="Input CSV or JSON source")
    parser.add_argument("--target", required=True, choices=sorted(SYNC_TARGETS.keys()), help="Synced target bucket")
    args = parser.parse_args()

    target_path = SYNC_TARGETS[args.target]

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        parsed = tmpdir / "parsed.json"
        normalized = tmpdir / "normalized.json"
        subprocess.run(
            ["python3", str(Path(__file__).with_name("import_parser.py")), "--input", args.source, "--output", str(parsed)],
            check=True,
        )
        subprocess.run(
            ["python3", str(Path(__file__).with_name("source_normalizer.py")), "--input", str(parsed), "--output", str(normalized)],
            check=True,
        )
        incoming = load_json(normalized, [])

    existing = load_json(target_path, [])
    merged, added, updated = upsert_records(existing, incoming)
    dump_json(target_path, merged)

    dump_json(
        knowledge_root() / "sync_report.json",
        {
            "status": "completed",
            "target": args.target,
            "source": args.source,
            "synced_at": now_iso(),
            "output": str(target_path),
            "records_total": len(merged),
            "records_added": added,
            "records_updated": updated,
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
