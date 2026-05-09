#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from common import dump_json, load_json


def merge_declaration_elements(base: dict, update: dict) -> dict:
    merged = dict(base)
    for key, value in (update or {}).items():
        if value not in (None, ""):
            merged[key] = value

    missing_fields = []
    for key in ["usage", "material", "brand", "model", "is_complete_set", "dangerous_goods_flag"]:
        if merged.get(key) in (None, "", "待补充"):
            if key not in missing_fields:
                missing_fields.append(key)
    merged["missing_fields"] = missing_fields
    return merged


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply intake response and rerender HS outputs.")
    parser.add_argument("--base-json", required=True, help="Base HS workflow result JSON")
    parser.add_argument("--intake-json", required=True, help="Filled intake response JSON")
    parser.add_argument("--output-dir", required=True, help="Rendered output directory")
    args = parser.parse_args()

    base = load_json(Path(args.base_json), {})
    intake = load_json(Path(args.intake_json), {})
    base["query"] = intake.get("query") or base.get("query")
    base["declaration_elements"] = merge_declaration_elements(
        base.get("declaration_elements", {}),
        intake.get("declaration_elements_update", {}),
    )

    if not base["declaration_elements"].get("declaration_factor_hint"):
        base["declaration_elements"]["declaration_factor_hint"] = "请继续补齐剩余申报要素。"

    with tempfile.TemporaryDirectory() as tmp:
        merged_path = Path(tmp) / "merged.json"
        dump_json(merged_path, base)
        subprocess.run(
            [
                "python3",
                str(Path(__file__).with_name("render_outputs.py")),
                "--input",
                str(merged_path),
                "--output-dir",
                args.output_dir,
            ],
            check=True,
        )
        print(json.dumps(base, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
