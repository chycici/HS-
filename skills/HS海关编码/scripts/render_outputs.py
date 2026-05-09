#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from common import dump_json, load_json, now_iso, skill_root


def stringify(value) -> str:
    if value is None:
        return "未获取"
    if isinstance(value, list):
        return "、".join(str(item) for item in value) if value else "未获取"
    return str(value)


def friendly_missing_field(name: str) -> str:
    mapping = {
        "usage": "用途说明",
        "material": "材质信息",
        "brand": "品牌信息",
        "model": "型号信息",
        "is_complete_set": "是否整机/成套",
        "dangerous_goods_flag": "危险品属性",
    }
    return mapping.get(name, name)


def build_context(payload: dict) -> dict[str, str]:
    product = (payload.get("hs_candidates_cn") or [{}])[0] if payload.get("hs_candidates_cn") else {}
    declaration = payload.get("declaration_elements") or {}
    rebate = payload.get("rebate_result") or {}
    supervision = payload.get("supervision_result") or {}
    mapping = payload.get("cn_id_mapping_result") or {}
    reasons = payload.get("needs_manual_review_reason") or []
    missing_fields = declaration.get("missing_fields", []) or []
    return {
        "query": stringify(payload.get("query")),
        "generated_at": now_iso(),
        "review_required": "是" if payload.get("review_required") else "否",
        "hs_code_cn": stringify(product.get("hs_code_cn")),
        "product_name_cn": stringify(product.get("product_name_cn")),
        "product_description": stringify(product.get("description") or product.get("mapping_basis")),
        "product_source_type": stringify(product.get("source_type")),
        "product_source_quality": stringify(product.get("source_quality")),
        "product_source_reference": stringify(product.get("source_reference")),
        "product_confidence": stringify(product.get("confidence")),
        "product_manual_review_reason": stringify(product.get("manual_review_reason")),
        "declare_product_name": stringify(declaration.get("product_name_declare")),
        "declare_usage": stringify(declaration.get("usage")),
        "declare_material": stringify(declaration.get("material")),
        "declare_brand": stringify(declaration.get("brand")),
        "declare_model": stringify(declaration.get("model")),
        "declare_is_battery": stringify(declaration.get("is_battery")),
        "declare_is_complete_set": stringify(declaration.get("is_complete_set")),
        "declare_dangerous_goods_flag": stringify(declaration.get("dangerous_goods_flag")),
        "declare_factor_hint": stringify(declaration.get("declaration_factor_hint")),
        "declare_missing_fields": "\n".join(
            f"- {friendly_missing_field(item)}" for item in missing_fields
        ) if missing_fields else "- 当前无明显缺失项",
        "intake_missing_items": "\n".join(
            f"- {friendly_missing_field(item)}"
            for item in missing_fields
        ) if missing_fields else "- 当前无必须补充项",
        "rebate_rate": stringify(rebate.get("rebate_rate")),
        "rebate_source_type": stringify(rebate.get("source_type")),
        "rebate_source_quality": stringify(rebate.get("source_quality")),
        "rebate_source_reference": stringify(rebate.get("source_reference")),
        "rebate_confidence": stringify(rebate.get("confidence")),
        "rebate_manual_review_reason": stringify(rebate.get("manual_review_reason")),
        "supervision_code": stringify(supervision.get("supervision_code")),
        "required_documents": stringify(supervision.get("required_documents")),
        "supervision_source_type": stringify(supervision.get("source_type")),
        "supervision_source_quality": stringify(supervision.get("source_quality")),
        "supervision_source_reference": stringify(supervision.get("source_reference")),
        "supervision_confidence": stringify(supervision.get("confidence")),
        "supervision_manual_review_reason": stringify(supervision.get("manual_review_reason")),
        "cn_hs_code": stringify(mapping.get("cn_hs_code") or product.get("hs_code_cn")),
        "id_hs_code": stringify(mapping.get("id_hs_code")),
        "mapping_basis": stringify(mapping.get("mapping_basis")),
        "mapping_source_type": stringify(mapping.get("source_type")),
        "mapping_source_quality": stringify(mapping.get("source_quality")),
        "mapping_source_reference": stringify(mapping.get("source_reference")),
        "mapping_confidence": stringify(mapping.get("confidence")),
        "mapping_manual_review_reason": stringify(mapping.get("manual_review_reason")),
        "needs_manual_review_reason": "\n".join(f"- {item}" for item in reasons) if reasons else "- 当前无额外人工复核提示",
    }


def render_template(template_text: str, context: dict[str, str]) -> str:
    rendered = template_text
    for key, value in context.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(description="Render HS memo and summary markdown outputs.")
    parser.add_argument("--input", required=True, help="HS workflow JSON result path")
    parser.add_argument(
        "--output-dir",
        default=str(skill_root() / "output"),
        help="Output directory for rendered files",
    )
    args = parser.parse_args()

    payload = load_json(Path(args.input), {})
    context = build_context(payload)
    template_dir = skill_root() / "templates" / "classification_memo_templates"
    memo_tpl = (template_dir / "memo.md.tpl").read_text(encoding="utf-8")
    summary_tpl = (template_dir / "summary.md.tpl").read_text(encoding="utf-8")
    declaration_tpl = (template_dir / "declaration-draft.md.tpl").read_text(encoding="utf-8")
    client_tpl = (template_dir / "client-note.md.tpl").read_text(encoding="utf-8")
    intake_tpl = (template_dir / "intake-checklist.md.tpl").read_text(encoding="utf-8")
    intake_response_tpl = (template_dir / "intake-response.json.tpl").read_text(encoding="utf-8")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = str(payload.get("query", "hs-query")).replace("/", "-").replace(" ", "_")
    memo_path = output_dir / f"{stem}-memo.md"
    summary_path = output_dir / f"{stem}-summary.md"
    declaration_path = output_dir / f"{stem}-declaration-draft.md"
    client_path = output_dir / f"{stem}-client-note.md"
    intake_path = output_dir / f"{stem}-intake-checklist.md"
    intake_response_path = output_dir / f"{stem}-intake-response.json"
    json_path = output_dir / f"{stem}.json"

    memo_path.write_text(render_template(memo_tpl, context), encoding="utf-8")
    summary_path.write_text(render_template(summary_tpl, context), encoding="utf-8")
    declaration_path.write_text(render_template(declaration_tpl, context), encoding="utf-8")
    client_path.write_text(render_template(client_tpl, context), encoding="utf-8")
    intake_path.write_text(render_template(intake_tpl, context), encoding="utf-8")
    intake_response_path.write_text(render_template(intake_response_tpl, context), encoding="utf-8")
    dump_json(json_path, payload)
    print(str(memo_path))
    print(str(summary_path))
    print(str(declaration_path))
    print(str(client_path))
    print(str(intake_path))
    print(str(intake_response_path))
    print(str(json_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
