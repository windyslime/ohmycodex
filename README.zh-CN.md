# OhMyCodex

OhMyCodex 是一个只包含 Skills 的 Codex 插件，用原生 Codex Goal、Scheduled、子代理、权限、MCP 控制和项目工具，把 AI 辅助 MVP 的规格、决策、实现、验证、审查和发布串成可追溯工作流。

它不提供 MCP Server、App、Hook、守护进程、遥测、自定义模型供应商或独立调度器。

## 安装

```bash
codex plugin marketplace add windyslime/ohmycodex --ref v0.3.0 --sparse .agents/plugins
codex plugin add ohmycodex@ohmycodex
```

安装后新建任务。可移植的调用方式是 `$omc-*` 或 `/skills`：

```text
使用 $omc-orchestrator 将我的应用想法转化为可构建的 MVP。
```

部分 Codex 客户端可能把 `/omc-*` 文本解析为 Skill mention；这只是客户端便利功能，OhMyCodex 不注册额外的斜杠命令运行时。

## v0.3 破坏性迁移

v0.3 把所有公开 Skill 硬改名为 `omc-*`，不提供兼容别名。升级前请更新保存的提示词和文档。迁移表见 [v0.3.0 发布说明](docs/releases/v0.3.0.md)。

## 自动续跑

- `$omc-intentgate` 检查能力并要求先有验收契约；仅在新循环开始前询问一次无进展阈值。
- `$omc-loop` 使用持久化原生 Goal 续跑。阈值默认和最小值都是 `3`，没有最大值，统计连续出现同一证据阻塞的 Goal 轮次；OhMyCodex 不另设总循环次数上限。
- `$omc-letgo` 让 Codex 自主决定当前轮完成还是进入续跑，并自行记录假设和选择阈值。原生权限、信任、MCP、推送、部署、标签和公开发布确认仍然有效。

Scheduled 心跳只用于外部等待，并在终态前删除。当前环境没有 Goal 能力时，只执行当前有用的一轮，不使用 shell 循环或 Hook 模拟。

## 语言切换

默认语言是英文。运行 `$omc-cn` 切换简体中文，运行 `$omc-en` 恢复英文。切换成功后需重启 Codex 或新建任务，让描述重新加载。它不会翻译代码、命令、路径、原始日志、其他插件或 Codex 其余界面。

## Team 模式

复杂任务可使用 `$omc-team`。它只安装缺失的 `.codex/agents/omc-*.toml`，保留项目已有配置；只读角色可以并发，实际代码保持单写入者。详情见 [Team mode](docs/team-mode.md)。

完整入口见 [Skill 目录](docs/skill-catalog.md)，平台差异见 [兼容性说明](docs/compatibility.md)。
