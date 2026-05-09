#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

from common import dump_json


def parse_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse CSV/JSON customs source into JSON array.")
    parser.add_argument("--input", required=True, help="Source file path")
    parser.add_argument("--output", required=True, help="Parsed JSON output path")
    args = parser.parse_args()

    source = Path(args.input)
    suffix = source.suffix.lower()
    if suffix == ".csv":
      records = parse_csv(source)
    elif suffix == ".json":
      import json
      with source.open("r", encoding="utf-8") as fh:
          records = json.load(fh)
    else:
        print(f"unsupported source format: {suffix}", file=sys.stderr)
        return 1

    if not isinstance(records, list):
        print("parsed records must be a JSON array", file=sys.stderr)
        return 1

    dump_json(Path(args.output), records)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
