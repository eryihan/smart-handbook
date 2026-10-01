# 工作指南

<!-- handbook-meta
{
  "schema_version": 1,
  "id": "handbook-working-guide",
  "kind": "working-guide",
  "coverage": "documented",
  "claims": []
}
-->

## 从任务找到页面

项目知识位于仓库根目录的 `.smart_handbook/`。从 [README](./README.md) 的业务词、症状、入口或编号进入 [map](./map.md)，读取直接相关的 module / flow。缺少页面时直接阅读代码并记录知识缺口。

安装 smart_handbook 后，可使用普通文本 `handbook init`、`handbook work <任务>`、`handbook update`、`handbook audit`、`handbook status`。Claude Code plugin 提供对应的 `/smart_handbook:<command>`。

## 核对目标版本与来源

确认仓库、branch / commit / worktree 和未提交修改。按任务目标版本读取源码、配置、SQL 与构建定义。README、Issue、PR、ADR、历史设计和注释用于了解背景，当前行为需实现证据。

线上行为与本地源码不符时，核对部署版本、运行配置、数据、Feature Flag、外部依赖和消息状态。无法确认时限定结论范围。

## 从 Handbook 回到代码

按 claim 的仓库相对 path 和可选 symbol 读取实现；line 用于辅助跳转。页面与目标版本实现冲突时，修正相关内容。

分别记录引用有效、文件未变、AI 复核、测试执行、行为验证和运行时确认。测试存在不能替代执行记录，文件未变不能排除间接依赖变化。

## 检查与处理失效

已安装 Skill 且 Python 3.9+ 可用时，在项目根目录执行：

```sh
python3 <skill-directory>/scripts/handbook.py check --root .
```

check 只读。引用失效时重新定位，区分改名和行为变化；状态损坏时保留业务 Markdown 和原状态，再修复或重建。

未安装 Skill 时，按页面引用手工核对相关代码和链接。Python 不可用时记录 automated check unavailable；Git 不可用时比较已有来源指纹；缺少历史指纹时记录 baseline unavailable，并说明增量检查范围。

## 开发、排障与增量更新

开发前确认现有行为、目标行为、修改位置、影响范围和验证判据。代码变化后复核相关 claim、module 与 flow，再保存新指纹和 AI review。局部复核保留原全库 commit 基线。

排障保留多个候选原因，分别寻找支持证据和反证。缺少日志不能证明步骤未执行，Mock 结果不能证明外部系统实际行为。

维护前明确对象、范围、副作用、幂等性、重跑条件及完成判据。影响边界无法确定时继续分析，暂不执行；执行后核对最终状态。

## 状态查询与权限

status 只展示已有记录，注明上次检查时间和适用条件。audit 重新检查来源、覆盖及关键内容，报告实际检查范围。

按用户授权和宿主权限执行。工作指南不增加生产访问、数据库写入、消息重发、部署、Git 提交、依赖安装或协作规则修改权限。用户只要求解释或方案时，按该范围交付。
