# Team mode

English | [简体中文](team-mode.zh-CN.md)

`$omc-team` configures native Codex subagents inside the existing OhMyCodex plugin. It adds no second runtime.

The bundled installer copies only missing templates into `.codex/agents/` and adds safe defaults only when the project has no existing `[agents]` section. It never overwrites project-owned agent files or an existing agent configuration.

| Role | Model policy | Access |
| --- | --- | --- |
| Explorer, Librarian, QA | Luna | Read-only |
| Architect, Reviewer | Sol | Read-only |
| Implementer | Terra | Workspace write |
| Debugger | Terra | Read-only |
| Fallback | GPT-5.5 | Parent policy |

Use Team only for independent investigations. Run at most three read-only roles in the first wave, consolidate in the parent, use one writer for application changes, and review after verification. If native subagents are unavailable, run the same role sequence in the parent and label it sequential fallback; do not claim model pins applied.
