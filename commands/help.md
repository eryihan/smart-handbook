---
description: Show Smart Handbook commands, arguments, and usage examples.
argument-hint: "[help|init|work|update|audit|status]"
disable-model-invocation: true
---

执行 `handbook help`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/commands.md`。

按命令说明中的帮助规则展示用途、参数、默认行为、写入范围和示例。参数指定有效命令时，仅展示该命令的帮助；无参数时展示命令表、首次使用顺序和示例。无效命令显示有效命令列表。

只读取插件说明，不扫描目标仓库，不创建 Handbook，不运行 check、impact 或测试。展示帮助后结束，不执行示例中的命令。

$ARGUMENTS
