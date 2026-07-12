# Skill 目录

[English](skill-catalog.md) | 简体中文

可移植的调用方式是 `$omc-*` 或 `/skills`。每个 Skill 都遵循共享语言策略；使用工具的工作流还遵循能力契约。

| Skill | 主要职责 |
| --- | --- |
| `omc-orchestrator` | 路由生命周期工作并指出下一个决策 |
| `omc-doctor` | 只读检查当前能力和降级路径 |
| `omc-intentgate` | 要求验收、检查能力并选择续跑方式 |
| `omc-letgo` | 自主选择有界单轮或原生续跑 |
| `omc-loop` | 把已验证契约适配到原生 Goal 续跑 |
| `omc-init` | 初始化持久项目上下文 |
| `omc-discover` | 生成 MVP 发现简报 |
| `omc-spec` | 定义范围、非目标和验收条件 |
| `omc-architecture` | 定义模块、契约、风险和实施顺序 |
| `omc-implement` | 按证据执行已批准计划 |
| `omc-qa` | 验证验收路径和回归 |
| `omc-debug` | 修复前诊断根因 |
| `omc-refactor` | 在保持行为的前提下改进结构 |
| `omc-review` | 根据规格和标准审查变更 |
| `omc-release` | 准备发布决策和回滚计划 |
| `omc-debt` | 记录有意接受的工程取舍 |
| `omc-team` | 配置并运行原生子代理角色 |
| `omc-cn` | 把插件自有元数据和指导切换为简体中文 |
| `omc-en` | 恢复规范英文元数据和指导 |

续跑和语言入口仅允许显式调用。生命周期 Skills 的描述与请求匹配时，仍可被隐式发现。
