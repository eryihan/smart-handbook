---
description: Build, resume, or explicitly rebuild a full project handbook in .smart-handbook/.
argument-hint: "[目标仓库或范围]"
disable-model-invocation: true
---

执行 `handbook init`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/workflows/init.md`。

此入口固定为 init；后续参数作为任务或范围。项目知识位于目标仓库的 `.smart-handbook/`，资源从插件目录读取。

$ARGUMENTS

无参数时，以当前任务所在仓库为目标。
