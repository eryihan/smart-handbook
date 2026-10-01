# handbook status

读取 `.smart-handbook/` 中已有页面和 `.state.json`，展示已记录状态。该工作流不扫描源码，不执行 `check`、`impact` 或测试。

## 查询内容

读取 README、map、页面 metadata 的 coverage，以及状态中的来源、review 和 verification 记录，输出：

- 已记录模块数、documented 数、navigation-only 数和 known-gap 数。
- 已知待复核页面、失效引用与来源变化。
- 行为验证记录、已知缺口和未验证环境。
- 上次来源检查、AI 复核和验证记录中的时间与适用条件。

模块数量只计算已记录内容。缺少扫描范围时不能声称全库覆盖；缺少 `source_state` 时显示 `unknown`，不得现场计算 hash。

复核时间表示当时的代码分析，`verified` 表示记录条件下的历史观察。缺少来源检查时间时注明时间未知，不推断内容当前有效。

展示上述记录后结束；需要重新检查时说明可使用 audit，不在本次查询中执行。

## 状态缺失

无 Handbook 时报告尚未建立。状态文件缺失、损坏或 schema 不支持时报告状态不可用，保留业务 Markdown，不自动重建或覆盖。后续可按需求执行 init 或 audit。

字段含义见[格式契约](../schema.md)。
