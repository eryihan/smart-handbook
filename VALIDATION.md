# V1 验证记录

日期：2026-10-02。

## 检查结果

| 项目 | 结果 | 范围 |
|---|---|---|
| 页面与状态格式 | 通过 | metadata、状态 schema、模板结构及关联 |
| Python 工具 | 46 个测试通过 | 临时 Java 文本、配置和 Git fixture |
| 文档 | 通过 | 最小 frontmatter、本地链接、模板实例化 |
| Claude Code | 本地安装与命令发现通过 | marketplace 注册、安装、核心 Skill 和六个命令 |
| Codex | 本地 marketplace 发现通过 | 列出插件；安装和任务执行未验证 |
| GitHub 分发 | 未验证 | 远端安装 |
| 真实项目任务 | 未验证 | 项目理解、开发、排障、维护 |

## Python 与文档

环境：Python 3.9.6。执行：

```sh
python3 -m unittest discover -s tests -v
```

46 个测试通过，覆盖：

- JSON、schema、ID、metadata 位置与数量、页面布局和固定章节。
- map / module / flow 关系、链接与 anchor、路径越界和 symlink。
- 来源修改、删除、改名、Java 简单 symbol 和不支持语法。
- 状态损坏、来源集合变化、复核时间与验证记录。
- Git / 基线缺失、脏工作区、暂存改名、指定目标、无效 ref、旧引用和删除页面关联。
- `.smart_handbook/` 读取、旧状态路径拒绝、知识文件变化排除及工具只读行为。

Python 编译、最小 frontmatter 和本地链接检查通过；模板链接在实例化后的 Handbook 中检查。通用 Skill 校验脚本因缺少 PyYAML 未执行。

## Claude Code

版本：2.1.283。两份 manifest 被原生 validator 接受，无 schema 或路径错误；插件名称触发 kebab-case 警告，Claude Code 接受 `smart_handbook`。

隔离配置中注册 `smart-handbook`，安装 `smart_handbook@smart-handbook` 返回 `outcome=ok`。`plugin details` 列出核心 Skill 和五个工作流，会话初始化事件发现全部五个 `smart_handbook:<command>`。

发现检查禁用工具、hooks 和 MCP，API 指向不可用的本地端口。该检查未运行模型任务，结果限于安装和命令发现。

五个 command 包装设置 `disable-model-invocation: true` 后，会话仍能发现全部 slash command。通过临时本地端点检查请求中的 Skill 列表，自动选择只包含 `smart_handbook:smart_handbook`，五个包装均未列入。端点返回错误结束检查，未执行模型推理。

2026-10-02 加入 help 后，隔离会话的初始化事件发现 help、init、work、update、audit、status 六个 slash command 和通用 Skill 入口。help 包装同样设置 `disable-model-invocation: true`。46 个 Python 测试和两份 manifest 校验再次通过。

## Codex

使用临时配置覆盖读取本地 marketplace：`plugin list --available --marketplace smart-handbook --json` 返回 `smart_handbook@smart-handbook`、版本 `0.1.0`，状态为未安装、未启用。结果限于插件发现。

## 待完成验收

优先验证 help、status 和局部 update。使用隔离目标项目，记录实际读取和执行的工具，比较执行前后的文件及 `.state.json`：help 只读取插件说明；status 只读取已有知识；局部 update 保留 `baseline.commit` 和未复核页面的指纹。检查实际调用和产物，不以回答中的承诺作为通过依据。

工作流回归使用以下请求：

| 场景 | 请求 | 预期结果 |
|---|---|---|
| 帮助，无 Handbook | `handbook help` 或无参数通用入口 | 展示命令、参数和示例，不扫描源码、不创建 `.smart_handbook/` |
| 普通任务，无 Handbook | “解释这个方法” | 完成解释，不创建 `.smart_handbook/` |
| 首次建立 | “为这个项目建立 Handbook” | 进入 init，建立导航，关联源码证据 |
| 状态查询 | `handbook status` | 只读已有知识和状态，不扫描源码或运行 check / impact |
| 局部更新 | “只更新审批模块的 Handbook” | 先分析候选和源码，仅更新相关页面，保留全库旧基线 |
| 改名或删除引用 | “根据这次改名更新 Handbook” | 通过旧来源关联定位候选，完成复核后替换指纹 |
| 维护分析 | “这个补偿任务能否重跑” | 给出对象、幂等条件和完成判据，不执行补偿 |

上述场景尚未完成 Agent 执行验收。

在真实大型 Java 项目的指定版本上建立全库导航、一个关键 module 和一条跨模块 flow，再用无项目上下文的新会话执行理解、开发、排障和维护任务。

记录定位错误、遗漏影响、错误结论、缺失知识、工具误报和工作流问题。工具 fixture 结果不覆盖业务语义、运行环境或外部系统行为。工具能力与限制见[格式契约](references/schema.md)。
