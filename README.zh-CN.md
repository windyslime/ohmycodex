# OhMyCodex

OhMyCodex 是一个只包含 skills 的 Codex 插件，面向用 AI 快速构建 MVP、同时希望项目保持可维护和可验证的开发者。

它不提供新的 Agent runtime，不包含 MCP、hooks、遥测、浏览器自动化或强制付费服务。它做的是将产品想法、工程决策、实现、测试、审查和发布串成一套可追溯的工作流。

## 安装

首个 GitHub Release 发布后，可使用：

```bash
codex plugin marketplace add windyslime/ohmycodex --ref v0.1.0 --sparse .agents/plugins
codex plugin add ohmycodex@ohmycodex
```

安装后请新建一个聊天、任务或 Codex session。推荐从下面的入口开始：

```text
Use $ohmycodex-orchestrator to help me turn this idea into a production-ready MVP.
```

首次使用时会在目标项目创建 `.ohmycodex/`，保存项目画像、规格、决策、计划、验证证据、发布记录和技术债。它不属于应用运行时代码。

更多信息请阅读英文 [README](README.md)、[skill 目录](docs/skill-catalog.md) 与 [兼容性说明](docs/compatibility.md)。
