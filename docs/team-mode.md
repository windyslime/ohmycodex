# Team mode

`$ohmycodex-team` brings native Codex subagents into the existing OhMyCodex plugin. It does not add a second plugin or a separate runtime.

## Enable locally

Ask the Team skill to enable the current repository. It runs its bundled installer, which copies only missing templates into `.codex/agents/` and creates `[agents]` defaults only if the project has no existing `[agents]` section.

| Role | Model | Reasoning | Access |
| --- | --- | --- | --- |
| Explorer | `gpt-5.6-luna` | low | Read-only |
| Librarian | `gpt-5.6-luna` | medium | Read-only |
| QA | `gpt-5.6-luna` | medium | Read-only |
| Architect | `gpt-5.6` (Sol) | xhigh | Read-only |
| Implementer | `gpt-5.6-terra` | high | Workspace write |
| Debugger | `gpt-5.6-terra` | high | Read-only |
| Reviewer | `gpt-5.6` (Sol) | high | Read-only |
| Fallback | `gpt-5.5` | high | Parent policy |

## Run safely

Use Team only for independent, multi-file, uncertain, or cross-disciplinary tasks. Run no more than three read-only agents in the first wave. The parent consolidates evidence, Architect follows discovery, one Implementer writes approved changes, and Reviewer follows verification.

If a preferred agent cannot launch, request `omc-fallback` with the original role contract. If the host cannot load local native agents, preserve the same role sequence in the parent task and record a sequential fallback; model pins do not apply in that mode.
