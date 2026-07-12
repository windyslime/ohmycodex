# 贡献指南

[English](CONTRIBUTING.md) | 简体中文

请让 OhMyCodex 始终专注于复用原生 Codex 控制能力的可重复工程工作流。说明触发提示词、预期行为或产物，以及希望避免的失败模式。续跑、Doctor 和语言切换入口必须保持仅显式调用；Skill frontmatter 应简洁且不引入依赖。

提交审查前请运行完整验证集：

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
for skill in plugins/ohmycodex/skills/omc-*; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

测试事务失败和降级路径，不能只测试成功路径。仓库中物化的元数据保持英文。若未单独批准设计，不得添加自定义代理运行时、MCP Server、App、Hook、守护进程、遥测、凭据，也不得直接编辑 Codex 配置。
