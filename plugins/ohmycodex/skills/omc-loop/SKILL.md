---
name: omc-loop
description: Continue validated work with native Codex Goals, evidence-backed completion, external waits, and a configurable blocker threshold. Use for explicit $omc-loop or /omc-loop invocation, or a validated handoff from another OMC entry.
---

# Continue With Native Controls

Read [the Language Policy](../omc-orchestrator/references/language-policy.md) before responding or writing OhMyCodex artifacts.

Read [the Loop Contract](../omc-orchestrator/references/loop-contract.md), [the Capability Contract](../omc-orchestrator/references/capability-contract.md), and [the Workspace Contract](../omc-orchestrator/references/workspace-contract.md) completely before acting. Locate the plugin-owned `scripts/loop_ledger.py`; use it only as the state adapter defined by the Loop Contract.

1. Build a current Capability Snapshot from host-exposed controls. Inspect the current native Goal before creating a ledger or Goal. A configured CLI feature is not proof that Goal or Scheduled controls are callable in this task.
2. Require a bounded objective and acceptance contract with at least one required item. If either is missing, do not create a Goal; route through `omc-intentgate` to discovery or specification.
3. Classify the invocation as a new direct run, a delegated new run, or a matching resume. For a new direct run, ask once for the consecutive no-progress threshold `X`, offering `3` as the default; reject values below `3` and impose no maximum. Use a threshold supplied by `omc-intentgate` or `omc-letgo` without asking again. Never ask on resume.
4. If a different unfinished Goal exists, create no ledger and do not replace or adopt it. Ask the user to finish, pause, or clear it through native controls. If the Goal names the same run ID, reconcile that run. Treat a Goal without a ledger as foreign. Treat an active ledger without a Goal as orphaned, and create a replacement Goal only when the current invocation targets the same objective.
5. For a new run, write the `preparing` ledger before calling the exposed native Goal-create control. Put the run ID and acceptance contract in the Goal objective. If ledger creation fails, create no Goal. If Goal creation fails, record the bounded failure and leave the ledger non-active. Activate only with the host-confirmed Goal ID. Recover an activation interruption by matching the run ID; never create a duplicate Goal.
6. During one native Goal turn, perform exactly one complete choose, execute, verify, and record cycle. Prefer exposed Codex tools, then existing project commands or installed tools, then the Capability Contract degradation route. Preserve dirty worktrees. Record one strict iteration payload after all tool calls for that turn; never write multiple ledger iterations for one Goal turn.
7. Follow the ledger decision. Complete the native Goal only after `complete`; block it only after `blocked` and only through an exposed host control. For `continue`, leave continuation to the persisted Goal. There is no total iteration, time, or token limit in OhMyCodex.
8. Enter `waiting` only when useful work depends on external state. When Scheduled create/delete controls exist, create a bounded heartbeat that returns to this same task, then record its confirmed ID. Otherwise use a bounded background terminal only for a short-lived process; keep a long wait as a recoverable Goal. Never create a daemon, shell loop, Stop Hook loop, or independent scheduler.
9. Delete a recorded heartbeat through the host before leaving `waiting` or producing any terminal result, and pass the matching deletion confirmation to the ledger. An unchanged external fingerprint remains waiting; a related newer fingerprint may resume. Unrelated or stale external state does not.
10. On user stop, clean the heartbeat and mark the ledger `paused`. Do not claim the native Goal was paused, resumed, edited, or cleared unless the host confirms that operation. For an objective change, update the ledger contract only after a confirmed native Goal edit; otherwise direct the user to the native Goal action.

If Goal support is unavailable, do not emulate continuation. Perform at most the current useful turn, report that automatic continuation and durable threshold recovery are unavailable, and preserve all native permission, sandbox, trust, MCP, Hook, and publication gates.

If the project workspace is not writable, native Goal continuation may still be available, but report that durable audit and custom threshold recovery are reduced. Do not claim the in-project ledger is durable.
