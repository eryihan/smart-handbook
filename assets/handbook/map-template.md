# 模块地图

<!-- handbook-meta
{
  "schema_version": 3,
  "id": "handbook-map",
  "kind": "map",
  "coverage": "navigation-only",
  "claims": [],
  "modules": [],
  "unowned_entries": []
}
-->

## 模块导航

| 模块 ID / 名称 | 业务词 / 症状 / 编号 | 职责 | 页面 | 源码 / 配置范围 |
|---|---|---|---|---|

按职责、入口、数据、状态和编排关系划分模块。填写 metadata 的 modules，保持页面路径及源码、配置范围与 module 页一致。

业务划分由 Agent 根据实现判断。逐文件、逐入口的完整归属与进度保存在 `.inventory.json`，本页保留业务导航，不复制整份清单。

## 关键交接关系

链接到相关 module / flow，说明从哪个任务或入口进入。行为和约束在对应页面维护。

## 未归属入口与导航缺口

在正文和 unowned_entries 中保留当前未归属入口、原因及后续核对位置。发现方法与完整范围以清单为准，本页仅摘要仍影响导航的范围；归属确认后更新导航并移除旧缺口，不追加每次发现记录。
