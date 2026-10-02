# Smart Handbook

`smart-handbook` 从代码生成和维护业务手册，知识保存在 `.smart-handbook/`。手册帮助未参与项目的研发理解业务并定位代码；Skill 的职责限于手册生成、修订和质量检查。

## 安装

### Claude Code

```sh
claude plugin marketplace add eryihan/smart-handbook
claude plugin install smart-handbook@smart-handbook
```

### Codex

```sh
codex plugin marketplace add eryihan/smart-handbook
codex plugin add smart-handbook@smart-handbook
```

### 离线安装

从 [Releases](https://github.com/eryihan/smart-handbook/releases) 下载 `smart-handbook-<version>.zip`，解压后得到 `smart-handbook/`。将 `<plugin-directory>` 替换为该目录的绝对路径。

Claude Code：

```sh
claude plugin marketplace add <plugin-directory>
claude plugin install smart-handbook@smart-handbook
```

Codex：

```sh
codex plugin marketplace add <plugin-directory>
codex plugin add smart-handbook@smart-handbook
```

安装后，在目标项目中启动新会话。宿主内安装、本地开发和更新方式见 [Claude Code](references/claude-code.md) 与 [Codex](references/codex.md)。

## 首次使用

以下命令输入到 Agent 会话中。Claude Code 使用 slash command；Codex 使用普通文本命令，也可通过 `$smart-handbook help` 明确调用 Skill。

1. 查看用法：Claude Code 输入 `/smart-handbook:help`，Codex 输入 `handbook help`。
2. 为当前项目建立知识：输入 `/smart-handbook:init` 或 `handbook init`。Agent 先发现文件、入口和业务归属，再分批编写业务手册，完成源码复核与独立阅读验收。默认目标是约定范围内的全量存量业务，中断保存进度，再次 init 继续未完成项。只做导航或局部范围时明确指定。
3. 从目标项目 `.smart-handbook/README.md` 找到业务手册，阅读规则、数据变化、生效与失败边界，再按引用定位代码。

后续代码变化或发现手册问题时使用 update 修订；audit 只检查并报告问题。已有进度从目标项目 README 的“覆盖状态与缺口”查看，详细记录保存在清单与状态文件中。

## 命令

完整命令表、参数、职责和读写范围统一见[命令说明](references/commands.md)。查看单个命令帮助，例如 `handbook help update`，Claude Code 对应使用 `/smart-handbook:help update`。

## 项目知识

```text
.smart-handbook/
├── README.md                 项目定位与任务导航
├── system.md                 系统边界、全局概念与依赖
├── map.md                    模块索引、源码范围与未归属入口
├── working-guide.md          本项目手册的阅读与代码定位说明
├── modules/<module>.md       单模块行为与约束
├── flows/<flow>.md           跨模块交接与失败处理
├── .inventory.json           Agent 的发现、业务归属和分析进度
└── .state.json               来源指纹、复核与验证记录
```

页面中的 claim 将关键结论关联到实现文件和可选 symbol。`.state.json` 保存文件指纹及复核记录；代码变化后，`update` 先定位候选页面，再读取实现并局部修改。

业务内容与证据要求见[接口分析与内容验收](references/endpoint-analysis.md)，全量发现和进度见[清单标准](references/project-inventory.md)，独立读者能否理解业务由[阅读验收](references/reading-review.md)核对。

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
