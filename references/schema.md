# Handbook V1 格式与工具契约

- [页面与目录](#页面与目录)
- [页面 metadata](#页面-metadata)
- [证据与定位](#证据与定位)
- [状态文件](#状态文件)
- [保存复核结果](#保存复核结果)
- [Python CLI](#python-cli)
- [impact 的比较范围](#impact-的比较范围)

## 页面与目录

项目知识位于目标仓库根目录的 `.smart-handbook/`：

```text
.smart-handbook/
├── README.md
├── system.md
├── map.md
├── working-guide.md
├── modules/<module>.md
├── flows/<flow>.md
└── .state.json
```

四个根页面必需，module 和 flow 按项目需要建立。每页一个 H1、至少一个 H2，并包含一个 `handbook-meta` HTML 注释。注释放在 H1 之后、第一个 H2 之前；围栏代码块中的示例不计入，正文中的额外 metadata 会报错。

module 和 flow 使用[模板](../assets/handbook/)中的固定 H2 标题。claim 的 `section` 必须与所属 H2 完整标题一致。

## 页面 metadata

格式定义见 [metadata-schema.json](../assets/metadata-schema.json)。`schema_version` 必须为整数 `1`；JSON 重复 key、非 JSON 常量和未知字段均不接受。

| 字段 | 要求 |
|---|---|
| `id` | 小写字母、数字、连字符，匹配 `^[a-z0-9][a-z0-9-]*$`；页面 ID 全库唯一 |
| `kind` | `readme` / `system` / `map` / `working-guide` / `module` / `flow`，与页面位置一致 |
| `coverage` | `navigation-only` / `documented` / `known-gap`，由 Agent 根据已编写内容判断 |
| `claims` | 关键行为和约束的列表，可为空；普通说明无需逐句建 claim |
| `claim.id` | claim ID 全库唯一，格式同页面 ID；两类 ID 分别检查唯一性 |
| `claim.section` | 所属 H2 的完整标题 |
| `claim.sources` | 至少一个实现文件；必填 `path`，可选 `symbol` 和正整数 `line` |
| module 的 `source_ranges`、`config_ranges` | 管理的源码、SQL、配置文件或目录，不使用 glob |
| flow 的 `modules` | 参与模块的 metadata ID 列表 |
| map 的 `modules` | 每项包含 `id`、`page`、`source_ranges`、`config_ranges`、`keywords`；页面和范围与 module 一致 |
| map 的 `unowned_entries` | 未归属入口及原因的字符串列表 |

所有页面必填 `schema_version`、`id`、`kind`、`coverage`、`claims`。module、flow、map 还需填写表中对应字段。

`path`、range、map 的 `page` 和状态中的页面 key 使用仓库根目录相对的 POSIX 路径。禁止绝对路径、`..`、以 `./` 开头的路径、反斜杠、`.git` 和指向仓库外的 symlink。Markdown 内部链接相对当前页面，可通过 `../` 跳转到仓库内的文件。

以下示例应放入真实页面的 `handbook-meta` 注释，并替换为项目实际路径：

```json
{
  "schema_version": 1,
  "id": "module-approval",
  "kind": "module",
  "coverage": "documented",
  "source_ranges": ["src/main/java/example/approval"],
  "config_ranges": ["src/main/resources/application.yml"],
  "claims": [{
    "id": "approval-01",
    "section": "当前行为与关键约束",
    "sources": [{
      "path": "src/main/java/example/approval/ApprovalService.java",
      "symbol": "ApprovalService#approve(Request)"
    }]
  }]
}
```

## 证据与定位

Implementation Evidence 包括源码、SQL、配置、构建定义、测试、运行观察和部署信息。Context Evidence 包括 README、ADR、OpenSpec、Issue、PR、历史设计、复盘和注释，用于说明背景及历史适用范围。

claim 的 `sources` 保存可读取的实现文件。运行观察另在正文中记录环境、版本、时间、方法和结果，不将日志观察伪装为源码路径。测试文件存在只说明有测试定义，执行结果需另行记录。

V1 的 symbol 检查限于 Java 类型名和 `Type#method(SimpleType, int)`。它采用文本匹配，支持简单声明、参数类型、数组和重载，不解析 AST 或调用图。`line` 仅辅助跳转。

| 定位结果 | 含义 |
|---|---|
| `located` | 在支持的文本语法中找到类型或方法；行为仍需阅读代码 |
| `symbol-broken` | 类型缺失，或单类型文件中完全找不到方法名 |
| `symbol-unverified` | 复杂注解、泛型参数、varargs、多类型归属、构造器、其他语言或无法确认的签名；需读取源码核对 |

链接检查支持常见单行 inline link、image、reference link 和标题 anchor，忽略代码、注释中的链接。多行链接、复杂嵌套括号、HTML 链接、自定义 anchor 和复杂标题标记需人工核对；外部 URL 不联网检查。

## 状态文件

格式定义见 [state-schema.json](../assets/state-schema.json)。`.smart-handbook/.state.json` 保存可重建的机器记录，业务结论保留在 Markdown。

`schema_version` 和 `pages` 必填。`pages` 的 key 使用 `.smart-handbook/...md`；每项必填 `sources`，将仓库相对文件路径映射到原始字节的 `sha256:<64 lowercase hex>`。可选的 `baseline.commit` 作为默认 Git 比较基线。

以下示例表示尚未建立来源指纹：

```json
{
  "schema_version": 1,
  "pages": {
    ".smart-handbook/modules/approval.md": {
      "sources": {},
      "source_state": "baseline-unavailable",
      "review": {"status": "needs_review"},
      "verification": {
        "status": "not-run",
        "conditions": "尚未选择验证环境",
        "method": "未执行",
        "observed": "无运行观察"
      }
    }
  }
}
```

完成源码复核后，`sources` 应保存该页全部当前 claim 来源的真实摘要。

| 维度 | 取值 | 表达的事实 |
|---|---|---|
| 内容覆盖 | `navigation-only` / `documented` / `known-gap` | 已记录内容的深度或缺口，保存在 metadata |
| 来源状态 | `unchanged` / `changed` / `broken` / `unknown` / `baseline-unavailable` | 直接引用文件与历史记录的比较结果 |
| AI 复核 | `reviewed_by_ai` / `needs_review` | 是否对照目标源码分析过；已复核时必填带时区的 `reviewed_at` |
| 行为验证 | `verified` / `failed` / `not-run` / `unavailable` | 指定条件下的验证记录；必填非空的 `conditions`、`method`、`observed` |

可选 `source_checked_at` 保存实际来源检查时间，必须带时区。status 展示已保存状态和时间，缺少来源状态时使用 `unknown`。

check 派生来源状态的优先级为 `broken`、`changed`、`baseline-unavailable`、`unknown`、`unchanged`。摘要或来源集合变化，包括移除引用，会使页面需要复核；缺少来源或存在无法确认的 symbol 时也不能标为无需复核。没有当前 claim 来源、也没有移除引用记录的页面派生为 `unknown`。

check 的 `recorded_verification` 保留历史观察。来源文件未变不能证明间接依赖、部署环境或当前运行行为未变；四个状态维度分别表达，不汇总为可信度分数。

## 保存复核结果

`check` 和 `impact` 均只读，没有 record、baseline 或 fingerprint 子命令。Agent 在实际复核后更新状态：

1. 保留旧指纹和关联，先完成候选分析与源码复核。状态损坏时保留 Markdown 和原状态，修复或按已确认来源重建。
2. 收集已复核页面全部当前 claim 来源，计算原始字节 SHA-256，或采用刚执行的 check JSON 中的真实 `fingerprint`。
3. 保存该页 `sources`、实际 `source_state` 和 `source_checked_at`。确实对照目标源码分析后，才写入 `reviewed_by_ai` 与实际 `reviewed_at`。
4. 记录验证条件、方法和观察。未执行填 `not-run`，无法执行填 `unavailable`；旧结果保留原条件和版本范围。
5. 未复核页面保留原记录。保存 JSON 时避免截断，不能把 check 的全部新摘要直接写成复核基线。
6. 从旧基线到目标版本的全部变更完成归属和处置后，才推进 `baseline.commit`。局部复核保留旧 commit。

指纹不覆盖未引用文件和间接依赖，这些范围由 Agent 在更新和审计时补查。

## Python CLI

要求 Python 3.9+，仅使用标准库。`--root` 指向目标项目根目录，脚本可从任意目录调用：

```sh
python3 <skill-directory>/scripts/handbook.py check --root .
python3 <skill-directory>/scripts/handbook.py check --root . --format json
python3 <skill-directory>/scripts/handbook.py impact --root . --base <commit> --target worktree
python3 <skill-directory>/scripts/handbook.py impact --root . --base <commit> --target <commit>
```

输出默认 text，可选 json。退出码 `0` 表示无机械错误，仍可能有 warning；`1` 表示机械错误；`2` 表示参数错误。业务语义、导航覆盖和行为验证需另行判断。

check 检查 JSON 与 schema、布局、固定章节、ID、记录关系、链接、来源文件、支持的 symbol、状态格式和指纹。

impact 输出 `changed_files`、`renames`、`direct_claims`、`previous_pages`、`related_modules`、`related_flows`、`unowned_changes`。它按 claim 来源、module 范围和 flow 参与关系生成候选，公共组件和未归属变化需 Agent 判断间接影响。

## impact 的比较范围

| 条件 | 比较方式与限制 |
|---|---|
| Git 可用，有 `--base` 或 `baseline.commit` | 用该基线比较目标；默认 `worktree`，包含 tracked 暂存与未暂存变化、非忽略 untracked 文件 |
| 指定目标 commit | 比较两个版本，不包含脏工作区和 untracked 文件 |
| 无 Git，或未提供 commit 基线 | 比较已有来源指纹；只能识别记录文件的修改或删除 |
| 缺少旧指纹 | `baseline-unavailable`；无法得出无变化的结论 |
| 显式 ref 无效，或缺少执行 ref 比较的条件 | 报错，不静默降级 |

Git 根目录必须等于 `--root`。关联 metadata 始终读取当前 worktree 的 Handbook；比较历史目标时需先确认这些关联适用。

改名保留旧、新路径，删除 claim 或页面后仍可通过旧状态的 `previous_pages` 找到候选。`.smart-handbook/` 自身的修改不列入实现变更。

指纹降级无法发现新增文件、未引用文件、完整改名关系和间接依赖变化。工具不生成全库入口清单或自动依赖图。

Python 不可用或版本不足时，手工完成当前工作流所需检查并记录 `automated check unavailable`；源码分析和知识维护可继续。
