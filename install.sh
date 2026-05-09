#!/usr/bin/env bash
# HS海关编码 — 一键安装 Hermes Agent Skill
set -euo pipefail

REPO_OWNER="${REPO_OWNER:-chycici}"
REPO_NAME="${REPO_NAME:-HS-}"
BRANCH="${BRANCH:-main}"
SKILL_NAME="HS海关编码"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SKILL_DIR="$HERMES_HOME/skills/$SKILL_NAME"

echo "📦 安装 $SKILL_NAME ..."
mkdir -p "$SKILL_DIR"

BASE_URL="https://raw.githubusercontent.com/$REPO_OWNER/$REPO_NAME/$BRANCH/skills/$SKILL_NAME"

# 核心文件
echo "  下载 SKILL.md ..."
curl -fsSL "$BASE_URL/SKILL.md" -o "$SKILL_DIR/SKILL.md"

# 脚本
echo "  下载脚本 ..."
for s in apply_intake_update bootstrap_sample_data cache_writer common data_sync hs_workflow import_parser live_lookup_agent render_outputs source_normalizer; do
  curl -fsSL "$BASE_URL/scripts/$s.py" -o "$SKILL_DIR/scripts/$s.py"
done

# 文档
for f in deployment_guide usage; do
  curl -fsSL "$BASE_URL/docs/$f.md" -o "$SKILL_DIR/docs/$f.md"
done

# 参考
for f in query-order internal-schema; do
  curl -fsSL "$BASE_URL/references/$f.md" -o "$SKILL_DIR/references/$f.md"
done

# 工作流
echo "  下载工作流 ..."
for w in workflow data_sync_workflow export_customs_autosync_workflow live_lookup_fallback_workflow; do
  curl -fsSL "$BASE_URL/$w.yaml" -o "$SKILL_DIR/$w.yaml" 2>/dev/null || \
    curl -fsSL "$BASE_URL/workflows/$w.yaml" -o "$SKILL_DIR/workflows/$w.yaml"
done

# 知识库（缓存数据）
echo "  下载知识库数据 ..."
for dir in cache_store synced_hs_rules synced_rebate_rates synced_supervision_conditions synced_cn_id_mapping; do
  mkdir -p "$SKILL_DIR/knowledge/$dir"
  curl -fsSL "$BASE_URL/knowledge/$dir/records.json" -o "$SKILL_DIR/knowledge/$dir/records.json" 2>/dev/null || true
done
curl -fsSL "$BASE_URL/knowledge/sync_report.json" -o "$SKILL_DIR/knowledge/sync_report.json" 2>/dev/null || true

# 完整性校验
if [ -f "$SKILL_DIR/SKILL.md" ]; then
  echo "✅ $SKILL_NAME 安装完成 → $SKILL_DIR"
else
  echo "❌ 下载失败，请检查网络连接"
  exit 1
fi
