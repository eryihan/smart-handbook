---
description: Review source changes and update affected handbook pages.
argument-hint: "[变更基线、目标版本或范围]"
disable-model-invocation: true
---

执行 `handbook update`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/workflows/update.md`。

此入口固定为 update；后续参数作为比较范围。项目知识位于目标仓库的 `.smart_handbook/`，资源从插件目录读取。

$ARGUMENTS

无参数时按已有状态确定基线；缺少基线时记录缺口。
