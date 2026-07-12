---
name: omc-intentgate
description: Inspect intent and active Codex capabilities, route to the right OhMyCodex lifecycle stage, and start native continuation only when acceptance is ready. Use only when the user explicitly invokes $omc-intentgate or /omc-intentgate.
---

# Gate Intent Before Continuation

Read [the Language Policy](../omc-orchestrator/references/language-policy.md) before responding or writing OhMyCodex artifacts.

Read and follow `omc-doctor`, then read and follow `omc-orchestrator`. Also read [the Capability Contract](../omc-orchestrator/references/capability-contract.md), [the Loop Contract](../omc-orchestrator/references/loop-contract.md), and [the Workspace Contract](../omc-orchestrator/references/workspace-contract.md) completely.

1. Normalize the user's objective, requested outcome, constraints, repository evidence, and active host controls. Return the selected lifecycle route and why it fits.
2. Establish an acceptance contract before continuation. If acceptance is missing or ambiguous, do not create a Goal or Loop Ledger. Route to `omc-discover`, `omc-spec`, or the applicable planning stage and stop at its approval boundary.
3. Decide whether the bounded request can finish in the current turn or requires continuation. For a matching existing run, reconcile it and do not ask for a threshold again. For a new continuation run, ask once for `X`, the number of consecutive unchanged blocker turns before blocking. Offer `3` as the default, reject `X < 3`, allow any larger integer, and pass the answer to `omc-loop` so Loop does not ask again.
4. Inspect the current Goal before delegation. Never replace or adopt a foreign unfinished Goal. Delegate a validated new or matching run to `omc-loop` with the objective, acceptance, threshold, and Capability Snapshot.

When a missing capability materially blocks the selected route, exhaust existing exposed tools, project commands, and documented degradation routes first. Propose MCP installation at most once per decision and only from an existing registry, a declared Skill dependency, user-supplied documented configuration, or an authoritative project source. Reject an untrusted or invented endpoint. After user acceptance, use Codex-native MCP controls: `codex mcp` on CLI or the exposed connector/dependency flow in an app. Never edit Codex MCP configuration directly. Preserve every native trust, authentication, sandbox, and administrator prompt. If installation fails, record the bounded failure and select the next Capability Contract route.

Text search may locate structural candidates but may not perform or claim a structural rewrite. Do not add a production dependency merely to improve agent tooling. Keep push, deploy, tag, public publication, destructive Git, and other existing external-action confirmations user-controlled.
