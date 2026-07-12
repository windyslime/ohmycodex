# Compatibility

English | [简体中文](compatibility.zh-CN.md)

OhMyCodex v0.3 is a skills-only plugin. Active host controls are authoritative; local CLI configuration cannot manufacture a capability that the current task does not expose.

| Surface | Expected behavior |
| --- | --- |
| ChatGPT Work Web | Invoke installed Skills and use Scheduled only when exposed. Do not claim local project files, commands, Team templates, or plugin metadata rewriting. |
| Codex Desktop | Use writable project artifacts, native Goals and Scheduled when exposed, native subagents, and installed-plugin language switching followed by restart or a new task. |
| Codex CLI | Invoke with `$omc-*` or `/skills`, use Goal controls when exposed, manage MCP through `codex mcp`, and use native subagents. Scheduled management is not assumed. |
| Codex IDE extension | Invoke installed Skills, use available Goal/subagent controls, and write project artifacts when allowed. Scheduled management is not assumed. |

When Goal support is absent, continuation degrades to the current useful turn; no Stop Hook, shell loop, daemon, or custom runtime is created. When Scheduled is absent, a short process may use a bounded terminal wait, while a long external wait remains a recoverable Goal. Heartbeats return to the same task and are cleaned before terminal outcomes.

When project writes are unavailable, durable audit and custom threshold recovery are reduced. When Git is unavailable, labeled file and acceptance fingerprints provide weaker evidence identity. Missing LSP or AST tools use declared project/compiler/parser routes; text search never substitutes for a structural rewrite.

MCP installation always uses Codex-native controls and preserves trust and authentication prompts. OhMyCodex bundles no MCP server, App, Hook, browser automation, secret, paid API, daemon, or telemetry.
