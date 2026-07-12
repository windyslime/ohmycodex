# 兼容性

[English](compatibility.md) | 简体中文

OhMyCodex v0.3 是一个只包含 Skills 的插件。当前宿主提供的控制能力具有最高权威；本地 CLI 配置无法凭空创造当前任务未暴露的能力。

| 使用界面 | 预期行为 |
| --- | --- |
| ChatGPT Work Web | 调用已安装的 Skills，仅在暴露 Scheduled 时使用它。不得声称可以访问本地项目文件、命令、Team 模板或重写插件元数据。 |
| Codex Desktop | 在能力可用时使用可写项目产物、原生 Goals 和 Scheduled、原生子代理，以及已安装插件的语言切换；切换后需重启或新建任务。 |
| Codex CLI | 使用 `$omc-*` 或 `/skills` 调用，在暴露 Goal 控制时使用它，通过 `codex mcp` 管理 MCP，并使用原生子代理。不假定存在 Scheduled 管理能力。 |
| Codex IDE extension | 调用已安装的 Skills，使用可用的 Goal 和子代理控制，并在允许时写入项目产物。不假定存在 Scheduled 管理能力。 |

没有 Goal 支持时，续跑降级为当前有用的一轮；不会创建 Stop Hook、shell 循环、守护进程或自定义运行时。没有 Scheduled 时，短进程可以使用有界终端等待，长时间外部等待则保留为可恢复 Goal。心跳会返回同一任务，并在终态前清理。

项目不可写时，持久审计和自定义阈值恢复能力会降低。Git 不可用时，使用带标签的文件和验收指纹提供较弱的证据身份。缺少 LSP 或 AST 工具时，使用声明的项目、编译器或解析器路径；文本搜索绝不能替代结构化重写。

MCP 安装始终使用 Codex 原生控制，并保留信任和身份验证提示。OhMyCodex 不捆绑 MCP Server、App、Hook、浏览器自动化、密钥、付费 API、守护进程或遥测。
