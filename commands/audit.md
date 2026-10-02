---
description: Read-only audit of handbook structure, source evidence, coverage, and business content.
argument-hint: "[目标版本或审计范围]"
disable-model-invocation: true
---

执行 `handbook audit`。读取 `${CLAUDE_PLUGIN_ROOT}/SKILL.md` 的公共约束，再读取 `${CLAUDE_PLUGIN_ROOT}/references/workflows/audit.md`。

此入口固定为 audit；后续参数作为审计范围。项目知识位于目标仓库的 `.smart-handbook/`，资源从插件目录读取。

只检查并报告，不修改目标仓库文件。发现问题后由用户选择 update 修复，不自动转入写入流程。

$ARGUMENTS

无参数时，检查当前目标仓库及任务版本。
