# Codex

## 安装

```sh
codex plugin marketplace add eryihan/smart-handbook
codex plugin add smart-handbook@smart-handbook
```

安装后在目标项目中新开会话。

## 使用

在 Codex 会话中输入普通文本命令，或直接描述任务。需要明确调用 Skill 时，在 CLI 或 IDE 扩展中输入 `$smart-handbook help`，也可通过 `/skills` 选择：

```text
handbook help
handbook help update
handbook init
handbook work 审批结束了，但数据没有生效，帮我定位原因
handbook update
handbook audit
handbook status
```

参数和路由规则见[命令说明](commands.md)。项目知识位于目标项目根目录的 `.smart-handbook/`。

## 本地开发

将 `<repo-directory>` 替换为本仓库的绝对路径：

```sh
codex plugin marketplace add <repo-directory>
codex plugin add smart-handbook@smart-handbook
```

查看 marketplace 中可用的插件：

```sh
codex plugin list --available --marketplace smart-handbook --json
```

Codex 通过兼容格式读取 `.claude-plugin/marketplace.json`，复用本仓库的 Skill 和资源。格式见 OpenAI 官方的[插件打包说明](https://developers.openai.com/plugins/build/plugins)，使用方式见[Codex 插件说明](https://developers.openai.com/learn/developers-codex-plugin)。
