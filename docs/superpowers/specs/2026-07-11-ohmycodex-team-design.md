# OhMyCodex Team Design

## Goal

Extend the single OhMyCodex plugin with native Codex subagent orchestration while retaining the existing skills-only distribution model.

## Shape

The plugin adds one public skill, `ohmycodex-team`, and bundles project-installable custom-agent TOML templates under that skill's assets. When a user explicitly enables team mode for a repository, the skill copies or merges those templates into `.codex/agents/` and safely adds only missing `[agents]` settings to `.codex/config.toml`.

No second plugin, MCP server, hook, telemetry service, or external runtime is introduced. ChatGPT Work Web can still use the role workflow through direct delegation, but cannot rely on the local TOML model pins. Desktop, CLI, and IDE use the native custom-agent configuration when installed.

## Agent roster

| Agent | Model | Reasoning | Write policy |
| --- | --- | --- | --- |
| `omc-explorer` | `gpt-5.6-luna` | `low` | Read-only |
| `omc-librarian` | `gpt-5.6-luna` | `medium` | Read-only |
| `omc-qa` | `gpt-5.6-luna` | `medium` | Read-only |
| `omc-architect` | `gpt-5.6` | `xhigh` | Read-only |
| `omc-implementer` | `gpt-5.6-terra` | `high` | Workspace write |
| `omc-debugger` | `gpt-5.6-terra` | `high` | Read-only by default |
| `omc-reviewer` | `gpt-5.6` | `high` | Read-only |
| `omc-fallback` | `gpt-5.5` | `high` | Inherit parent policy |

`gpt-5.6` is the Sol tier alias. Do not use any GPT-5.4 model. The Codex custom-agent schema has no automatic fallback field: when a role's preferred model is unavailable, Team explicitly requests `omc-fallback` with the original role's task contract.

## Orchestration contract

Team starts only for independent, multi-file, uncertain, or cross-disciplinary work. It keeps `max_threads = 4` and `max_depth = 1`.

1. Run only independent read-only agents in parallel: explorer, librarian, QA, and when relevant reviewer.
2. The parent task consolidates evidence, identifies contradictions, and records the chosen plan.
3. Run architect only after discovery is sufficient.
4. Run a single implementer after the plan is approved. Never run concurrent writers.
5. Run reviewer after implementation and QA. Route failures to debugger or implementer as appropriate.

Every delegated prompt requires a concise result with: conclusion, evidence paths or commands, risks, and recommendation. The parent waits for requested workers before making a decision. A host without native subagents performs the same role sequence in the parent and labels the run as sequential fallback.

## Skill integration

`ohmycodex-orchestrator` routes qualifying work to Team. Architecture can request explorer/librarian; QA can request independent test analysis; debugging can request explorer and QA; review can request explorer plus reviewer. Implementation may request read-only support but remains the only writer.

Each team run records agent roster, chosen models, fallback substitutions, tasks, evidence, and final consolidation in `.ohmycodex/plans/team-runs/` when writable. The Team installer never overwrites a project-owned agent file and never changes a pre-existing model or permission setting without an explicit user decision.

## Validation

Validate every TOML template for required custom-agent fields, exact model policy, reasoning effort, sandbox mode, and role uniqueness. Test installer behavior against an empty project, a project with existing agent configuration, and a read-only host. Add workflow evaluations for parallel exploration, single-writer implementation, fallback delegation, and sequential fallback.
