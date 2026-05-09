#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import urllib.parse
from pathlib import Path

from common import (
    dump_json,
    get_provider_api_key,
    http_get,
    http_post_json,
    keys_match,
    load_json,
    normalize_hs_code,
    normalize_key,
    now_iso,
    skill_root,
)

SOURCE_RULES = [
    {"pattern": "customs.gov.cn", "tier": "official", "weight": 1.0},
    {"pattern": "gov.cn", "tier": "official", "weight": 0.95},
    {"pattern": "chinatax.gov.cn", "tier": "official", "weight": 0.95},
    {"pattern": "mofcom.gov.cn", "tier": "official", "weight": 0.92},
    {"pattern": "transcustoms.cn", "tier": "reference", "weight": 0.82},
    {"pattern": "baiducc.com", "tier": "reference", "weight": 0.72},
    {"pattern": "365area.com", "tier": "reference", "weight": 0.68},
    {"pattern": "10100.com", "tier": "reference", "weight": 0.6},
]

LOW_QUALITY_PATTERNS = [
    "bbs.",
    "forum",
    "tieba",
    "zhidao",
    "blog",
    "csdn",
]

FIELD_STRATEGIES = {
    "product": {
        "preferred_patterns": ["customs.gov.cn", "gov.cn", "transcustoms.cn", "365area.com"],
        "signal_terms": ["hs", "海关编码", "税则", "归类"],
        "min_weight": 0.45,
    },
    "rebate": {
        "preferred_patterns": ["chinatax.gov.cn", "gov.cn", "customs.gov.cn", "transcustoms.cn"],
        "signal_terms": ["退税率", "出口退税", "%"],
        "min_weight": 0.55,
    },
    "supervision": {
        "preferred_patterns": ["customs.gov.cn", "gov.cn", "transcustoms.cn"],
        "signal_terms": ["监管条件", "检验检疫", "申报要素"],
        "min_weight": 0.55,
    },
    "cn_id_mapping": {
        "preferred_patterns": ["gov.cn", "customs.gov.cn", "mofcom.gov.cn", "transcustoms.cn"],
        "signal_terms": ["印尼", "Indonesia", "BTKI", "对应"],
        "min_weight": 0.5,
    },
}


def source_quality(url: str) -> tuple[str, float]:
    host = urllib.parse.urlparse(url).netloc.lower()
    for rule in SOURCE_RULES:
        if rule["pattern"] in host:
            return rule["tier"], rule["weight"]
    for pattern in LOW_QUALITY_PATTERNS:
        if pattern in host:
            return "low", 0.25
    return "unknown", 0.45


def matches_preferred_host(url: str, query_type: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    strategy = FIELD_STRATEGIES.get(query_type, FIELD_STRATEGIES["product"])
    return any(pattern in host for pattern in strategy["preferred_patterns"])


def score_search_result(item: dict, query_type: str) -> dict:
    tier, weight = source_quality(item.get("url", ""))
    text = f"{item.get('title','')} {item.get('snippet','')}"
    score = weight
    strategy = FIELD_STRATEGIES.get(query_type, FIELD_STRATEGIES["product"])
    if re.search(r"\b\d{8,10}\b", text):
        score += 0.08
    if "%" in text:
        score += 0.05
    if "监管条件" in text:
        score += 0.05
    if matches_preferred_host(item.get("url", ""), query_type):
        score += 0.08
    lowered = text.lower()
    matched_terms = [term for term in strategy["signal_terms"] if term.lower() in lowered]
    score += min(0.09, 0.03 * len(matched_terms))
    item["source_quality"] = tier
    item["matched_terms"] = matched_terms
    item["source_weight"] = round(min(score, 1.0), 3)
    return item


def rank_search_results(results: list[dict], query_type: str) -> list[dict]:
    strategy = FIELD_STRATEGIES.get(query_type, FIELD_STRATEGIES["product"])
    scored = [score_search_result(dict(item), query_type) for item in results]
    scored = [item for item in scored if item.get("source_weight", 0) >= strategy["min_weight"]]
    scored.sort(
        key=lambda item: (
            item.get("source_weight", 0),
            len(item.get("snippet", "")),
        ),
        reverse=True,
    )
    return scored


def tavily_search(query: str, max_results: int, query_type: str) -> list[dict]:
    key = get_provider_api_key("tavily")
    if not key:
        return []
    payload = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "search_depth": "basic",
        "include_answer": False,
        "include_images": False,
        "include_raw_content": False,
    }
    try:
        obj = http_post_json("https://api.tavily.com/search", payload, timeout=12)
    except Exception:
        return []
    results = []
    for item in (obj.get("results") or [])[:max_results]:
        results.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "snippet": item.get("content", ""),
                "engine": "tavily",
            }
        )
    return rank_search_results(results, query_type)


def ddg_search(query: str, max_results: int, query_type: str) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    try:
        html = http_get(url, timeout=12)
    except Exception:
        return []

    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>.*?'
        r'<a[^>]*class="result__snippet"[^>]*>(?P<snippet>.*?)</a>',
        re.S,
    )
    results = []
    for match in pattern.finditer(html):
        title = re.sub(r"<.*?>", "", match.group("title")).strip()
        snippet = re.sub(r"<.*?>", "", match.group("snippet")).strip()
        raw_url = match.group("url")
        parsed = urllib.parse.urlparse(raw_url)
        if parsed.path == "/l/":
            target = urllib.parse.parse_qs(parsed.query).get("uddg", [""])[0]
            url_value = urllib.parse.unquote(target) if target else raw_url
        else:
            url_value = raw_url
        results.append(
            {
                "title": title,
                "url": url_value,
                "snippet": snippet,
                "engine": "duckduckgo",
            }
        )
        if len(results) >= max_results:
            break
    return rank_search_results(results, query_type)


def heuristic_extract(query: str, query_type: str, results: list[dict]) -> list[dict]:
    """从搜索摘要中用正则启发式抽取字段。

    修复：按 query_type 限制各字段的抽取范围，避免把非退税率的百分比
    （如增长率、市占率）误当退税率写入缓存。
    """
    joined = "\n".join(
        f"{item.get('title','')} {item.get('snippet','')} {item.get('url','')}" for item in results
    )
    hs_match = re.search(r"\b(\d{8,10})\b", joined)

    # 只在退税类查询中抽取百分比，且要求上下文包含退税相关词
    rate_match = None
    if query_type == "rebate":
        rate_match = re.search(
            r"(?:退税率|出口退税)[^\d]*(\d{1,2}(?:\.\d+)?)\s*%", joined
        ) or re.search(
            r"(\d{1,2}(?:\.\d+)?)\s*%[^\d]*(?:退税|出口退税)", joined
        )

    # 只在监管条件类查询中抽取监管码
    supervision_match = None
    if query_type == "supervision":
        supervision_match = re.search(r"监管条件[^A-Z0-9]*([A-Z0-9]{1,4})", joined)

    if not hs_match and not rate_match and not supervision_match:
        return []

    top = results[0] if results else {}
    hs_code = normalize_hs_code(hs_match.group(1)) if hs_match else ""
    return [
        {
            "query_key": query,
            "query_type": query_type,
            "hs_code_cn": hs_code,
            "rebate_rate": f"{rate_match.group(1)}%" if rate_match else "",
            "supervision_code": supervision_match.group(1) if supervision_match else "",
            "source_type": "live_lookup",
            "source_reference": top.get("url", "web://heuristic"),
            "fetched_at": now_iso(),
            "source_quality": top.get("source_quality", "unknown"),
            "confidence": round(min(top.get("source_weight", 0.35), 0.55), 2),
            "review_required": True,
        }
    ]


def compose_search_query(query: str, query_type: str) -> str:
    if query_type == "rebate":
        return f"{query} 中国 出口 退税率"
    if query_type == "supervision":
        return f"{query} 中国 海关 监管条件"
    if query_type == "cn_id_mapping":
        return f"{query} 中国 印尼 HS 编码 对应"
    return f"{query} 中国 出口 HS 编码 归类"


def deepseek_extract(query: str, query_type: str, results: list[dict]) -> list[dict]:
    key = get_provider_api_key("deepseek")
    if not key or not results:
        return []

    source_lines = []
    for index, item in enumerate(results[:6], start=1):
        source_lines.append(
            f"[{index}] 标题: {item.get('title','')}\n"
            f"URL: {item.get('url','')}\n"
            f"摘要: {item.get('snippet','')}\n"
        )

    prompt = (
        "你是海关编码查询结构化助手。"
        "你只能基于给定搜索结果提取候选信息，不能编造。"
        "如果证据不足，就返回空数组。"
        "优先采用与查询类型匹配的高可信来源，忽略论坛、问答、博客。"
        "请输出 JSON 数组，每个元素只包含这些字段："
        "query_key, query_type, hs_code_cn, product_name_cn, description, rebate_rate, "
        "supervision_code, required_documents, id_hs_code, mapping_basis, source_type, "
        "source_reference, fetched_at, confidence, review_required。"
        "其中 source_type 固定为 live_lookup，fetched_at 用字符串 now，"
        "confidence 为 0 到 1，review_required 默认 true。"
    )
    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": (
                    f"查询词: {query}\n"
                    f"查询类型: {query_type}\n"
                    "搜索结果如下：\n"
                    + "\n".join(source_lines)
                ),
            },
        ],
        "temperature": 0.1,
    }
    try:
        obj = http_post_json(
            "https://api.deepseek.com/chat/completions",
            payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "Authorization": f"Bearer {key}",
            },
            timeout=18,
        )
        text = (
            obj.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
            .strip()
        )
        text = re.sub(r"^```json\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            return []
    except Exception:
        return []

    normalized = []
    strategy = FIELD_STRATEGIES.get(query_type, FIELD_STRATEGIES["product"])
    for item in parsed:
        if not isinstance(item, dict):
            continue
        item["query_key"] = item.get("query_key") or query
        item["query_type"] = item.get("query_type") or query_type
        item["source_type"] = "live_lookup"
        item["fetched_at"] = now_iso()
        ref = item.get("source_reference", "")
        tier, weight = source_quality(ref)
        item["source_quality"] = tier
        model_confidence = item.get("confidence", 0.5)
        try:
            model_confidence = float(model_confidence)
        except Exception:
            model_confidence = 0.5
        item["confidence"] = round(min(model_confidence, weight), 2)
        item["review_required"] = item.get("review_required", True) or tier != "official"
        if item.get("hs_code_cn"):
            item["hs_code_cn"] = normalize_hs_code(item["hs_code_cn"])
        if not matches_preferred_host(ref, query_type) and tier == "unknown":
            item["confidence"] = round(min(item["confidence"], strategy["min_weight"]), 2)
            item["review_required"] = True
        if item["confidence"] < strategy["min_weight"]:
            continue
        normalized.append(item)
    normalized.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    return normalized


def lookup(query: str, query_type: str) -> list[dict]:
    search_query = compose_search_query(query, query_type)
    results = tavily_search(search_query, 5, query_type)
    if not results:
        results = ddg_search(search_query, 5, query_type)

    structured = deepseek_extract(query, query_type, results)
    if structured:
        return structured

    heuristic = heuristic_extract(query, query_type, results)
    if heuristic:
        return heuristic

    # 最后降级到 sample 示例数据——明确标注来源，置极低可信度
    sample_path = skill_root() / "examples" / "live_lookup_candidates.json"
    candidates = load_json(sample_path, [])
    query_key = normalize_key(query)
    matches = []
    for item in candidates:
        item_key = normalize_key(item.get("query_key", ""))
        item_type = item.get("query_type", "product")
        if keys_match(query_key, item_key):
            candidate = dict(item)
            candidate["query_type"] = query_type or candidate.get("query_type", item_type)
            candidate["fetched_at"] = now_iso()
            # 标注为 sample，避免被当作真实查询结果
            candidate["source_type"] = "sample"
            candidate["source_quality"] = "low"
            candidate["confidence"] = 0.08
            candidate["review_required"] = True
            candidate["manual_review_reason"] = "结果来自本地示例数据，非实时查询，必须人工复核。"
            matches.append(candidate)
    return matches


def main() -> int:
    parser = argparse.ArgumentParser(description="Fallback live lookup agent using local sample sources.")
    parser.add_argument("--query", required=True, help="Query text or hs code")
    parser.add_argument("--query-type", default="product", help="Query type")
    parser.add_argument("--output", required=True, help="Output JSON file")
    args = parser.parse_args()

    dump_json(Path(args.output), lookup(args.query, args.query_type))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
