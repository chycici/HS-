# HS海关编码系统 — Hermes Agent Skill

面向出口报关场景的智能HS编码归类与查询系统。采用"免手工录库"设计理念，优先自动同步与实时补查。

## 功能

- 🔍 **智能商品归类** — 根据文本/技术文档自动抽取商品属性，推荐HS编码
- 💰 **退税率查询** — 查询出口退税率（缓存30天，超期自动补查）
- ⚠️ **监管条件识别** — 识别监管条件代码及所需单证
- 🌏 **中印尼编码映射** — 中国-印尼HS编码候选对应关系
- 📝 **报关要素生成** — 自动生成完整的报关要素

## 安装（Hermes Agent）

```bash
# 一键安装
bash <(curl -fsSL https://raw.githubusercontent.com/chycici/HS-/main/install.sh)

# 或手动复制
git clone --depth=1 https://github.com/chycici/HS-.git /tmp/hs
cp -r /tmp/hs/skills/HS海关编码 ~/.hermes/skills/
rm -rf /tmp/hs
```

安装后重启 Hermes Agent 或在会话中使用 `/refresh` 即可加载该技能。

## 使用方法

在 Hermes Agent 中对助理说：
- "帮我查查锂电池的HS编码"
- "太阳能板的出口退税率是多少"
- "生成这批货的报关资料"

## 数据来源

- 海关总署2025年税则
- 税务总局出口退税率数据
- 中印尼HS编码对应关系

## 设计原则

1. **数据来源透明** — 所有查询结果标记来源、时间、可信度
2. **多级查询** — 缓存 → 同步数据 → 实时补查 → 人工复核
3. **不猜数据** — 不猜测退税率、监管条件、印尼对应编码

## 文件结构

```
skills/HS海关编码/
├── SKILL.md                     # 技能入口
├── workflow.yaml                # 主工作流
├── references/                  # 参考文档
├── scripts/                     # Python脚本
├── knowledge/                   # 知识库（缓存+同步数据）
├── templates/                   # 模板文件
└── docs/                        # 部署/使用说明
```

## License

MIT
