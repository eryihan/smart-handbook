---
description: Show recorded handbook coverage, review, verification, and gaps.
argument-hint: "[目标仓库]"
disable-model-invocation: true
---

执行 `handbook status`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/workflows/status.md`。

此入口固定为 status；后续参数作为目标范围。项目知识位于目标仓库的 `.smart-handbook/`，资源从插件目录读取。
只读取已有 Handbook 与状态，不扫描源码，不执行 check、impact 或测试。

$ARGUMENTS

无参数时，展示当前目标仓库的已记录状态。
