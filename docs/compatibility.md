# Compatibility

OhMyCodex is a skills-only plugin. It targets the plugin and skills surfaces documented for ChatGPT Work Web, ChatGPT/Codex Desktop, Codex CLI, and the Codex IDE extension.

| Surface | Expected behavior |
| --- | --- |
| ChatGPT Work Web | Discover and invoke installed skills; delegate generic roles when available, but do not claim project-local model pins. |
| Desktop | Discover installed skills, install local Team templates, and create project artifacts when the selected workspace is writable. |
| CLI | Install from the configured marketplace; invoke skills with `$`; install Team templates and inspect native agent threads with `/agent`. |
| IDE extension | Install through plugin settings; start a new chat; install Team templates and inspect available background-agent activity. |

Do not advertise Codex cloud support in v0.2.0. Do not require a browser, computer-control tool, MCP server, secret, paid API, app, hook, or external runtime dependency on any surface.
