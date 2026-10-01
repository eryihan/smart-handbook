# handbook init

从任务目标版本建立项目导航，再分批编写关键模块和流程。重建已有 Handbook 时，先保留其中的业务知识和状态，核对后再替换。

## 确定范围与入口

确认目标仓库、branch / commit / worktree、未提交修改和执行约束。线上部署版本未确认时，结论限于所读取版本。

识别技术栈、构建入口和业务入口。V1 优先围绕 Java、Spring Boot、Maven / Gradle、MyBatis / SQL、REST、RPC、Consumer 和 Scheduled Job 搜索；其他技术栈使用相应源码与配置入口。

用构建定义、路由、注解、配置和代码建立模块导航，按职责、入口、数据、状态与编排关系划分模块。每个已发现入口归属模块，或记录为未归属缺口。保存已搜索范围和未检查范围。

## 分批建页

在目标仓库创建 `.smart_handbook/`，从[模板目录](../../assets/handbook/)生成 README、system、map、working-guide，创建 modules 和 flows 目录。填写真实项目内容，替换示例名称与 ID；格式见[契约](../schema.md)。

先编写 system 的边界、概念、状态、数据、依赖、配置来源和本地验证条件。随后按失败影响、使用频率、跨模块复杂度、知识缺失、恢复难度和任务相关性选择深入顺序。

先完成一个关键 module，以及一条确有跨模块交接需求的 flow，再随实际任务扩展。完整导航只表示入口有记录；未经深入阅读的模块保留 `navigation-only`，已知缺口保留 `known-gap`。每完成一页即保存，同一结论只维护一处。

## 证据与验收

对关键输入、状态、事务、顺序、权限、重试、幂等、失败、副作用和恢复条件建立 claim，关联目标版本的实现文件及可选 symbol。背景材料单列，说明历史适用范围。

`<skill-directory>` 使用 Skill 安装目录的绝对路径，`<project-directory>` 使用目标仓库的绝对路径：

```sh
python3 "<skill-directory>/scripts/handbook.py" check --root "<project-directory>" --format json
```

修复输出中的格式和引用错误；来源摘要在 `pages[页面路径].sources[来源路径].fingerprint`。完成源码复核后，仅将已复核页面的摘要保存到 `.state.json`，复核与行为验证分别记录。

从业务词或症状检验能否定位 module / flow、入口、状态和代码，记录定位失败、遗漏入口和证据缺口。

按[状态保存规则](../schema.md)记录实际读取版本、来源指纹、复核时间和已执行验证。工具或历史基线不可用时，记录降级方式及未检查范围。
