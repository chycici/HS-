# 查询顺序

所有查询型结果必须遵循以下顺序：

1. `knowledge/cache_store`
2. `knowledge/synced_*`
3. `scripts/live_lookup_agent.py`
4. `scripts/cache_writer.py`
5. 人工复核

适用对象：
- 退税率
- 监管条件
- 中国-印尼编码候选映射
- 需要来源说明的税则辅助信息

字段级实时补查策略：
- `product`: 优先 `customs.gov.cn`、`gov.cn`、`transcustoms.cn`
- `rebate`: 优先 `chinatax.gov.cn`、`gov.cn`、`customs.gov.cn`
- `supervision`: 优先 `customs.gov.cn`、`gov.cn`、`transcustoms.cn`
- `cn_id_mapping`: 优先 `gov.cn`、`customs.gov.cn`、`mofcom.gov.cn`

低质量来源：
- 论坛
- 问答站
- 博客
- 非结构化转载页

对于低质量来源或未知来源：
- 自动降权
- 默认建议人工复核

禁止：
- 无来源猜测退税率
- 无来源猜测监管条件
- 无来源猜测印尼对应编码
