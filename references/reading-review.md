# 阅读验收

init 验收各入口，update 复验受影响场景，audit 检查已有记录与所审业务。源码核对检验说明和答案是否正确，独立阅读检验手册能否让新人理解；两者分别完成，互不代替。

## 规划与源码核对

生成者读完本地链路，编写业务页及实际场景。逐入口覆盖正常路径、权限/状态拒绝、生效边界、部分失败、重复执行、异步交接六个方面；它们是角度，不规定题数。一题可覆盖多个方面，共用实现可联合验收，但须包含入口差异。不适用时提供源码支持的具体理由，正常路径不能排除。

先按具体动作判断六方面各自适用与否，再组合问题。场景的 topics 对其列出的每个入口都生效；合并题须能核对每个动作的条件、资源、结果及定位，控制器数量、接口族性质和代表方法不能证明其他动作通过。适用方面不同的入口拆题，不能给查询入口套用写入链的异步或部分失败标签，也不能为消除冲突把不适用项改成已测试。是否不适用仍由实现决定，不能仅凭“查询”名称判断。

预期答案写清条件、实际资源、字段、状态、停止位置及实现证据。按实际分支出题，不能只从手册摘问题；尤其检查校验前副作用、远端成功后本地失败、异步体异常、消息交接和重复副作用。首次阅读前准备完整场景，不把缺失题目留到通过后补齐。

先检查动作粒度、格式及场景计划，再让未继承生成历史的源码复核者读取原始实现、SQL、实体和配置：先独立复述调用顺序及失败结果，再比对手册、答案和不适用理由。独立性相对生成者判断；生成者自查、继承生成历史的 Agent，或“只与读者不同”均不满足。实际新上下文记录 context=fresh，生成上下文自查为 authoring，无法隔离为 unavailable；后二者不能通过。接口须查实际实现；本地跨模块继续追踪，关键框架／依赖行为遵循[沿实现追踪](endpoint-analysis.md#沿实现追踪)。逐项记录错误和依据，不能把已有答案当作标准答案背书。

委派时给出本批具体动作、待核对断言、入口与已发现的实现／SQL／配置位置、相关页面及输出文件。定位只帮助起步，复核者仍沿调用补查依赖；遇到缺口返回下一处证据，不扩大到无关模块。按场景 ID 返回实际结论、问题和依据。任务大小按涉及的链路与分支判断，不能用题数代替。局部复验只重查受影响断言；保留题仍逐题核对具体 diff。

源码复核失败时先修正说明、答案或场景，重新准备该版本并核对；未解决错误不能交给阅读者评分。宿主不能隔离复核上下文时记录 unavailable，继续可做的分析，不登记 accepted。

## 固定版本与独立阅读

源码核对通过后，独立读者只得到业务问题、回答模板和临时目录中已绑定的 Markdown 快照，可以沿包内链接阅读。不得提供生成历史、预期答案、源码、SQL、配置、测试或 `.reviews/` 附件。需要独立 Agent 时使用新上下文；不能隔离则记录 unavailable。用户指定人工验收时按实际过程记录。

阅读期间不修改本次快照或对应页面；可处理不改变这些页面的其他业务。发现新错误就结束该版本，修正后重新准备，不能边读边改或把新指纹套在旧答案上。

源码复核期间也保持绑定的题目、入口 claim 与页面不变。后台验收可用时，执行安排见 [init](workflows/init.md#持续处理清单)。网络或宿主故障不作为内容失败；确认版本未变后重试该阶段一次，再次失败保存 unavailable / needs-review 并继续可做的分析，不循环重启全部流程。旧目录保留，修订使用新目录；读取阶段重试可继续使用已封存的同一快照。

读者逐题回答业务结果、手册依据、代码位置和无法确认项。依据使用页面路径与实际 H2，代码位置使用文件内方法、SQL或行号。合并题逐动作作答，在定位的 entrypoints 中标明对应动作；可共享实际实现，不能用代表方法代替其他动作。题目中的条件、数据、生效、失败或定位无法回答时写入 unanswered；与题目无关的部署／远端未知在正文说明。说明缺失时不按惯例补推，也不读源码补答案。

## 评分、保存与复验

评分者以已核对的源码事实逐题、逐动作比对条件、数据、生效、失败和定位。核心问题答错、无法回答、定位失败或需要读源码补答案均为 failed；读者忠实记录手册缺失也属于手册验收失败。unanswered 非空不能 passed。相同错误出现在手册和答案中也不能通过；重新回到源码核对阶段修正。不能以控制器族性质或共用实现为由，将未解释的动作一并通过。

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

prepare 返回实际 session、source_task、reader 目录及源码反馈、读者回答、评分三个 JSON 路径；后续使用返回的路径，不猜目录名。也可显式指定全新的 `--session`。它只读目标项目：检查本批与绑定依赖的结构、来源角色、场景及六方面计划；身份、路径、清单和状态损坏仍阻塞，无关页面／记录问题返回 deferred_issues，后续处理及全局收尾仍须解决。

验收自动绑定 claim 所在页；准备前按问题和正文引用选出实际依赖页，重复传 `--page .smart-handbook/<页面>.md`。工具将这些页及其 claim 来源一起纳入源码核对、指纹和阅读包。仅导航链接不必加入；选择由 Agent 阅读业务关系决定，不自动遍历整库链接。读者需要但包内没有的规则须回答无法确认，保存失败后补依赖、重新核对并复验，不能删引用或换成别处依据。

source-task.json 给源码复核者本批入口、题目、答案、绑定页及来源、保留题的历史阅读；复核绑定页中本批所用的公共规则与代码位置。packet.json 保存完整绑定材料，均不能给读者。`reader/` 只含已绑定的页面、questions.json 和 answers.json；无关导航更新不使本批失效。先给源码复核者原始项目和 source_task，保存其实际反馈：

```json
{
  "status": "passed",
  "isolation": "independent",
  "context": "fresh",
  "description": "实际复核者及隔离方式",
  "findings": [],
  "retained": {}
}
```

status 使用 passed / failed / unavailable；findings 记录未解决错误，passed 要求 independent 且无未解决项。工具不判断反馈真假。使用实际反馈文件封存源码核对：

```sh
python3 <skill-directory>/scripts/review.py seal --root <project-directory> --session <temporary-directory>/review-01 --result <source-feedback.json>
```

seal 只写临时 session，自动记录收到反馈的真实时间并绑定题目、expected、不适用理由及版本指纹。新反馈通过须 context=fresh；字段是可核对声明，不能代替实际隔离。reader_allowed 为 true 才开始独立阅读。读者读取 prepare 生成的 guide.md（字段规则与真实 H2）、questions.json 和冻结页面，直接填写 reader_feedback（reader/answers.json），不提供评分文件：

```json
{
  "reader": {"isolation": "independent", "description": "实际读者及隔离方式"},
  "scenarios": [{
    "id": "实际场景ID",
    "reading": {"status": "answered", "answer": "实际回复", "unanswered": [], "evidence": [{"page": ".smart-handbook/modules/<业务ID>.md", "section": "实际H2"}], "locations": [{"path": "实现路径", "symbol": "类型#方法", "entrypoints": ["对应动作ID"]}]}
  }]
}
```

读者完成后保留该文件原样。主 Agent 可一次只读检查全部输出问题，不重新执行源码复核：

```sh
python3 <skill-directory>/scripts/review.py plan --root <project-directory> --session <temporary-directory>/review-01
```

此调用汇总字段、H2、定位格式、动作对应及显式未答项，不替代评分，也不改文件。纯序列化／多余字段／H2 格式问题一次反馈给原读者，按原快照自行修正；不能夹带源码结论、具体方法答案或删除缺失说明。手册缺少业务定位和规则属于内容失败，保存失败后修订并复验，不当作格式问题反复提示答案。finish 同样汇总这些问题，不必为每条错误另建 session。

评分者只填写 graded-feedback.json：

```json
{"scenarios": [{"id": "实际场景ID", "verdict": "passed", "assessment": "根据源码逐项评分的理由"}]}
```

评分文件不接受 reading 或 reader 字段。不能补方法、替换定位或删除读者实际引用；缺定位、关键答案无法确认就 failed，修订后交读者复验。保存时运行：

```sh
python3 <skill-directory>/scripts/review.py finish --root <project-directory> --session <temporary-directory>/review-01 --result <graded-feedback.json>
```

finish 检查源码、题目和页面仍为同一版本，从 answers.json 直接保存 reading，另存逐题 reading_fingerprint，评分仅提供判定与理由。新答案必须显式填写 unanswered；合并题定位逐动作对应，未答项不能被评分覆盖。错误定位和缺失依据可原样保存为 failed；passed 仍要求正确、已绑定的依据和具体定位。工具不证明读者身份或隔离真实，评分者也不得编辑回答文件。只更新本批 claim 页的来源记录，保留运行观察、其他页和旧基线。Agent 核对入口状态，运行 check，同步摘要并继续下一批。

复核者、读者和评分者分别填写工具生成的对应模板，保留 ID 和字段结构；pending / unavailable 是未完成状态，不能直接提交为通过。模板不能代替实际报告，不需要再次写转换脚本。

人工或宿主只能返回文本时，可一次整理为 JSON 并保留原报告；仅整理字段和序列化，不增删答案、依据、定位或未解决 findings。正常 AI 阅读直接输出模板。多余说明放 description / assessment，retained 只放未选场景 ID；缺少实际内容仍按失败或 unavailable 处理。

局部复验时 prepare 可重复传 `--scenario <ID>`；失败／未完成题必须选入，未选题必须原先 passed。源码复核反馈 retained 按未选 ID 给出本次具体 diff 核对理由；finish 保留原阅读答案与历史时间说明，记录本次确认时间，不伪称重新独立阅读。

若具体 diff 表明所有题的业务答案、依据与定位均不受影响，可用 prepare 的 `--retain-all`。仍须独立源码核对并逐题填写 retained；seal 的 reader_required 为 false 时，评分文件为 `{"scenarios": []}`，finish 使用原 reader 声明并保留全部历史阅读及已有指纹。已知失败、未答项、定位被补写、答案指纹冲突或缺乏真实独立阅读证据不能保留。旧 V3 缺增补字段时对照实际报告，区分有效、明确冲突与无法确认：有效题不为升级重新阅读，不补造 context 或原始指纹；冲突题选入局部复验，无法确认项如实留在交付边界，不以间接佐证背书。

每次修订使用新 session；工具发现版本变化就拒绝保存，不自动刷新旧证据。工具不可用时按[格式契约](schema.md)手工记录实际时钟和版本、冻结阅读材料，并说明 automated check unavailable，不能编造验收过程。
