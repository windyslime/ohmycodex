# OhMyCodex

OhMyCodex is a skills-only Codex plugin for people building AI-assisted MVPs. It turns a vague product idea into a traceable engineering workflow: discover, scope, design, build, verify, review, release, and record technical debt.

It is intentionally not an agent runtime. It ships no MCP server, hooks, telemetry, browser automation, or required paid service.

## Install

After the first GitHub release is published, add the repository marketplace and install the plugin:

```bash
codex plugin marketplace add windyslime/ohmycodex --ref v0.2.0 --sparse .agents/plugins
codex plugin add ohmycodex@ohmycodex
```

Start a new chat, task, or Codex session after installation. In CLI or the IDE extension, invoke a workflow explicitly with `$ohmycodex-orchestrator`, or describe a matching task and let Codex select a skill.

## Start here

```text
Use $ohmycodex-orchestrator to help me turn this idea into a production-ready MVP.
```

On first use, the plugin creates `.ohmycodex/` in the target project. It keeps the project profile, approved specifications, decisions, plans, verification evidence, release records, and technical debt. This directory is local project state, not application runtime code.

## Skills

| Stage | Skill |
| --- | --- |
| Route work | `ohmycodex-orchestrator` |
| Set up project state | `ohmycodex-init` |
| Discover and scope | `ohmycodex-discover`, `ohmycodex-spec` |
| Design | `ohmycodex-architecture` |
| Build and verify | `ohmycodex-implement`, `ohmycodex-qa` |
| Improve and inspect | `ohmycodex-debug`, `ohmycodex-refactor`, `ohmycodex-review` |
| Ship and track trade-offs | `ohmycodex-release`, `ohmycodex-debt` |

See [the skill catalog](docs/skill-catalog.md) and [compatibility notes](docs/compatibility.md).

## Team mode

Use `$ohmycodex-team` for complex work that benefits from independent investigation. In local Codex Desktop, CLI, and IDE projects, ask it to enable Team mode; it installs missing project-local `omc-*` custom agent templates without replacing existing `.codex` configuration.

Team mode uses Luna for Explorer, Librarian, and QA; Terra for Implementer and Debugger; Sol for Architect and Reviewer; and GPT-5.5 only as an explicit fallback. It runs read-only work in parallel, keeps application changes to one writer, and records the consolidated result under `.ohmycodex/plans/team-runs/`. See [Team mode](docs/team-mode.md).

## Compatibility

The package is designed for ChatGPT Work on the web, ChatGPT/Codex Desktop, Codex CLI, and the Codex IDE extension. It uses host-neutral instructions and falls back to conversation-only guidance when the current host cannot write files or run commands. Codex cloud is not a supported claim in v0.2.0.

## Development

```bash
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a skill change. The project is licensed under [MIT](LICENSE).
