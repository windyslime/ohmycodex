# Team 模式

[English](team-mode.md) | 简体中文

`$omc-team` 在现有 OhMyCodex 插件内配置原生 Codex 子代理，不添加第二套运行时。

随附安装器只把缺失模板复制到 `.codex/agents/`，并且仅在项目没有现有 `[agents]` 配置段时添加安全默认值。它绝不覆盖项目自有的代理文件或现有代理配置。

| 角色 | 模型策略 | 访问权限 |
| --- | --- | --- |
| Explorer、Librarian、QA | Luna | 只读 |
| Architect、Reviewer | Sol | 只读 |
| Implementer | Terra | 工作区写入 |
| Debugger | Terra | 只读 |
| Fallback | GPT-5.5 | 继承父级策略 |

Team 仅用于彼此独立的调查。第一轮最多并发三个只读角色，由父任务汇总；应用代码只允许一个写入者，并在验证后进行审查。原生子代理不可用时，在父任务中按相同角色顺序执行，并标注为顺序降级；不得声称模型固定策略已生效。
