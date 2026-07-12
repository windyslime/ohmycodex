# Contributing

English | [简体中文](CONTRIBUTING.zh-CN.md)

Keep OhMyCodex focused on repeatable engineering workflows that reuse native Codex controls. Describe the triggering prompt, expected behavior or artifact, and failure mode prevented. Preserve explicit-only policy for continuation, Doctor, and locale entries; keep Skill frontmatter concise and dependency-free.

Run the complete validation set before review:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
for skill in plugins/ohmycodex/skills/omc-*; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

Test transaction failure and degradation paths, not only success. Leave checked-in metadata materialized in English. Do not add a custom agent runtime, MCP server, App, Hook, daemon, telemetry, credentials, or direct Codex configuration editing without a separately approved design.
