# HS海关编码使用说明

## 初始化样例数据

```bash
python3 <skill-dir>/scripts/bootstrap_sample_data.py
```

## 执行本地工作流

```bash
python3 <skill-dir>/scripts/hs_workflow.py \
  --query "锂离子蓄电池组"
```

如需直接输出 memo / 摘要文件：

```bash
python3 <skill-dir>/scripts/hs_workflow.py \
  --query "锂离子蓄电池组" \
  --render-output-dir <skill-dir>/output
```

输出中会包含：

- `review_required`
- `needs_manual_review_reason`
- 每个字段结果内的 `manual_review_reason`

## 导入公开资料到同步知识层

```bash
python3 <skill-dir>/scripts/data_sync.py \
  --source /absolute/path/to/rebate.csv \
  --target rebate
```

可选 `--target`：

- `hs`
- `rebate`
- `supervision`
- `mapping`

## 当前可运行范围

- 查询顺序已落地为 `cache -> synced -> live lookup -> cache writeback`
- 支持 CSV / JSON 导入到同步知识层
- 支持真实联网实时补查与缓存回写
- `live_lookup_agent` 优先使用 Tavily，未配置时回退到公开网页搜索
- 若已配置 DeepSeek，会把搜索结果进一步整理成结构化 JSON 候选
- 实时补查会对来源做质量分级并自动降权低质量站点
- `product / rebate / supervision / cn_id_mapping` 已启用字段级来源偏好策略
- 主 workflow 会在未命中或低可信时输出明确的人工复核原因
- 支持渲染 Markdown 版归类意见 memo 和查询摘要
- 支持渲染报关要素草稿和对外沟通说明
- 输出包含结构化 `declaration_elements`，可用于继续扩展正式申报草稿
- 支持自动生成补料清单，便于向客户或业务收集缺失资料
- 支持生成补料回填 JSON 模板，并可基于补充信息二次刷新输出件

## 补料回填后刷新输出

```bash
python3 <skill-dir>/scripts/apply_intake_update.py \
  --base-json <skill-dir>/output/锂离子蓄电池组.json \
  --intake-json <skill-dir>/output/锂离子蓄电池组-intake-response.json \
  --output-dir <skill-dir>/output
```

## 当前未接入

- PDF / Excel / HTML 表格深度解析
- 图像识别与文档抽取模型
- 更细粒度的官方源优先级策略与按字段分项评分细则
