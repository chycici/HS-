# HS海关编码部署说明

## 部署位置
本工作流已部署到：

`<skill-dir>`

该目录位于 workspace 的 `skills/` 下，符合当前 OpenClaw 在本仓库中的技能识别习惯，可作为一个独立技能目录被扫描到。

## 已建立结构
```text
HS海关编码
├── SKILL.md
├── workflow.yaml
├── docs/
│   └── deployment_guide.md
├── knowledge/
│   ├── cache_store/
│   ├── declaration_templates/
│   ├── historical_classification_cases/
│   ├── synced_cn_id_mapping/
│   ├── synced_hs_rules/
│   ├── synced_rebate_rates/
│   └── synced_supervision_conditions/
├── output/
├── templates/
│   ├── classification_memo_templates/
│   ├── invoice_templates/
│   └── packing_list_templates/
└── workflows/
    ├── data_sync_workflow.yaml
    ├── export_customs_autosync_workflow.yaml
    └── live_lookup_fallback_workflow.yaml
```

## 当前入口
- 主入口：`workflow.yaml`
- 主业务流：`workflows/export_customs_autosync_workflow.yaml`
- 自动同步流：`workflows/data_sync_workflow.yaml`
- 实时补查流：`workflows/live_lookup_fallback_workflow.yaml`

## 查询顺序
1. `cache_store`
2. `synced_*`
3. `live_lookup_agent`
4. `cache_writer`
5. 人工复核

## 风控约束
- 不猜退税率
- 不猜监管条件
- 不猜印尼对应编码
- 图片识别仅做初判
- 历史案例只作辅助
- 所有查询型结果保留来源、时间、可信度字段

## 后续建议
1. 为 `live_lookup_agent` 接入实际外部查询脚本
2. 为 `data_sync_workflow` 接入 PDF / Excel / HTML 解析器
3. 在 `knowledge/` 下补充 schema 和样例数据
4. 如果你希望直接可运行，我可以下一步继续给这个 workflow 补 `agents/`、脚本和示例输入输出
