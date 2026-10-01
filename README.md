# Smart Handbook

`smart_handbook` 为代码项目建立和维护 Handbook，用于理解项目、开发、排障和维护。项目知识保存在 `.smart_handbook/`，通过模块导航和源码引用定位任务上下文；具体行为以任务目标版本的实现为准。

## 安装

### Claude Code

```sh
claude plugin marketplace add eryihan/smart_handbook
claude plugin install smart_handbook@smart-handbook
```

### Codex

```sh
codex plugin marketplace add eryihan/smart_handbook
codex plugin add smart_handbook@smart-handbook
```

安装后，在目标项目中启动新会话。宿主内安装、本地开发和更新方式见 [Claude Code](references/claude-code.md) 与 [Codex](references/codex.md)。

## 命令

| 普通文本命令 | Claude Code slash command | 用途 |
|---|---|---|
| `handbook help [command]` | `/smart_handbook:help [command]` | 查看全部用法或指定命令的帮助 |
| `handbook init` | `/smart_handbook:init` | 建立或重建 Handbook |
| `handbook work <任务>` | `/smart_handbook:work <任务>` | 理解、开发、排障或维护 |
| `handbook update` | `/smart_handbook:update` | 根据代码变化复核并更新相关页面 |
| `handbook audit` | `/smart_handbook:audit` | 重新检查结构、来源、导航覆盖和关键内容 |
| `handbook status` | `/smart_handbook:status` | 查看已记录的覆盖、复核、验证和缺口 |

首次使用可执行 `handbook help`；查看单个命令的用法，例如 `handbook help update`。Claude Code 对应使用 `/smart_handbook:help` 和 `/smart_handbook:help update`。

项目已有 `.smart_handbook/` 时，也可直接描述任务，例如“审批结束了，但数据没有生效，帮我定位原因”。Skill 会进入对应工作流。参数和自然语言路由见[命令说明](references/commands.md)。

## 项目知识

```text
.smart_handbook/
├── README.md                 项目定位与任务导航
├── system.md                 系统边界、全局概念与依赖
├── map.md                    模块索引、源码范围与未归属入口
├── working-guide.md          阅读、核对和更新方法
├── modules/<module>.md       单模块行为与约束
├── flows/<flow>.md           跨模块交接与失败处理
└── .state.json               来源指纹、复核与验证记录
```

页面中的 claim 将关键结论关联到实现文件和可选 symbol。`.state.json` 保存文件指纹及复核记录；代码变化后，`update` 先定位候选页面，再读取实现并局部修改。

内容覆盖、来源变化、AI 复核和行为验证分别记录。`status` 只展示已有记录；`audit` 重新核对源码和覆盖范围。

页面模板见 [assets/handbook](assets/handbook/)，metadata 和状态字段见[格式契约](references/schema.md)。

## 检查工具

要求 Python 3.9+，无第三方依赖。从插件目录执行，`--root` 指向目标项目根目录：

```sh
python3 scripts/handbook.py check --root /path/to/project
python3 scripts/handbook.py impact --root /path/to/project --base <commit>
```

`check` 检查页面结构、引用和已记录来源的变化。`impact` 根据 diff 或历史指纹输出候选影响范围。两者均只读，语义复核和状态保存由 Agent 完成。参数、退出码及降级范围见[工具契约](references/schema.md#python-cli)。

## 开发

运行工具测试：

```sh
python3 -m unittest discover -s tests -v
```

已执行检查及待完成验收见[验证记录](VALIDATION.md)。
