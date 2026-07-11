# Contributing

Keep OhMyCodex focused on repeatable engineering workflows for AI-assisted products.

Before opening a pull request, describe the user prompt that should trigger the change, the expected artifact or behavior, and the failure mode it prevents. Keep skill descriptions concise, use only `name` and `description` in `SKILL.md` frontmatter, and avoid adding a dependency unless a workflow cannot be reliable without it.

Run both validators before requesting review:

```bash
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
```

Do not add MCP servers, hooks, telemetry, credentials, browser-only instructions, or surface-specific behavior without a separately approved proposal. Preserve the plugin's host-neutral fallback: when a capability is unavailable, say so and continue with the safest useful alternative.
