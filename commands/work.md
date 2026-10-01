---
description: Understand, develop, debug, or maintain a project with source-backed handbook context.
argument-hint: "<任务>"
disable-model-invocation: true
---

执行 `handbook work`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/workflows/work.md`。

此入口固定为 work；后续参数作为任务。项目知识位于目标仓库的 `.smart_handbook/`，资源从插件目录读取。

$ARGUMENTS

无参数时展示 work 的用法和任务示例，等待任务描述。
