# 模块名称

<!-- handbook-meta
{
  "schema_version": 1,
  "id": "module-example",
  "kind": "module",
  "coverage": "navigation-only",
  "claims": [],
  "source_ranges": [],
  "config_ranges": []
}
-->

## 职责与边界

填写负责的业务、排除范围和目标代码版本。

## 关键概念、数据与状态

引用 system 的全局定义，描述本模块的数据归属、状态及变化条件。

## 入口与核心实现路径

列出入口、仓库相对路径、可选 symbol 和核心调用次序。填写 metadata 的 source_ranges 与 config_ranges，使用文件或目录路径。

## 当前行为与关键约束

描述已核对的输入、状态、权限、顺序、事务、幂等、失败处理及恢复条件。关键结论建立 claim 并关联实现文件；缺少证据时标记 unknown / unverified。

## 修改位置与影响范围

指出常见修改入口、交接模块、相关 flow 和公共组件，说明需要一起核对的接口、状态或配置。

## 验证方法与覆盖边界

记录环境和前提、验证方法、实际结果及未覆盖范围。未执行时记录 not-run。

## 排障与维护操作

列出正常状态路径、候选原因及支持或反证位置。维护操作写清对象、范围、副作用、前提、重跑条件和完成判据。

## 证据与已知缺口

实现证据使用仓库相对 path 和可选 symbol；背景材料单列为 Context Evidence。列出未确认的版本、配置、依赖行为或验证条件。
