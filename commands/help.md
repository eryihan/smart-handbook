---
description: Show Smart Handbook commands, arguments, and usage examples.
argument-hint: "[help|init|update|audit]"
disable-model-invocation: true
---

执行 `handbook help`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/commands.md`。

按命令说明的“帮助输出”规则处理参数并展示用法。

只读取插件说明，不扫描目标仓库，不创建 Handbook，不运行 check、impact 或测试。展示帮助后结束，不执行示例中的命令。

$ARGUMENTS
