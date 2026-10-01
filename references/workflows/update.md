# handbook update

根据源码变化形成候选范围，再阅读代码决定局部更新内容。

无 Handbook 时报告尚未建立，不自动初始化。

## 识别与复核

1. 读取 `.smart-handbook/.state.json` 和现有 metadata，保留旧来源关联。确认基线、目标 commit / worktree，以及未提交修改是否在比较范围内。
2. 运行 `impact`，查看变更文件、直接 claim、旧页面关联、相关 module / flow 和未归属变化。
3. 阅读候选项的实际代码与 diff。公共组件、共享配置或未归属变更可能影响其他调用方和流程，按实现关系扩大阅读范围。
4. 为每个候选项记录有源码依据的处置：无影响、定位变化、行为变化、新增知识、删除知识、需要扩大分析范围。
5. 修改受影响内容的权威页面。入口或模块迁移时同步 map、module 范围、flow 参与关系和 README 导航。
6. 运行 `check` 修复路径、symbol、链接和结构错误。完成复核后保存该页的新指纹与 review；行为验证单独记录条件、方法和结果。

## 工具调用

工具从 Skill 安装目录调用，`--root` 指向目标仓库。以下示例使用状态中的基线与当前 worktree；需要其他比较范围时传入已确认的 `--base`、`--target`。

```sh
python3 "<skill-directory>/scripts/handbook.py" impact --root "<project-directory>" --format json
python3 "<skill-directory>/scripts/handbook.py" check --root "<project-directory>" --format json
```

读取 impact 的候选关联后再复核代码。check 的来源摘要位于 `pages[页面路径].sources[来源路径].fingerprint`；只有已复核页面的新摘要可写入 `.state.json`。

## 保留基线与旧关联

删除 claim、来源路径或页面前，先分析旧状态中的关联，避免提前替换指纹导致候选丢失。

局部复核保留原 `baseline.commit`，各已复核页面保存自己的指纹。只有从旧基线到目标版本的全部变更完成归属与处置，才能推进全库 commit；后续候选中重复出现已处理项可以逐项确认。

状态无法解析时保留业务 Markdown 和原状态，修复状态或根据已确认来源重建。缺少历史记录时标记 `baseline unavailable`。

## 工具降级

Python 不可用时手工比较和核对，记录 `automated check unavailable`。Git 不可用时只比较已有指纹；该范围无法覆盖新增、未引用文件或间接依赖，不能据此报告全库无变化。

CLI 与状态写入要求见[格式契约](../schema.md)。

## 交付

说明比较的基线与目标、实际复核范围、候选项的处置和修改页面。报告检查及行为验证结果、仍待复核的范围，以及 `baseline.commit` 是否推进；局部更新明确说明保留旧基线。
