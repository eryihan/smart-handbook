# 命令与路由

Skill 提供五个逻辑命令，由 Agent 解读。Python CLI 另提供 `check`、`impact`，用于机械检查。

| 普通文本命令 | Claude Code 入口 | 任务示例 | 工作流 |
|---|---|---|---|
| `handbook init` | `/smart_handbook:init` | 为项目建立 Handbook；从代码重建知识 | [init](workflows/init.md) |
| `handbook work <task>` | `/smart_handbook:work <task>` | 解释审批流程；增加撤回；定位数据未生效；判断补偿能否重跑 | [work](workflows/work.md) |
| `handbook update` | `/smart_handbook:update` | 根据代码变化更新 Handbook | [update](workflows/update.md) |
| `handbook audit` | `/smart_handbook:audit` | 检查过期、覆盖与关键内容 | [audit](workflows/audit.md) |
| `handbook status` | `/smart_handbook:status` | 查看已记录状态 | [status](workflows/status.md) |

## 参数解析

专用命令固定工作流，命令后的文本全部作为任务或范围。通用 Claude Code 入口 `/smart_handbook:smart_handbook <command> <task>` 将首个词与五个命令精确匹配；匹配时路由，余下文本作为参数，否则将全部文本作为 work 任务。

通用入口无参数时展示五种用法；work 缺少任务时要求补充。明显的命令拼写错误应提示有效命令，避免被当作开发任务。

## 自然语言与歧义

自然语言按任务意图路由，模糊请求默认 work，内部识别 understand、development、debugging、maintenance。

项目没有 `.smart_handbook/` 时，普通开发、排障或解释请求按原任务处理；建立和重建需要明确请求。

- “更新这个接口”进入 development；“更新 Handbook”进入 update。
- “这个模块有没有过期”先局部核对；全库过期和覆盖检查进入 audit。
- “这个任务能否重跑”进入 maintenance 分析；是否执行取决于用户授权。

仓库、目标版本或任务范围缺失且会影响结果时，补充必要信息；可独立进行的源码定位继续完成。用户只要求解释或方案时，保持该范围。

安装入口见 [Claude Code](claude-code.md) 与 [Codex](codex.md)。知识目录固定为目标项目根目录的 `.smart_handbook/`，CLI 参数见[格式契约](schema.md)。
