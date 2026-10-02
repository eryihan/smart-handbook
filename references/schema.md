# Handbook V2 格式与工具契约

- [页面与目录](#页面与目录)
- [页面 metadata](#页面-metadata)
- [证据与定位](#证据与定位)
- [状态文件](#状态文件)
- [验收记录](#验收记录)
- [保存复核结果](#保存复核结果)
- [Python CLI](#python-cli)
- [impact 的比较范围](#impact-的比较范围)

## 页面与目录

项目知识位于目标仓库根目录：

```text
.smart-handbook/
├── README.md
├── system.md
├── map.md
├── working-guide.md
├── modules/<module>.md
├── flows/<flow>.md
├── .inventory.json
├── .state.json
└── .reviews/<business>.json
```

四个根页面必需，module / flow 按业务需要建立。每页一个 H1、至少一个 H2，在 H1 之后、第一个 H2 之前放一个 handbook-meta HTML 注释。代码块中的示例不计入；额外 metadata、重复 JSON key 与非 JSON 常量均报错。

module / flow 使用[模板](../assets/handbook/)的固定 H2，claim.section 与所属 H2 完整标题一致。当前页面、状态、清单与验收记录均为 schema_version 2；旧产物重新 init，不自动兼容或迁移。

清单保存发现、入口进度与验收关联，格式见[清单与进度](project-inventory.md)及[清单 schema](../assets/inventory-schema.json)。脚本不发现代码或划分业务。

## 页面 metadata

格式见[metadata-schema.json](../assets/metadata-schema.json)，未知字段不接受。

| 字段 | 要求 |
|---|---|
| id | 全库唯一的小写字母、数字、连字符，匹配 `^[a-z0-9][a-z0-9-]*$` |
| kind | readme / system / map / working-guide / module / flow，与路径一致 |
| coverage | navigation-only / documented / known-gap，表达页面声明范围，不代表全模块或运行验证 |
| claims | 关键结论，可为空；普通说明无需逐句建 claim |
| claim.id / section | claim ID 全库唯一，与页面 ID 分别检查；section 为实际 H2 |
| claim.resource_types | 当前结论涉及的 database / redis / mq / es / rpc / http / async / other，可为空 |
| claim.sources | 至少一个来源，必填 path、roles，可选 symbol、正整数 line |
| module.source_ranges / config_ranges | 相关源码、映射及配置的文件或目录，不使用 glob |
| flow.modules | 参与模块的 metadata ID |
| map.modules | id、page、source_ranges、config_ranges、keywords，与 module 一致 |
| map.unowned_entries | 未归属入口及原因的字符串列表 |

所有页面必填 schema_version、id、kind、coverage、claims。module / flow 的 documented 需要按[内容标准](endpoint-analysis.md)写清声明入口；关键本地链路未查清用 known-gap，纯导航用 navigation-only。全量完成由清单入口和有效验收记录汇总。

示例只展示一个结论，实际按业务填写：

```json
{
  "schema_version": 2,
  "id": "module-approval",
  "kind": "module",
  "coverage": "documented",
  "source_ranges": ["src/approval"],
  "config_ranges": [],
  "claims": [{
    "id": "approval-save",
    "section": "当前行为与关键约束",
    "resource_types": ["database"],
    "sources": [
      {"path": "src/approval/ApprovalService.java", "symbol": "ApprovalService#save(Request)", "roles": ["implementation"]},
      {"path": "src/approval/ApprovalMapper.xml", "line": 12, "roles": ["persistence"]}
    ]
  }]
}
```

path、range、map.page 与机器记录使用仓库相对 POSIX 路径。禁止绝对路径、`..`、`./` 前缀、反斜杠、`.git` 和指向仓库外的 symlink。scope.include 的 `.` 只表示发现范围。Markdown 链接允许在仓库内通过 `../` 跳转。

## 证据与定位

来源角色为 implementation / persistence / configuration / handoff / definition。database 结论需要实现与持久化映射；Redis、MQ、ES、RPC、HTTP 需要使用实现与决定行为的配置；async 需要实现与交接证据。本仓库有接收方时 handoff 引用接收实现；接收方在仓库外时引用可见的客户端或协议交接边界，远端内部与最终结果未知须明确，不能用外部边界跳过本地消费或回写。一文件可有多个角色，例如注解 SQL 或代码常量，按实际内容标记。脚本核对已声明角色是否齐全，不判断内容是否真实支持结论。

来源内容和指纹要求见[证据与来源指纹](endpoint-analysis.md#证据与来源指纹)。业务资料、历史方案和注释用于背景；当前行为需要实际实现。测试存在不代表已执行，运行观察另记环境、版本、时间、方法和结果，不伪装成源码路径。

symbol 定位为保守 Java 文本检查，支持类型名和简单 `Type#method(SimpleType, int)`，不解析 AST / 调用图。复杂泛型、注解、varargs、多类型文件和其他语言返回 symbol-unverified，交由 Agent 核对；明确缺类型或方法报 symbol-broken。已验收入口与场景定位在指纹未变时核对明显缺失的方法及越界行号；源码已变时旧定位进入待复核，不能用当前文件否定历史位置。

链接检查支持常见单行 inline、image、reference link 与标题 anchor，忽略代码和注释。多行、复杂嵌套、HTML、自定义 anchor 等需人工核对，外部 URL 不联网检查。

## 状态文件

[state-schema.json](../assets/state-schema.json) 定义 `.state.json`。必填 schema_version、pages；可选 baseline.commit 保存默认 Git 比较基线。

pages 的 key 为 `.smart-handbook/...md`，每项 sources 将该页全部 claim 来源映射为实际 `sha256:<64 lowercase hex>`。可选 source_state、source_checked_at 描述当时来源核对，可选 verification 保存运行验证；不保存独立的 review 状态。

| 维度 | 表达的事实 |
|---|---|
| 页面覆盖 | metadata.coverage 表达实际声明范围 |
| 来源状态 | check 根据来源集合和指纹派生 broken / changed / baseline-unavailable / unknown / unchanged |
| 内容复核 | check 根据入口及验收记录派生 reviewed_by_ai / needs_review，不手填页面 review |
| 运行验证 | verification.status 为 verified / failed / not-run / unavailable，必填非空 conditions、method、observed |

缺少来源或历史摘要不能声称 unchanged。来源删除、指纹变化或引用集合减少需要复核。没有 claim 来源的页面为 unknown。symbol 的定位限制与业务复核分别表达。

source_checked_at 使用工具取得的实际时间并带时区。历史运行观察保留原版本和条件；指纹未变不能证明间接依赖、部署环境或当前运行行为未变。

## 验收记录

[review-schema.json](../assets/review-schema.json) 定义 `.reviews/*.json`，起始结构见[模板](../assets/review-template.json)。清单入口通过 reviews 引用当前记录；未引用的历史文件不能证明当前验收。源码答案只给评分者，阅读者不读取这些附件。

| 字段 | 内容 |
|---|---|
| id / target | 验收 ID、实际 commit 和工作区说明 |
| sources / pages | 来源与 Markdown 页面分别保存实际 SHA-256，不用 commit 相同代替指纹 |
| source_reviewed_at / reader | 实际源码复核时间；隔离条件 independent / unavailable 及说明 |
| scenarios | id、entrypoints、topics、question、expected、reading、verdict、assessment、reviewed_at |
| not_applicable | 按入口 ID、检查方面保存 reason 与 sources |

检查方面为 normal / rejection / effective-time / partial-failure / repeat / async。由实际场景覆盖或提供源码支持的不适用理由，不固定题数；正常路径不能标不适用。

expected 包含 answer 和 sources（path，可选 symbol / line）。reading 包含 status（pending / answered / unavailable）、answer、evidence（page + 实际 H2 section）、locations（源码 path + symbol 或 line）。verdict 为 pending / passed / failed，已判定时填写具体 assessment 与实际 reviewed_at。

源码答案引用该入口的实现，来源必须存在于 snapshots 与清单。阅读依据引用已保存指纹的页面。场景关联的每个入口反向引用该记录，避免用其他业务的报告充当验收；accepted 入口的处理路径、claim 来源和关联页面都需被指纹覆盖。

保存全部关联题，不能删去失败题或用其他通过题替代。修订后对同一题实际复验，更新阅读答案、判定与时间，在 assessment 保留原失败及修复说明；复验完成前仍为 failed / pending。源码复核时间不晚于评分时间；所有时间带时区且不得在未来。工具可用时用 `datetime.now(timezone.utc).isoformat()` 或宿主时钟取得实际时间，未知为 null。

脚本核对范围、引用、隔离声明、答案字段、逐题结果、检查方面及快照，不判定答案真假。语义、隔离真实性和未发现分支仍由 Agent / 人工负责。变更及复验规则见[阅读验收](reading-review.md#变更后的有效性)。

## 保存复核结果

check / impact 均只读，没有写记录或推进基线的子命令。以下保存仅由 init / update 执行，audit 在答复交付结果：

1. 保留旧指纹和关联，先分析候选，复核源码与手册差异。状态损坏时保留知识，只按实际核对来源修复。
2. 写清业务和 claim，计算对应来源与页面原始字节 SHA-256；验收快照应为阅读者实际读取的版本。
3. 保存实际场景、阅读答案和逐题判定；失败题修订后独立复验，检查快照与时间。入口达到条件后才 accepted。
4. 保存已复核页面 sources、source_state、source_checked_at。运行未执行为 not-run、无法执行为 unavailable，保留历史结果的条件。
5. 未复核入口与记录保持原状，不将 check 的全部新摘要批量写成复核基线。核对清单派生进度后同步 README。
6. 只有旧基线到目标的全部变更完成归属、处置与验收，才推进 baseline.commit。局部修订保留旧基线。

页面指纹覆盖 claim 来源，清单指纹覆盖已登记文件，验收指纹绑定实际题目与阅读版本。遗漏文件和依赖仍需 Agent 补查。

## Python CLI

要求 Python 3.9+，仅用标准库，从安装目录运行：

```sh
python3 <skill-directory>/scripts/handbook.py check --root <project-directory> --format json
python3 <skill-directory>/scripts/handbook.py impact --root <project-directory> --base <commit> --target worktree --format json
```

check 返回页面状态及 inventory 的 recorded_status、派生 status、ready_to_complete、entries、units、changed_files、unknown_files、related_units。单元状态从入口、缺口和证据派生。缺资源角色、验收不完整、错误关联或完成记录冲突报 error，快照变化报待复核。

impact 返回 changed_files、renames、direct_claims、previous_pages、related_modules、related_flows、related_units、related_entries、review_candidates、unowned_changes。根据 claim、范围、流程和清单依赖给候选；review_candidates 包含旧验收失效的入口，即使业务代码零 diff。

退出码 0 只表示无机械错误，仍可能有 warning 或未完成入口；1 为机械错误，2 为参数错误。标题、非空 claims、指纹一致、答案字段齐全和退出成功都不证明业务语义正确。

## impact 的比较范围

Git 可用且有显式 base 或 baseline.commit 时比较该基线；默认 worktree 包含暂存、未暂存和非忽略 untracked 文件。指定目标 commit 时排除工作区变化，显式 ref 无效则报错，不静默降级。Git 根目录必须等于 root，metadata 始终取当前 worktree，比较历史目标前确认关联适用。

无 Git 或无 commit 基线时比较状态与清单历史指纹，只能发现已记录文件修改/删除，无法发现未登记文件、完整改名关系或遗漏依赖。缺旧摘要为 baseline-unavailable。改名保留旧新路径；删除页面或 claim 后仍利用旧 state 定位候选。

手册自身改动不列入业务源码 changed_files；验收的页面快照变化单独给出 review_candidates。候选仍由 Agent 核对实际影响，代码未变不免除已发现手册问题的修订。

Python 不可用时手工检查并记录 automated check unavailable；Git 不可用时说明指纹降级边界。源码分析和知识维护可以继续。
