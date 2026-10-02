# 清单与进度

init 的全量发现与续跑、update 的新增归属与间接影响、audit 的覆盖检查使用本页。清单由 Agent 根据目标项目建立；工具辅助搜索、枚举、计算指纹和检查引用，不决定业务边界。

发现方法供三个流程共用；建立、保存与更新清单仅由 init / update 执行。audit 将新发现和状态冲突写入本次报告，保留目标仓库原记录。

## 发现与归属

确认版本和范围，查看构建、目录、配置及业务资料，再选择适合项目的搜索方法。不把某种注解、命名或目录规则作为唯一发现依据。

范围内每个源码与配置文件都有记录。业务实现归属具体业务；公共组件可归属多条业务。测试、生成代码、工具与排除项说明角色或理由。行为不明的代码保留待分析，不能仅因搜索不到调用方就认定无用。

执行入口逐项记录，包括请求、消息、事件、回调、任务等实际存在的形式。动态注册或配置分支继续核对，无法确定的入口保留缺口。业务按用户动作、规则和数据归属划分，名称和粒度由 Agent 判断。

反向检查未归属文件、没有业务说明的入口、没有接收方的交接、涉及但未读的 SQL / 配置。分析中新发现的内容及时补入清单，不把首次搜索结果当作固定边界。

## 保存结构

清单写入 `.smart-handbook/.inventory.json`，起始结构见[模板](../assets/inventory-template.json)。它是必需产物，格式见[清单 schema](../assets/inventory-schema.json)。结构固定最小记录，业务分类由 Agent 决定。

| 字段 | 内容 |
|---|---|
| `schema_version` | 清单格式版本，当前为 1 |
| `mode` / `status` | full 或用户明确选择的 navigation；in-progress / incomplete / complete，表达内容进度 |
| `target` | commit（无 Git 时为 null）、工作区说明、带时区的记录时间 |
| `scope` | include 的目录/文件、exclude 的路径及理由；`.` 表示全库发现范围 |
| `discovery` | 实际检查范围、发现方法和未确认范围 |
| `files` | 文件路径、指纹、角色、业务归属，以及待归属或排除理由 |
| `units` | 业务 ID、名称、入口、页面、支撑文件、依赖业务、进度、缺口和验收记录 |

files 每项包含 `path`、`fingerprint`、`role`、`units`、`disposition`、`reason`。disposition 为 pending / assigned / excluded；assigned 至少归属一条业务，其他项写明理由。role 使用项目实际含义，不固定类型。fingerprint 保存实际 SHA-256；无法取得时为 null 并说明。

units 每项包含 `id`、`name`、`entrypoints`、`pages`、`sources`、`depends_on`、`status`、`gaps`、`review`。入口包含 path、可选 symbol 和说明触发方式的 trigger，不强制 HTTP 路由。depends_on 保存影响本业务的其他业务或公共单元 ID，由 Agent 根据实现确认。

业务状态为 pending / analysing / needs-review / accepted / known-gap。review 分别保存 source、reading 两项，各含 `status`（pending / passed / failed / unavailable）、`reviewed_at`、`scope`、`result`。日期带时区，未知为 null。gaps 记录尚未解决的关键内容缺口，外部环境未知另用说明字段。accepted 要求两项均 passed，且 gaps 为空；公共组件说明应覆盖其已发现使用方。

来源、入口、页面使用仓库相对路径；scope 的 `.` 不能当 claim 来源。不记录仓库外路径、凭据和敏感数据。归属与依赖 ID 必须存在；清单不重复抄写业务规则。Agent 可增加项目需要的说明字段，不为填字段虚构入口或依赖。

## 分批、续跑与目标变化

按业务分批，顺序按依赖、风险和规模调整。每批保存页面、实际来源指纹、进度、缺口和下一步。上下文切换或中断不改变全量目标。

再次 init 时未完成清单默认续跑；明确要求重建才重建。已完成时说明版本和范围，代码变化进入 update。缺少清单的产物不符合当前格式，需要重新 init；不设置旧格式兼容分支。

复核后确认实际文件版本再保存指纹。续跑核对目标与已分析来源，变化项及其使用方回到待复核。收尾重新枚举范围、核对新增/删除和指纹，处理分析期间变化，避免混合版本。

## 完成条件

full 模式满足以下条件才能保存 complete：

- 范围内文件都有归属或明确排除理由，没有未处理的发现范围。
- 所有纳入范围的入口都有业务说明，没有待归属文件或未分析业务。
- 各业务完成源码复核和独立阅读验收，没有关键本地链路缺口。
- 页面引用、归属、依赖、README 摘要与实际目标版本一致。

外部与运行未知项单列；使核心问题无法回答的未知项不能验收通过。其他环境未知不冒充运行验证，也不要求初始化自行执行生产操作。

navigation 的 complete 仅表示声明的导航任务结束，必须注明未深入分析。无法独立验收或仍有关键缺口时保存 incomplete，列出未完成项与恢复条件，不能报告全量完成。

Python check 校验清单格式、已记录引用与完成状态，比较已记录文件指纹；impact 沿 Agent 记录的归属与依赖给出候选。工具不枚举源码、不划分业务、不验证验收记录的真实性。Agent 仍需发现遗漏、核对影响和完成内容验收。
