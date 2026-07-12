---
name: omc-letgo
description: Let Codex autonomously choose a bounded one-turn workflow or native Goal continuation, including justified capability setup, while preserving native safety gates. Use only when the user explicitly invokes $omc-letgo or /omc-letgo.
---

# Choose and Execute the Workflow

Read and follow `omc-doctor` and `omc-orchestrator`. Read [the Capability Contract](../omc-orchestrator/references/capability-contract.md), [the Loop Contract](../omc-orchestrator/references/loop-contract.md), and [the Workspace Contract](../omc-orchestrator/references/workspace-contract.md) completely.

1. Infer the concrete objective, acceptance, constraints, current repository state, and available Codex controls from the request and evidence. Distinguish user facts from assumptions.
2. Decide whether one bounded workflow turn is enough. If yes, execute that route without creating a Goal or Loop Ledger. If continuation is useful, author a bounded acceptance contract, record every unapproved assumption honestly, choose `X >= 3`, and record why that threshold fits the uncertainty and recovery cost. Do not ask an extra OhMyCodex threshold confirmation.
3. Inspect the current Goal. Never override, replace, or adopt a foreign unfinished Goal. Pass a validated new or matching run, the chosen threshold, assumptions, reason, and Capability Snapshot to `omc-loop`; Loop must not ask for the threshold again.
4. Prefer capabilities already exposed in the task, then existing project commands or installed tools, then documented degradation. When a missing MCP is justified, Codex may initiate the native installation flow without a separate OhMyCodex proposal, but only for a source from an existing registry, declared Skill dependency, user-supplied documented configuration, or authoritative project source. Never invent an endpoint or edit Codex configuration directly. Native trust, authentication, sandbox, administrator, and permission prompts remain mandatory. On failure, record it and use the next valid route.
5. Preserve dirty worktrees and repository conventions. Never substitute text replacement for an unavailable structural rewrite, add a production dependency only for agent convenience, create an agent runtime, or simulate missing Goal or Scheduled controls.

Autonomy does not widen external authority. Immediately before push, deploy, tag, public publication, destructive Git, purchase, credential change, or any other existing release or trust gate, obtain the user's required confirmation or use the native confirmation flow. Never claim a native action succeeded without host evidence. Stop on acceptance-backed completion, a policy block, an explicit user stop, or `X` consecutive materially unchanged blocker turns; do not impose a separate total iteration limit.
