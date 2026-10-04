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
2. 为当前项目建立知识：输入 `/smart-handbook:init` 或 `handbook init`。Agent 先建立清单，再连续处理业务批次：分析、编写、独立源码核对、固定版本阅读、保存，然后继续下一批。默认全量梳理存量业务；实际中断时保存原因和续跑位置，再次 init 继续。只做导航或局部范围时明确指定。
3. 从目标项目 `.smart-handbook/README.md` 找到业务手册，阅读规则、数据变化、生效与失败边界，再按引用定位代码。

后续代码变化或发现手册问题时使用 update 修订；audit 只检查并报告问题。已有手册时，init 先只读核对记录是否有效，再判断续跑或复用。进度从目标项目 README 的“覆盖状态与缺口”查看。

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
├── .inventory.json           Agent 的发现、业务归属和逐入口进度
├── .reviews/<业务ID>.json     源码场景、阅读答案及逐题验收证据
└── .state.json               来源指纹、比较基线和运行验证记录
```

页面中的 claim 将关键结论关联到实现、SQL、配置或异步交接代码，并标明资源类型和证据角色。入口进度引用实际验收记录，模块与全量进度从有效记录汇总；文件已归属或页面已创建不代表业务已分析。

代码或手册变化后，旧验收进入待复核，update 根据差异修订并复验。当前格式版本为 3；更早的 schema 不自动迁移。V3 的已有页面、指纹、基线和验收继续保留，新增字段缺失只进入对应核对范围，不触发全量重建。

升级 Skill 并让会话加载新版后，已有 V3 手册使用 `handbook update 核对新版要求，保留有效结果，只修复受影响业务`（Claude Code 对应 `/smart-handbook:update`）。先确认入口粒度与证据，再修订缺项、局部复验；无需删除 `.smart-handbook/`、反复安装或重新跑全量 init。后续仍按实际代码变化和内容问题使用 update。

业务内容与证据要求见[接口分析与内容验收](references/endpoint-analysis.md)，全量发现和进度见[清单标准](references/project-inventory.md)，独立读者能否理解业务由[阅读验收](references/reading-review.md)核对。

页面模板见 [assets/handbook](assets/handbook/)，metadata 和状态字段见[格式契约](references/schema.md)。

## 检查工具

要求 Python 3.9+，无第三方依赖。从插件目录执行，`--root` 指向目标项目根目录：

```sh
python3 scripts/handbook.py check --root /path/to/project
python3 scripts/handbook.py impact --root /path/to/project --base <commit>
```

`check` 检查结构、引用、证据角色、验收记录和指纹变化，派生当前进度。`impact` 根据 diff 或历史指纹输出受影响入口，也列出手册变化导致的待复验项。两者均只读；业务发现是否完整、答案是否正确仍由 Agent 对照源码和独立阅读核对。参数、退出码及降级范围见[工具契约](references/schema.md#python-cli)。

init / update 另用内部 `review.py` 建立待验记录、汇总计划问题、自动创建新验收目录和反馈模板，再绑定源码核对与实际评分。它保留历史、其他页面、运行观察和旧基线，不自动生成业务事实、评分或宣布完成。具体调用只供 Agent 执行，见[阅读验收](references/reading-review.md#内部记录工具)；公开命令仍为 help / init / update / audit。

## 开发

运行工具测试：

```sh
python3 -m unittest discover -s tests -v
```

已执行检查及待完成验收见[验证记录](VALIDATION.md)。
