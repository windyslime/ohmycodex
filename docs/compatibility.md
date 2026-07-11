# Compatibility

OhMyCodex is a skills-only plugin. It targets the plugin and skills surfaces documented for ChatGPT Work Web, ChatGPT/Codex Desktop, Codex CLI, and the Codex IDE extension.

| Surface | Expected behavior |
| --- | --- |
| ChatGPT Work Web | Discover and invoke installed skills; use conversation-only fallback when local repository access is absent. |
| Desktop | Discover installed skills and create project artifacts when the selected workspace is writable. |
| CLI | Install from the configured marketplace; invoke skills with `$`; run declared local verification commands when available. |
| IDE extension | Install through plugin settings; start a new chat; use repository context and available terminal capabilities. |

Do not advertise Codex cloud support in v0.1.0. Do not require a browser, computer-control tool, MCP server, secret, paid API, app, hook, or runtime dependency on any surface.
