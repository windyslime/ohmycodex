# OhMyCodex
inspired by https://github.com/opensoft/oh-my-opencode

OhMyCodex is a skills-only Codex plugin for building AI-assisted MVPs with traceable specifications, decisions, implementation evidence, review, and release records. It reuses native Codex Goals, Scheduled tasks, subagents, permissions, MCP controls, and project tooling instead of adding another agent runtime.

It ships no MCP server, app, Hook, daemon, telemetry, custom model provider, or independent scheduler.

## Install

```bash
codex plugin marketplace add windyslime/ohmycodex --ref v0.3.0 --sparse .agents/plugins
codex plugin add ohmycodex@ohmycodex
```

Start a new task after installation. Portable invocation uses `$omc-*` or `/skills`:

```text
Use $omc-orchestrator to turn my app idea into a buildable MVP.
```

Some Codex clients may resolve `/omc-*` text to a Skill mention as a UI convenience. OhMyCodex does not register a separate slash-command runtime.

## Breaking v0.3 migration

v0.3 hard-renames every public Skill to the `omc-*` namespace with no compatibility aliases. Update saved prompts and documentation before upgrading. See [the v0.3.0 release notes](docs/releases/v0.3.0.md).

## Continuation entries

- `$omc-intentgate` inspects capabilities, requires an acceptance contract, and asks once for the no-progress threshold before a new run.
- `$omc-loop` continues validated work through a persisted native Goal. The threshold defaults to `3`, must be at least `3`, has no maximum, and counts consecutive materially unchanged blocker turns. OhMyCodex adds no total iteration limit.
- `$omc-letgo` lets Codex choose between a bounded current turn and Goal-backed continuation. It records assumptions and chooses the threshold, while native trust, sandbox, MCP, release, push, deploy, tag, and publication gates remain authoritative.

Scheduled heartbeat is used only for external waits and is deleted before terminal outcomes. Without Goal support, OhMyCodex performs at most the current useful turn; it never emulates continuation with a shell loop or Hook.

## Language

English is the checked-in default. Run `$omc-cn` for Simplified Chinese metadata and OhMyCodex output, or `$omc-en` to restore English. After either switch, restart Codex or start a new task so descriptions reload. The setting does not translate code, commands, paths, raw logs, other plugins, or the rest of the Codex UI.

## Skill groups

| Purpose | Skills |
| --- | --- |
| Route and inspect | `omc-orchestrator`, `omc-doctor`, `omc-intentgate`, `omc-letgo` |
| Continue | `omc-loop` |
| Project lifecycle | `omc-init`, `omc-discover`, `omc-spec`, `omc-architecture`, `omc-implement`, `omc-qa`, `omc-debug`, `omc-refactor`, `omc-review`, `omc-release`, `omc-debt` |
| Delegate | `omc-team` |
| Language | `omc-cn`, `omc-en` |

See [the complete Skill catalog](docs/skill-catalog.md), [compatibility notes](docs/compatibility.md), and [Team mode](docs/team-mode.md).

## Project state

When the workspace is writable, OhMyCodex stores project guidance under `.ohmycodex/`. Continuation state lives in `.ohmycodex/runtime/loops/`, with compact audit records in `.ohmycodex/plans/loop-runs/`. These are agent workflow records, not application runtime code.

## Development

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
```

Read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a change. The project is licensed under [MIT](LICENSE).
