# 命令与路由

命令输入到 Agent 会话中，由 Skill 解读；命令后的仓库、版本、范围和问题用自然语言描述。以下命令仅面向业务手册。

## 命令一览

| 普通文本命令 | Claude Code 入口 | 职责 | 目标仓库写入 |
|---|---|---|---|
| `handbook help [command]` | `/smart-handbook:help [command]` | 查看用法 | 无；只读插件说明 |
| `handbook init` | `/smart-handbook:init` | 首次建立、续跑或明确重建手册 | .smart-handbook/ |
| `handbook update` | `/smart-handbook:update` | 根据代码变化或手册问题更新内容 | .smart-handbook/ |
| `handbook audit` | `/smart-handbook:audit` | 对照源码检查手册并报告问题 | 无 |

## 各命令用法

### help

`handbook help [command]`。可指定上表中的命令；省略时展示命令一览、首次使用顺序和示例。无效命令显示有效列表。帮助不扫描项目、不执行示例。

### init

`handbook init [目标仓库、版本或范围]`。默认全量分析当前项目 worktree，包含未提交修改。已有产物先只读检查，核对目标、入口进度与验收证据，再复用有效结果或续跑未完成项；不能只看 complete 标记。必需记录缺失或格式无效时重新发现与建立。导航、局部范围或主动重建有效产物需明确指定。已有完整手册的日常修订使用 update。

示例：`handbook init`；`handbook init 只梳理审批业务`。执行流程见 [init](workflows/init.md)。

### update

`handbook update [基线、目标版本、范围或待修复问题]`。输入可以是代码变化，也可以是 audit 报告或已明确的手册错误；代码未变时仍能修复知识遗漏。

默认以已有基线与当前 worktree 比较；缺少 Git / commit 时使用已有指纹，比较条件与限制见[工具契约](schema.md#impact-的比较范围)。局部更新保留全库旧基线。无手册不自动初始化，缺少清单时交由 init 重建。

示例：`handbook update 只更新审批模块`；`handbook update 修复刚才审计中遗漏的状态回写说明`。执行流程见 [update](workflows/update.md)。

### audit

`handbook audit [目标版本或范围]`。默认对照当前 worktree，检查现有手册全部范围的结构、来源、入口覆盖、验收记录与内容；也检查代码未变时原有的遗漏、错误和重复。可分批执行，报告实际检查与未检查范围，不能把抽查写成全量通过。

只读目标仓库，问题在答复中报告；不修改页面、清单、状态或基线，不自动执行 update。无手册报告尚未建立。

示例：`handbook audit 检查审批手册的失败和重试说明`。执行流程见 [audit](workflows/audit.md)。

## 帮助输出

首次使用顺序为 init → 阅读生成的手册；后续按需使用 update 或 audit。init / update 交付本次进度，后续查看已有记录直接读取项目 README 和清单。无参数 help 展示上表、此顺序、一个 init 和一个 update 示例。`help <command>` 只展示对应命令的用途、输入、默认行为、读写范围和示例。用户询问执行细节时再读对应工作流。

展示帮助后结束，不执行示例。安装与宿主入口见 [Claude Code](claude-code.md) 和 [Codex](codex.md)。

## 参数与自然语言路由

专用命令固定路由，后续文本作为参数。通用入口 `handbook` 或 `/smart-handbook:smart-handbook` 无参数时进入 help；首词与 help、init、update、audit 精确匹配时进入对应流程。

不匹配时仅识别明确的手册意图：“建立业务手册”进入 init，“更新手册 / 修复手册错误”进入 update，“检查手册质量”进入 audit。未知命令提示有效列表，不将任意文本当作研发任务。

模糊的“处理一下手册”需确认是只检查还是修改，确认前只读已有知识。普通功能开发、应用排障、业务解释或数据操作不触发本 Skill，即使项目已有 .smart-handbook/。
