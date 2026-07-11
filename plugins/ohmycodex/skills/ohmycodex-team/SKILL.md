---
name: ohmycodex-team
description: Configure and run OhMyCodex native subagent teams. Use for parallel investigation, multi-file uncertainty, team mode, or delegation to Explorer, Librarian, Architect, QA, Debugger, Implementer, or Reviewer.
---

# OhMyCodex Team

Use Team only when two or more independent investigations can materially improve speed or decision quality. Keep small, local, or single-file work in the parent task.

## Enable local native roles

For a local Codex project, inspect `.codex/agents/` and `.codex/config.toml`. When the user asks to enable Team, run `scripts/install_team_agents.py <repository-root>`. It installs only missing `omc-*.toml` templates and adds `max_threads = 4` and `max_depth = 1` only when the repository has no `[agents]` section.

Never overwrite an existing project-owned agent file or alter an existing `[agents]` section. Explain preserved files and ask before replacing any template.

Use the installed role names directly:

| Role | Use for | Model policy |
| --- | --- | --- |
| `omc-explorer` | Code paths, repository structure, evidence | Luna / low |
| `omc-librarian` | Documentation, APIs, external constraints | Luna / medium |
| `omc-qa` | Tests, acceptance paths, regression risk | Luna / medium |
| `omc-architect` | Contracts, modules, change plan | Sol / xhigh |
| `omc-implementer` | Approved code changes | Terra / high |
| `omc-debugger` | Reproduction and root cause | Terra / high |
| `omc-reviewer` | Correctness, security, and test review | Sol / high |
| `omc-fallback` | A preferred model is unavailable | GPT-5.5 / high |

If a selected model or agent is unavailable, delegate the same role contract to `omc-fallback` and label the result as a fallback. Do not claim automatic fallback occurred.

## Orchestrate a run

1. State the objective, accepted scope, required evidence, and whether the parent must wait for all results.
2. Spawn at most three independent read-only roles in parallel. Typical first wave is Explorer plus Librarian, QA, or Reviewer.
3. Require every role to return: conclusion, file paths or commands as evidence, risks, and recommendation.
4. Consolidate results in the parent. Resolve conflicting findings before selecting architecture or implementation.
5. Run Architect after discovery. Run exactly one Implementer only after the plan is approved. Never run parallel writing agents.
6. Run Reviewer after implementation and verification. Route failures to Debugger or Implementer in a new, bounded task.

If native subagents are unavailable in the current host, perform the same role sequence in the parent task and state that the run used sequential fallback. Do not pretend that model pins applied on ChatGPT Work Web.

When `.ohmycodex/` is writable, create `.ohmycodex/plans/team-runs/<timestamp>.md` with the objective, roles, requested models, fallback substitutions, result summaries, evidence, unresolved risks, and final decision. Read `../ohmycodex-orchestrator/references/workspace-contract.md` before writing it.
