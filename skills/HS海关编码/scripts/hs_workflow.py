#!/usr/bin/env python3
from __future__ import annotations

import argparse
import tempfile
from pathlib import Path

from common import (
    dump_json,
    is_record_expired,
    keys_match,
    knowledge_root,
    load_json,
    normalize_hs_code,
    normalize_key,
)


def load_records(path: Path) -> list[dict]:
    return load_json(path, [])


def source_label(item: dict | None) -> str:
    if not item:
        return "none"
    return item.get("source_type") or "unknown"


def find_match(records: list[dict], query: str, query_type: str) -> dict | None:
    """在记录列表中查找最佳匹配项。

    改进点：
    1. 跳过已过期记录（TTL 检查）
    2. 用覆盖率阈值替代宽松双向 in 匹配，避免短词误命中长词
    3. 返回覆盖率最高的匹配，而非第一个
    """
    query_key = normalize_key(query)
    best_item: dict | None = None
    best_coverage = 0.0

    for item in records:
        item_type = item.get("query_type", query_type)
        if item_type != query_type:
            continue
        if is_record_expired(item, query_type):
            continue

        item_key = normalize_key(item.get("query_key", item.get("hs_code_cn", "")))

        # 精确匹配立即返回
        if query_key == item_key:
            return item

        # 覆盖率匹配：较短串 / 较长串 >= 50%
        if not item_key or not query_key:
            continue
        if item_key in query_key:
            coverage = len(item_key) / len(query_key)
        elif query_key in item_key:
            coverage = len(query_key) / len(item_key)
        else:
            continue

        if coverage >= 0.5 and coverage > best_coverage:
            best_item = item
            best_coverage = coverage

    return best_item


def explain_result_status(field_name: str, item: dict | None, *, required: bool = True) -> str | None:
    if not item:
        if required:
            return f"{field_name} 未命中缓存、同步库和可信实时来源，需要人工复核。"
        return None

    if item.get("review_required"):
        quality = item.get("source_quality", "unknown")
        source = item.get("source_reference", "")
        if quality in {"unknown", "low"}:
            return f"{field_name} 仅命中{quality}质量来源（{source or source_label(item)}），需要人工复核。"
        return f"{field_name} 当前结果来自 {source_label(item)}，但仍建议人工复核。"

    confidence = item.get("confidence")
    try:
        confidence = float(confidence)
    except Exception:
        confidence = None
    if confidence is not None and confidence < 0.6:
        return f"{field_name} 结果可信度仅为 {confidence:.2f}，建议人工复核。"

    return None


def attach_reason(item: dict | None, field_name: str, *, required: bool = True) -> dict | None:
    if not item:
        return None
    enriched = dict(item)
    enriched["manual_review_reason"] = explain_result_status(field_name, enriched, required=required)
    return enriched


def contains_any(text: str, terms: list[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def build_declaration_elements(query: str, product: dict | None) -> dict:
    product_name = (product or {}).get("product_name_cn") or ""
    description = (product or {}).get("description") or ""
    combined = f"{query} {product_name} {description}"

    is_battery = contains_any(combined, ["电池", "蓄电池", "锂"])
    is_complete_set = contains_any(combined, ["整机", "成套", "套装"])
    may_be_dangerous = contains_any(combined, ["锂", "电池", "危险品"])
    usage = "供电/储能用途" if is_battery else "待补充"

    elements = {
        "product_name_declare": product_name or query,
        "usage": usage,
        "material": "待补充",
        "brand": "待补充",
        "model": "待补充",
        "is_battery": "是" if is_battery else "待补充",
        "is_complete_set": "是" if is_complete_set else "待补充",
        "dangerous_goods_flag": "可能涉及" if may_be_dangerous else "待补充",
        "declaration_factor_hint": "请结合材质、用途、品牌、型号、是否整机/零件补足申报要素。",
        "missing_fields": [],
    }
    for key in ["usage", "material", "brand", "model", "is_complete_set", "dangerous_goods_flag"]:
        if elements[key] == "待补充":
            elements["missing_fields"].append(key)
    return elements


def classify_product(query: str) -> dict | None:
    cache_records = load_records(knowledge_root() / "cache_store" / "records.json")
    cache_match = find_match(cache_records, query, "product")
    if cache_match:
        return cache_match

    records = load_records(knowledge_root() / "synced_hs_rules" / "records.json")
    if not records:
        records = load_records(knowledge_root() / "synced_hs_rules" / "sample.json")
    match = find_match(records, query, "product")
    if match:
        return match

    from subprocess import run
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "live_product.json"
        run(
            [
                "python3",
                str(Path(__file__).with_name("live_lookup_agent.py")),
                "--query",
                query,
                "--query-type",
                "product",
                "--output",
                str(output),
            ],
            check=True,
        )
        results = load_records(output)
        if results:
            # 写回缓存前标准化 HS 编码格式
            for r in results:
                if r.get("hs_code_cn"):
                    r["hs_code_cn"] = normalize_hs_code(r["hs_code_cn"])
            run(
                [
                    "python3",
                    str(Path(__file__).with_name("cache_writer.py")),
                    "--input",
                    str(output),
                ],
                check=True,
            )
            return results[0]
    return None


def lookup_bucket(query: str, query_type: str, synced_file: Path, fallback_hs_code: str | None) -> dict | None:
    cache_records = load_records(knowledge_root() / "cache_store" / "records.json")
    cache_match = find_match(cache_records, fallback_hs_code or query, query_type)
    if cache_match:
        return cache_match

    synced_records = load_records(synced_file)
    if not synced_records:
        sample_name = "sample.json"
        synced_records = load_records(synced_file.with_name(sample_name))
    synced_match = find_match(synced_records, fallback_hs_code or query, query_type)
    if synced_match:
        return synced_match

    from subprocess import run
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "live.json"
        run(
            [
                "python3",
                str(Path(__file__).with_name("live_lookup_agent.py")),
                "--query",
                query,
                "--query-type",
                query_type,
                "--output",
                str(output),
            ],
            check=True,
        )
        results = load_records(output)
        if results:
            # 写回缓存前标准化 HS 编码格式
            for r in results:
                if r.get("hs_code_cn"):
                    r["hs_code_cn"] = normalize_hs_code(r["hs_code_cn"])
            from subprocess import run as run2
            run2(
                [
                    "python3",
                    str(Path(__file__).with_name("cache_writer.py")),
                    "--input",
                    str(output),
                ],
                check=True,
            )
            return results[0]
    return None


def build_result(query: str) -> dict:
    product = classify_product(query)
    # 标准化从缓存/同步数据读出的 HS 编码（兼容旧格式如 "84716072.00"）
    if product and product.get("hs_code_cn"):
        product["hs_code_cn"] = normalize_hs_code(product["hs_code_cn"])
    hs_code = product.get("hs_code_cn") if product else None

    result = {
        "query": query,
        "hs_candidates_cn": [attach_reason(product, "HS编码候选", required=True)] if product else [],
        "declaration_elements": build_declaration_elements(query, product),
        "rebate_result": None,
        "supervision_result": None,
        "cn_id_mapping_result": None,
        "review_required": False,
        "needs_manual_review_reason": [],
    }

    if hs_code:
        result["rebate_result"] = attach_reason(lookup_bucket(
            query,
            "rebate",
            knowledge_root() / "synced_rebate_rates" / "records.json",
            hs_code,
        ), "出口退税率", required=True)
        result["supervision_result"] = attach_reason(lookup_bucket(
            query,
            "supervision",
            knowledge_root() / "synced_supervision_conditions" / "records.json",
            hs_code,
        ), "监管条件", required=True)
        result["cn_id_mapping_result"] = attach_reason(lookup_bucket(
            query,
            "cn_id_mapping",
            knowledge_root() / "synced_cn_id_mapping" / "records.json",
            hs_code,
        ), "中国-印尼编码映射", required=False)
    else:
        result["needs_manual_review_reason"].append("未能确认可用的 HS 编码候选，后续退税率、监管条件和映射查询无法可靠展开。")

    result["review_required"] = any(
        item and item.get("review_required")
        for item in [
            product,
            result["rebate_result"],
            result["supervision_result"],
            result["cn_id_mapping_result"],
        ]
    )
    review_reasons = [
        explain_result_status("HS编码候选", product, required=True),
        explain_result_status("出口退税率", result["rebate_result"], required=bool(hs_code)),
        explain_result_status("监管条件", result["supervision_result"], required=bool(hs_code)),
        explain_result_status("中国-印尼编码映射", result["cn_id_mapping_result"], required=False),
    ]
    result["needs_manual_review_reason"].extend(reason for reason in review_reasons if reason)
    if result["rebate_result"] is None and hs_code:
        result["needs_manual_review_reason"].append("退税率未找到满足字段级来源阈值的结果。")
    if result["supervision_result"] is None and hs_code:
        result["needs_manual_review_reason"].append("监管条件未找到满足字段级来源阈值的结果。")
    if result["cn_id_mapping_result"] is None and hs_code:
        result["needs_manual_review_reason"].append("中印尼编码映射未找到足够可信的候选结果。")
    # Deduplicate while preserving order.
    deduped: list[str] = []
    seen: set[str] = set()
    for reason in result["needs_manual_review_reason"]:
        if reason not in seen:
            seen.add(reason)
            deduped.append(reason)
    result["needs_manual_review_reason"] = deduped
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local HS customs workflow.")
    parser.add_argument("--query", required=True, help="Product description or hs code")
    parser.add_argument("--output", help="Optional output JSON path")
    parser.add_argument("--render-output-dir", help="Optional directory to render memo/summary outputs")
    args = parser.parse_args()

    result = build_result(args.query)
    if args.render_output_dir:
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            temp_json = Path(tmp) / "hs_result.json"
            dump_json(temp_json, result)
            subprocess.run(
                [
                    "python3",
                    str(Path(__file__).with_name("render_outputs.py")),
                    "--input",
                    str(temp_json),
                    "--output-dir",
                    args.render_output_dir,
                ],
                check=True,
            )
    if args.output:
        dump_json(Path(args.output), result)
    else:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
