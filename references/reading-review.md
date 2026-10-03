# 阅读验收

init 验收各入口，update 复验受影响场景，audit 检查已有记录与所审业务。源码核对检验说明和答案是否正确，独立阅读检验手册能否让新人理解；两者分别完成，互不代替。

## 规划与源码核对

生成者读完本地链路，编写业务页及实际场景。逐入口覆盖正常路径、权限/状态拒绝、生效边界、部分失败、重复执行、异步交接六个方面；它们是角度，不规定题数。一题可覆盖多个方面，共用实现可联合验收，但须包含入口差异。不适用时提供源码支持的具体理由，正常路径不能排除。

先按具体动作判断六方面各自适用与否，再组合问题。场景的 topics 对其列出的每个入口都生效；适用方面不同的入口拆题，不能给查询入口套用写入链的异步或部分失败标签，也不能为消除冲突把不适用项改成已测试。是否不适用仍由实现决定，不能仅凭“查询”名称判断。

预期答案写清条件、实际资源、字段、状态、停止位置及实现证据。按实际分支出题，不能只从手册摘问题；尤其检查校验前副作用、远端成功后本地失败、异步体异常、消息交接和重复副作用。首次阅读前准备完整场景，不把缺失题目留到通过后补齐。

先检查格式及场景计划，再让未继承生成历史的源码复核者读取原始实现、SQL、实体和配置：先独立复述调用顺序及失败结果，再比对手册、答案和不适用理由。接口须查实际实现；本地跨模块继续追踪，关键框架／依赖行为遵循[沿实现追踪](endpoint-analysis.md#沿实现追踪)。逐项记录错误和依据，不能把已有答案当作标准答案背书。

委派时给出本批具体动作、待核对断言、入口与已发现的实现／SQL／配置位置、相关页面及输出文件。定位只帮助起步，复核者仍沿调用补查依赖；遇到缺口返回下一处证据，不扩大到无关模块。按场景 ID 返回实际结论、问题和依据。任务大小按涉及的链路与分支判断，不能用题数代替。局部复验只重查受影响断言；保留题仍逐题核对具体 diff。

源码复核失败时先修正说明、答案或场景，重新准备该版本并核对；未解决错误不能交给阅读者评分。宿主不能隔离复核上下文时记录 unavailable，继续可做的分析，不登记 accepted。

## 固定版本与独立阅读

源码核对通过后，独立读者只得到业务问题和临时目录中的 Markdown 快照，可以沿链接读知识页。不得提供生成历史、预期答案、源码、SQL、配置、测试或 `.reviews/` 附件。需要独立 Agent 时使用新上下文；不能隔离则记录 unavailable。用户指定人工验收时按实际过程记录。

阅读期间不修改本次快照或对应页面；可处理不改变这些页面的其他业务。发现新错误就结束该版本，修正后重新准备，不能边读边改或把新指纹套在旧答案上。

源码复核期间也保持绑定的题目、入口 claim 与页面不变。后台验收可用时，执行安排见 [init](workflows/init.md#持续处理清单)。网络或宿主故障不作为内容失败；确认版本未变后重试该阶段一次，再次失败保存 unavailable / needs-review 并继续可做的分析，不循环重启全部流程。旧目录保留，修订使用新目录；读取阶段重试可继续使用已封存的同一快照。

读者逐题回答业务结果、手册依据、代码位置和无法确认项。依据使用页面路径与实际 H2，代码位置使用文件内方法、SQL或行号。说明缺失时回答无法确认，不按惯例补推，也不读源码补答案。

## 评分、保存与复验

评分者以已核对的源码事实逐题比对条件、数据、生效、失败和定位。核心问题答错、无法回答、定位失败或需要读源码补答案均为 failed。相同错误出现在手册和答案中也不能通过；重新回到源码核对阶段修正。

保存全部实际题及结果，不能删失败题或批量填 passed。任何失败、未完成题或不可用复核均阻塞其关联入口 accepted。修订权威页后，只独立复验受影响题；未受影响答案需根据具体 diff 确認业务结论、依据和定位仍有效，保留原答案及阅读时间，追加本轮核对说明。共同规则变化检查所有使用方，定位变化复验定位。

源码或页面变化使旧记录待复核，推进基线不能替代重验。纯排版／错字也需具体 diff 核对；影响条件、数据、状态、生效、失败或交接的变化不得称为纯文案。结构检查只证明记录自洽，不证明答案语义或隔离声明真实。

## 内部记录工具

init / update 使用 `scripts/review.py` 处理记录结构、计划检查、指纹、时间、阅读快照和保存。它不是公开手册命令，不发现业务、不生成答案、不评分、不设置 accepted / complete，也不推进全库基线。格式见[验收契约](schema.md#验收记录)。审计的记录留在仓库外，不运行写入阶段。

新业务批次先按[计划模板](../assets/review-plan-template.json)在仓库外写纯 JSON：实际 id / target、entries 的入口与 claim 对应关系、问题、expected 和不适用理由。六方面须全部有题或有证据的不适用理由。工具补齐 pending 字段，并保存新记录和清单关联：

```sh
python3 <skill-directory>/scripts/review.py draft --root <project-directory> --record .smart-handbook/.reviews/<业务ID>-<批次ID>.json --input <plan.json>
```

draft 不覆盖已有路径或验收 ID，保留入口原有 claim、验收引用和 gaps，只将本批入口置为 needs-review；原 complete 清单回到 incomplete。新权威页可使用新记录；同一页面追加业务时沿用相关记录，追加待验题，再用 --scenario 选择新题及受影响旧题，保留题仍按实际 diff 核对。页面级指纹变化会使关联旧记录待复核，拆记录不能免除复验。业务 ID 与批次按实际关系决定；失败题的修订仍在原记录中保留，不另建记录或删引用绕过失败。已有记录用 JSON 编辑工具修订实际题目，不临时编写 Python 拼字段。

编辑已有记录后可只读检查计划：

```sh
python3 <skill-directory>/scripts/review.py plan --root <project-directory> --record .smart-handbook/.reviews/<业务ID>.json
```

plan 一次列出各入口的 tested / not_applicable / missing / conflicts 及结构问题；它不证明答案正确，也不更新记录。prepare 同样执行计划检查。修复反馈列出的全部问题后再准备，不能按第一个错误逐个试跑。

sources / pages 可暂空，源码核对和阅读保持 pending。准备版本时让工具自动创建仓库外的新 session：

```sh
python3 <skill-directory>/scripts/review.py prepare --root <project-directory> --record .smart-handbook/.reviews/<业务ID>.json
```

prepare 返回实际 session、source_task、reader 目录以及两份待填写的反馈 JSON 路径；后续使用返回的路径，不猜目录名。也可显式指定全新的 `--session`。它只读目标项目：先检查结构、来源角色、场景范围及六方面计划，计算本批入口和 claim 来源的指纹，保存全部 Markdown 快照。source-task.json 给源码复核者本批入口、题目、答案、来源和保留题的实际历史阅读，省去重复的评分历史；packet.json 保存完整绑定材料，由工具读取，必要时复核者可查历史。两者均不能给读者，`reader/` 仅含页面与问题。验收自动绑定 claim 所在页；依赖其他页的规则时重复传 `--page .smart-handbook/<页面>.md`，纳入源码核对与版本绑定。导航摘要变化不应让其他业务失效。先给源码复核者原始项目和 source_task，保存其实际反馈：

```json
{
  "status": "passed",
  "isolation": "independent",
  "description": "实际复核者及隔离方式",
  "findings": [],
  "retained": {}
}
```

status 使用 passed / failed / unavailable；findings 记录未解决错误，passed 要求 independent 且无未解决项。工具不判断反馈真假。使用实际反馈文件封存源码核对：

```sh
python3 <skill-directory>/scripts/review.py seal --root <project-directory> --session <temporary-directory>/review-01 --result <source-feedback.json>
```

seal 只写临时 session，自动记录收到反馈的真实时间并绑定题目、expected、不适用理由及版本指纹。reader_allowed 为 true 才开始独立阅读。阅读回复交评分者，逐题保存原始 reading 和实际判定：

```json
{
  "reader": {"isolation": "independent", "description": "实际读者及隔离方式"},
  "scenarios": [{
    "id": "实际场景ID",
    "reading": {"status": "answered", "answer": "实际回复", "evidence": [{"page": ".smart-handbook/modules/<业务ID>.md", "section": "实际H2"}], "locations": [{"path": "实现路径", "symbol": "类型#方法"}]},
    "verdict": "passed",
    "assessment": "根据源码逐项评分的理由"
  }]
}
```

不能将模型建议补成读者实际给出的定位。缺定位就 failed，并让读者复验。保存时运行：

```sh
python3 <skill-directory>/scripts/review.py finish --root <project-directory> --session <temporary-directory>/review-01 --result <graded-feedback.json>
```

finish 检查源码、题目和页面仍为同一版本，再保存实际反馈及工具时钟时间。只更新本批 claim 页的来源记录，保留对象结构、运行观察、其他页和全库旧基线；失败题仍保存 failed。Agent 随后核对入口状态，运行 check，同步摘要并继续下一批。

直接编辑工具生成的 source-feedback.json / graded-feedback.json，保留 ID 和字段结构；模板中的 pending / unavailable 是未完成状态，不能直接提交为通过。读者只获得 reader 目录；源码反馈与评分模板留给复核者／评分者。模板不能代替实际报告，不需要再次写转换脚本。

可将已收到的实际报告整理为工具字段，原报告保留在 session 附件中；多余说明放 description / assessment，retained 只放未选场景 ID。仅格式不符无需再次调用复核者或读者。整理不能改变判定、补造答案／定位，或把未解决错误移出 findings；缺少实际内容仍按失败或 unavailable 处理。

局部复验时 prepare 可重复传 `--scenario <ID>`；失败／未完成题必须选入，未选题必须原先 passed。源码复核反馈 retained 按未选 ID 给出本次具体 diff 核对理由；finish 保留原阅读答案与历史时间说明，记录本次确认时间，不伪称重新独立阅读。

若具体 diff 表明所有题的业务答案、依据与定位均不受影响，可用 prepare 的 `--retain-all`。仍须独立源码核对并逐题填写 retained；seal 的 reader_required 为 false 时，finish 使用原 reader 声明和空 scenarios，保留全部历史阅读。任何题有影响、失败或缺乏真实独立阅读证据就不能走此路径。

每次修订使用新 session；工具发现版本变化就拒绝保存，不自动刷新旧证据。工具不可用时按[格式契约](schema.md)手工记录实际时钟和版本、冻结阅读材料，并说明 automated check unavailable，不能编造验收过程。
