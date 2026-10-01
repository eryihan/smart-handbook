---
description: Show Smart Handbook commands, arguments, and usage examples.
argument-hint: "[help|init|work|update|audit|status]"
disable-model-invocation: true
---

执行 `handbook help`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/commands.md`。

展示命令用途、参数和示例。参数指定有效命令时，仅展示该命令的帮助；需要执行细节时读取其对应工作流。无参数时展示全部命令和首次使用顺序。无效命令显示有效命令列表。

只读取插件说明，不扫描目标仓库，不创建 Handbook，不运行 check、impact 或测试。

$ARGUMENTS
