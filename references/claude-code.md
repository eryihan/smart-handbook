# Claude Code

## 安装

终端安装和离线安装见 [README](../README.md#安装)。也可在 Claude Code 中添加 marketplace，并从插件面板安装：

```text
/plugin marketplace add eryihan/smart-handbook
/plugin install smart-handbook@smart-handbook
```

安装后在目标项目中启动新会话。已有会话可用 `/reload-plugins` 刷新，通过 `/plugin` 查看启用状态，通过 `/` 菜单查看命令。

## 使用

使用专用 slash command，例如 `/smart-handbook:init`。完整入口列表、参数、默认行为与读写范围统一见[命令说明](commands.md)。核心 Skill 只路由明确的手册请求。

通用入口为 `/smart-handbook:smart-handbook <command> <参数>`。也支持普通文本 `handbook <command>` 和明确的手册请求。

## 更新

通过 `/plugin` 管理已安装插件和 marketplace 更新。插件名为 `smart-handbook`，marketplace 名为 `smart-handbook`，安装 ID 为 `smart-handbook@smart-handbook`。

## 本地开发

从本地 marketplace 安装，将 `<repo-directory>` 替换为本仓库的绝对路径：

```sh
claude plugin marketplace add <repo-directory>
claude plugin install smart-handbook@smart-handbook
```

直接加载开发目录：

```sh
claude --plugin-dir <repo-directory>
```

在仓库根目录校验分发文件：

```sh
claude plugin validate .claude-plugin/plugin.json
claude plugin validate .claude-plugin/marketplace.json
```

`.claude-plugin/plugin.json` 的 `skills: ["./"]` 加载根目录 Skill；`commands/` 提供专用入口，通过 `${CLAUDE_PLUGIN_ROOT}` 读取资源。目标项目知识写入该项目的 `.smart-handbook/`，脚本的 `--root` 指向目标项目。

分发格式见 Claude Code 官方的[插件参考](https://code.claude.com/docs/en/plugins-reference)与[marketplace 文档](https://code.claude.com/docs/en/plugin-marketplaces)。
