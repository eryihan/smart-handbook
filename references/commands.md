# 命令与路由

以下命令输入到 Agent 会话中，由 Skill 解读。方括号表示可选输入，尖括号表示必填输入，不需要输入括号。命令后的任务、版本和范围用自然语言描述；Python CLI 的 `--base`、`--target` 等选项用于脚本调用。

- [命令一览](#命令一览)
- [首次使用](#首次使用)
- [各命令用法](#各命令用法)
- [帮助输出](#帮助输出)
- [参数解析](#参数解析)
- [自然语言与歧义](#自然语言与歧义)

## 命令一览

| 普通文本命令 | Claude Code 入口 | 任务示例 | 工作流 |
|---|---|---|---|
| `handbook help [command]` | `/smart_handbook:help [command]` | 查看全部用法或指定命令的帮助 | 本页 |
| `handbook init` | `/smart_handbook:init` | 为项目建立 Handbook；从代码重建知识 | [init](workflows/init.md) |
| `handbook work <task>` | `/smart_handbook:work <task>` | 解释审批流程；增加撤回；定位数据未生效；判断补偿能否重跑 | [work](workflows/work.md) |
| `handbook update` | `/smart_handbook:update` | 根据代码变化更新 Handbook | [update](workflows/update.md) |
| `handbook audit` | `/smart_handbook:audit` | 检查过期、覆盖与关键内容 | [audit](workflows/audit.md) |
| `handbook status` | `/smart_handbook:status` | 查看已记录状态 | [status](workflows/status.md) |

## 首次使用

1. 项目没有 Handbook 时，执行 `handbook init` 建立导航。
2. 执行 `handbook work <任务>`，或在已有 Handbook 的项目中直接描述任务。
3. 代码变化后执行 `handbook update`；需要重新检查覆盖和关键内容时执行 `handbook audit`。
4. 查看已记录状态使用 `handbook status`。

示例：

```text
handbook help
handbook help update
handbook init
handbook work 审批结束但数据未生效，帮我定位原因
handbook update 只复核审批模块，比较当前 worktree 与已有基线
handbook audit 检查审批流程及补偿逻辑
handbook status
```

## 各命令用法

### help

`handbook help [command]` 查看用法。可指定 help、init、work、update、audit、status 中的一个命令；省略时展示命令一览、首次使用顺序和示例。无效命令显示有效命令列表。

只读取插件说明，不扫描项目，不运行脚本或测试，不写入文件。示例：`handbook help update`。

### init

`handbook init [目标仓库、版本或范围]` 建立 Handbook；重建已有知识需要明确说明。省略参数时，以当前项目的 worktree 为目标，包含未提交修改。

读取范围内的实现，写入 `.smart_handbook/` 的页面和状态。首次建立先完成导航及关键模块，跨模块流程按实际需要编写。结果说明生成页面、已深入阅读的范围、未检查范围和验证结果。

示例：`handbook init 先建立全库导航，再深入审批模块`。详细流程见 [init](workflows/init.md)。

### work

`handbook work <任务>` 用于理解、开发、排障或维护。可在任务中指定仓库、目标版本和范围；省略这些信息时使用当前项目的 worktree。缺少任务描述时只展示用法和任务示例，等待任务描述。

解释和方案按请求范围交付；实施按用户授权修改代码或执行操作。已有 Handbook 时，按任务需要更新已确认且可复用的知识。无 Handbook 时直接处理任务，不自动初始化。

示例：`handbook work 解释审批失败后的重试条件，并给出源码位置`。详细流程见 [work](workflows/work.md)。

### update

`handbook update [基线、目标版本或范围]` 根据代码变化复核知识。省略参数且 Git 可用时，使用 `.state.json` 的 `baseline.commit` 与当前 worktree 比较；没有 commit 基线或 Git 不可用时比较已有来源指纹，记录无法覆盖的范围。显式指定的 ref 无效或无法比较时报告错误，不静默降级；缺少历史指纹时不能判断无变化。

读取 diff 和相关实现，写入受影响页面及其状态。局部更新保留全库旧基线；全部变更完成归属和处置后才可推进。结果说明比较版本、候选处置、修改页面、未完成项及基线是否推进。

示例：`handbook update 以 abc1234 为基线，只复核审批模块，目标为当前 worktree`。将示例 commit 替换为实际 commit。无 Handbook 时报告尚未建立，不自动初始化。详细流程见 [update](workflows/update.md)。

### audit

`handbook audit [目标版本或范围]` 重新检查结构、引用、导航覆盖和关键内容。省略参数时检查当前项目的 Handbook，并对照当前 worktree；指定范围时报告该范围内的结果。

运行机械检查并阅读相关源码，按实际复核结果修正页面和状态。结果说明错误、来源变化、覆盖缺口、实际复核页面和验证限制。无 Handbook 时报告尚未建立，不自动初始化。

示例：`handbook audit 检查审批流程及补偿逻辑`。详细流程见 [audit](workflows/audit.md)。

### status

`handbook status [目标仓库]` 查看已有记录。省略参数时读取当前项目的 `.smart_handbook/`。

只读取已有页面和状态，不扫描源码，不计算指纹，不运行脚本或测试，不写入文件。结果列出内容覆盖、来源状态、复核和行为验证的记录及时间；未知项显示 unknown。无 Handbook 时报告尚未建立；状态不可用时报告原因，不自动修复。

示例：`handbook status`。详细流程见 [status](workflows/status.md)。

## 帮助输出

无参数 help 展示命令表、首次使用顺序、一个 work 示例和查看单个命令帮助的方法，注明命令输入到 Agent 会话中。`handbook help <command>` 只展示该命令的用途、输入、默认行为、读取与写入范围、结果和示例；优先使用本页内容。用户询问执行细节时再读取对应工作流。

回答省略内部路由规则。展示帮助后结束，不运行示例，也不继续执行 init、audit 或其他任务。

## 参数解析

专用命令固定路由，命令后的文本作为参数。通用 Claude Code 入口 `/smart_handbook:smart_handbook <command> <task>` 将首个词与 help、init、work、update、audit、status 精确匹配；匹配时路由，余下文本作为参数，否则将全部文本作为 work 任务。

`handbook` 和通用入口无参数时进入 help。work 缺少任务时展示该命令的用法和任务示例，等待任务描述。明显的命令拼写错误显示有效命令，避免被当作开发任务。

## 自然语言与歧义

自然语言按任务意图路由，模糊请求默认 work，内部识别 understand、development、debugging、maintenance。

项目没有 `.smart_handbook/` 时，普通开发、排障或解释请求按原任务处理；建立和重建需要明确请求。

- “更新这个接口”进入 development；“更新 Handbook”进入 update。
- “这个模块有没有过期”先局部核对；全库过期和覆盖检查进入 audit。
- “这个任务能否重跑”进入 maintenance 分析；是否执行取决于用户授权。

仓库、目标版本或任务范围缺失且会影响结果时，补充必要信息；可独立进行的源码定位继续完成。用户只要求解释或方案时，保持该范围。

安装入口见 [Claude Code](claude-code.md) 与 [Codex](codex.md)。知识目录固定为目标项目根目录的 `.smart_handbook/`，CLI 参数见[格式契约](schema.md)。
