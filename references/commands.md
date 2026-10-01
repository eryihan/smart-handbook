# 命令与路由

Skill 提供帮助入口和五个工作命令，由 Agent 解读。Python CLI 另提供 `check`、`impact`，用于机械检查。

| 普通文本命令 | Claude Code 入口 | 任务示例 | 工作流 |
|---|---|---|---|
| `handbook help [command]` | `/smart_handbook:help [command]` | 查看全部用法或指定命令的帮助 | 本页 |
| `handbook init` | `/smart_handbook:init` | 为项目建立 Handbook；从代码重建知识 | [init](workflows/init.md) |
| `handbook work <task>` | `/smart_handbook:work <task>` | 解释审批流程；增加撤回；定位数据未生效；判断补偿能否重跑 | [work](workflows/work.md) |
| `handbook update` | `/smart_handbook:update` | 根据代码变化更新 Handbook | [update](workflows/update.md) |
| `handbook audit` | `/smart_handbook:audit` | 检查过期、覆盖与关键内容 | [audit](workflows/audit.md) |
| `handbook status` | `/smart_handbook:status` | 查看已记录状态 | [status](workflows/status.md) |

## 帮助与首次使用

`handbook help` 展示命令表、参数和以下使用顺序：

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

help 可带一个命令名；init 可带目标仓库或范围；work 需要任务描述；update 可指定基线、目标版本或范围；audit 可指定目标版本或范围；status 可指定目标仓库。省略可选参数时按当前仓库和已有状态处理。

`handbook help <command>` 只展示指定命令的用途、参数和示例，需要执行细节时读取其对应工作流。帮助只读取插件说明，不扫描项目或执行工具。回答时省略内部路由规则。

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
