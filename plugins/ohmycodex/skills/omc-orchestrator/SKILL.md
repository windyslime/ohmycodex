---
name: omc-orchestrator
description: Route AI-assisted MVP work through the OhMyCodex engineering workflow. Use when a user has an app idea, asks what to do next, wants an end-to-end plan, or needs to continue a project with `.ohmycodex` artifacts.
---

# OhMyCodex Orchestrator

Inspect `.ohmycodex/` and the repository before choosing a workflow. If the workspace is absent and writes are available, invoke the initialization flow before routing. If writes are unavailable, state that the session is conversation-only.

Classify the request into one primary stage:

| Request | Route |
| --- | --- |
| Idea, audience, outcome, constraints | `omc-discover` |
| Two or more independent investigations, multi-file uncertainty, or cross-disciplinary work | `omc-team` |
| MVP boundary, acceptance criteria, non-goals | `omc-spec` |
| Modules, data contracts, technical approach | `omc-architecture` |
| Approved work to change code | `omc-implement` |
| Tests, build, acceptance validation | `omc-qa` |
| Broken, failing, slow, unexpected behavior | `omc-debug` |
| Simplify, untangle, reduce duplication | `omc-refactor` |
| Inspect a diff, branch, or implementation | `omc-review` |
| Ship, tag, rollback, release decision | `omc-release` |
| Record a deliberate shortcut | `omc-debt` |

Return the selected stage, the evidence used, the artifact to read or create, and the next decision required. Do not duplicate a specialist workflow. Do not implement code until the applicable specification and plan are approved.

Route to Team only when independent read-heavy work can improve the parent decision. Keep a single writer for implementation, configuration, dependency, Git, and release changes.

Read [the workspace contract](references/workspace-contract.md) before creating or updating project artifacts.

The explicit continuation entries wrap this router: `omc-intentgate` inspects capabilities and requires acceptance before selecting a route, `omc-letgo` chooses between a bounded current turn and continuation, and `omc-loop` adapts a validated contract to native Goals. When already called from one of those entries, return the selected lifecycle route without invoking the entry again.
