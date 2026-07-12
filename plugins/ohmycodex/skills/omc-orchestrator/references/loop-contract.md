# Loop Contract

Use this contract whenever an OhMyCodex workflow starts, resumes, waits for, or closes a continuation run.

## Ownership and limits

Codex owns automatic continuation. A persisted native Goal is the source of truth for whether another continuation turn runs. The Loop Ledger owns only OhMyCodex state, acceptance evidence, blocker counting, and audit recovery. Scheduled owns delayed wakeups only while useful work depends on external state. The ledger never calls a model, Goal control, scheduler, package installer, or MCP.

One ledger iteration is exactly one native Goal continuation turn: choose, execute, verify, and record. The turn may use multiple tools or commands, but it records one iteration payload.

The no-progress threshold is an integer `X >= 3`, defaults to `3`, has no maximum, and counts consecutive turns with the same evidence-backed blocker. Direct `omc-loop` and `omc-intentgate` ask once before each new run. `omc-letgo` chooses `X` and records its reason. There is no total logical iteration, time, or token limit. A run ends only when current evidence satisfies acceptance, the user or host pauses it, policy prevents safe progress, or the repeated blocker reaches `X`.

## Lifecycle

| Ledger state | Meaning | Allowed next states |
| --- | --- | --- |
| `preparing` | The run exists but is not bound to a confirmed native Goal. | `active`, `blocked`, `paused` |
| `active` | A Goal turn may execute and record one iteration. | `active`, `waiting`, `complete`, `blocked`, `paused` |
| `waiting` | An external condition must change before useful work continues. | `active`, `complete`, `blocked`, `paused` |
| `complete` | Every required acceptance item has current pass evidence. | Terminal |
| `blocked` | Policy blocks immediately, or one technical blocker reached `X`. | `active` after an explicit resume or related material external change |
| `paused` | The user or host paused the run. | `active` after an explicit resume |

For a new run, write `preparing` first, create a Goal whose objective names the run ID and acceptance contract, then call `activate_run` with the host-confirmed Goal ID. A failed Goal creation must never produce an active ledger. Retrying activation with the same Goal ID is idempotent; a different Goal ID is rejected.

Before creating anything, inspect the current Goal. Resume a matching run ID. Do not replace a different unfinished Goal, and never adopt a Goal that has no matching ledger. An active ledger without a Goal is orphaned; reconcile it and create a replacement Goal only when the invocation targets the same objective. If Goal support is unavailable, perform at most the current turn and report that automatic continuation is unavailable; do not emulate it with a shell loop, Stop Hook, daemon, or custom scheduler.

Native Goal controls own pause, resume, edit, clear, complete, and block. The ledger may record a user request or observed workflow state, but it must never claim the corresponding native transition until the host confirms it. Native Goal state remains authoritative.

## Python interface

`LoopState` is the strict JSON object persisted for a run. `LoopDecision` is `{"kind", "state", "reason", "material_progress"}`, where `kind` is `continue`, `wait`, `complete`, `blocked`, or `paused` and `state` is a `LoopState`.

```text
LoopLedger(repository)
  .create_run(objective, acceptance, threshold, baseline, capabilities,
              entrypoint, assumptions=(), threshold_reason=None) -> LoopState
  .load_run(run_id) -> LoopState
  .activate_run(run_id, goal_id) -> LoopState
  .record_iteration(run_id, evidence) -> LoopDecision
  .record_wait(run_id, external_state, schedule_id) -> LoopState
  .reconcile_run(run_id, current_repository_state, *, external_state=None,
                 resume_signal=None, cleanup_confirmation=None) -> LoopDecision
  .finish_run(run_id, outcome, evidence, *, cleanup_confirmation=None) -> LoopState
```

All objects reject unknown or missing required fields, duplicate JSON keys, non-standard numeric constants, invalid timestamps, and inconsistent cross-field state. Timestamps are timezone-aware ISO-8601 values. Run IDs match `YYYYMMDDTHHMMSSZ-<12 lowercase hex>`.

## JSON payloads

Repository identity uses one of these exact shapes. File fingerprints provide the explicitly weaker fallback when Git is unavailable.

```json
{"git_head":"abc123","worktree_fingerprint":"sha256:...","evidence_strength":"git"}
```

```json
{"git_head":null,"worktree_fingerprint":"sha256:...","evidence_strength":"files","file_fingerprint":"sha256:...","acceptance_fingerprint":"sha256:..."}
```

The `create` payload is:

```json
{
  "objective": "Implement the approved behavior",
  "acceptance": [
    {"id": "AC-1", "description": "Required tests pass", "required": true}
  ],
  "threshold": 3,
  "baseline": {"git_head": "abc123", "worktree_fingerprint": "sha256:...", "evidence_strength": "git"},
  "capabilities": {"schema_version": 1},
  "entrypoint": "omc-loop",
  "assumptions": [],
  "threshold_reason": "User selected the no-progress threshold"
}
```

`entrypoint` is `omc-loop`, `omc-intentgate`, or `omc-letgo`. `acceptance` must be non-empty and contain at least one required item. `assumptions` is optional and defaults to `[]`. `threshold_reason` defaults to the user-selected reason for direct modes, but is mandatory for `omc-letgo`.

The `activate` payload is `{"goal_id":"host-confirmed-id"}`.

The `iterate` payload is exact and represents one Goal turn:

```json
{
  "iteration_number": 1,
  "iteration_id": "turn-0001",
  "observed_at": "2026-07-12T12:00:00Z",
  "action": "Run the required checks",
  "tools": ["exec_command"],
  "commands": [
    {"id": "cmd-1", "argv": ["python3", "-m", "unittest"], "exit_code": 0, "result": "passed", "summary": "Required tests passed"}
  ],
  "repository_state": {"git_head": "abc123", "worktree_fingerprint": "sha256:...", "evidence_strength": "git"},
  "acceptance_updates": [
    {
      "id": "AC-1",
      "status": "passed",
      "evidence": [
        {"id": "ev-1", "kind": "command", "summary": "Required tests passed", "reference": "cmd-1", "repository_fingerprint": "sha256:...", "external_fingerprint": null, "decision_id": null}
      ]
    }
  ],
  "check_updates": [],
  "progress_claim": {"kind": "none", "reason": "", "evidence_ids": []},
  "blocker": null,
  "residual_risks": [],
  "next_action": "Evaluate remaining acceptance"
}
```

Command `result` is `passed`, `failed`, or `unavailable`. Evidence `kind` is `command`, `inspection`, `external`, `user_decision`, or `bounded_unavailable`. Acceptance and check status is `unknown`, `failed`, `passed`, or `bounded_unavailable`. A check update has the same shape as an acceptance update plus `description`.

`progress_claim.kind` is `none`, `repository_change`, `external_change`, or `user_decision`. A non-`none` claim requires a reason and IDs of evidence in the same iteration. A blocker is either null or:

```json
{"kind":"technical","key":"stable-key","summary":"Bounded explanation","evidence_ids":["cmd-1"],"next_action":"Specific next action"}
```

Blocker `kind` is `technical` or `policy`; its evidence IDs must resolve inside the iteration. Iteration numbers are contiguous. Reusing the immediately previous iteration ID with an identical canonical payload is idempotent; reusing it with different content, or reusing any older ID, is rejected.

The `wait` payload is:

```json
{
  "external_state": {
    "strategy": "scheduled",
    "condition": "Wait for required CI checks",
    "fingerprint": "ci:pending",
    "observed_at": "2026-07-12T12:05:00Z",
    "next_action": "Reconcile CI state"
  },
  "schedule_id": "host-confirmed-schedule-id"
}
```

Strategy is `scheduled`, `background_terminal`, or `recoverable_goal`. `scheduled` requires a schedule ID; other strategies require `null`.

The `reconcile` payload is:

```json
{
  "current_repository_state": {"git_head": "abc123", "worktree_fingerprint": "sha256:...", "evidence_strength": "git"},
  "external_state": null,
  "resume_signal": null,
  "cleanup_confirmation": null
}
```

An external state uses the wait shape. A resume signal is `{"kind":"user","id":"stable-id","reason":"...","observed_at":"..."}`; `kind` may be `user` or `host`. Cleanup confirmation is `{"schedule_id":"...","deleted":true,"observed_at":"..."}` and must match the recorded schedule.

The `finish` payload is:

```json
{
  "outcome": {"kind": "paused", "reason": "The user stopped the run"},
  "evidence": {
    "observed_at": "2026-07-12T12:07:00Z",
    "action": "Honor the stop request",
    "tools": ["goal_control"],
    "commands": [],
    "residual_risks": ["Acceptance remains incomplete"],
    "next_action": "Resume only after an explicit signal"
  },
  "cleanup_confirmation": null
}
```

Finish outcome is `complete`, `blocked`, or `paused`. `complete` is rejected unless every required acceptance item has current pass evidence. A scheduled wait requires confirmed deletion before any terminal finish.

`LoopState` always contains these fields:

```text
schema_version, run_id, revision, status, entrypoint, objective, assumptions,
goal_id, threshold, threshold_reason, iteration_count, iteration_ids,
no_progress_count, blocker_key, blocker_signature, baseline, repository_state,
acceptance, checks, capability_snapshot, scheduled_task_id, external_wait,
last_iteration, outcome, closed_at, audit, created_at, updated_at
```

Stored acceptance/check evidence adds a computed Boolean `stale`. `last_iteration` adds `payload_hash`, `material_progress`, `decision_kind`, and `decision_reason`. Callers must treat these as ledger outputs, not user-authored iteration fields.

## Evidence, progress, and blockers

Passing required acceptance needs at least one non-stale item whose repository fingerprint equals the current worktree fingerprint. `bounded_unavailable` records a real verification limit but never passes required acceptance. A repository revision or file/acceptance fingerprint change invalidates affected stored verification and returns previously passed items to `unknown` until refreshed.

Material progress is computed, not trusted. It occurs when acceptance or a relevant check newly passes, an actual repository change has a same-iteration evidence-backed `repository_change` claim, a new external fingerprint changes the available decision, or a new explicit decision ID removes a blocker. Repeated external fingerprints, repeated decision IDs, unsupported claims, or repository changes without cited evidence do not reset the counter.

A technical blocker signature covers its kind, key, summary, normalized referenced evidence, next action, current repository state, and acceptance states. The first occurrence sets the count to `1`; an identical consecutive signature increments it; changed evidence, next action, repository state, or acceptance state starts a new sequence. Material progress or no blocker resets the count to `0`. Reaching `X` returns `blocked`. A current evidence-backed policy blocker blocks immediately and does not consume the technical threshold.

Completion is decided before blocker counting and requires current evidence for all required acceptance items.

## Waiting and reconciliation

Create a Scheduled heartbeat only for a genuine external wait and return it to the same task. `record_wait` records host-created schedule identity; it does not create the schedule. An unchanged external fingerprint returns `wait`. A changed fingerprint or explicit resume must be newer than the recorded wait. Before leaving a scheduled wait, delete the schedule through the host and supply matching cleanup confirmation; clear the recorded schedule on every terminal result.

Reconciliation compares current repository identity with the ledger and marks old evidence stale. Active runs accept repository reconciliation only. Waiting runs require the same strategy and condition they recorded. Blocked runs reactivate only after an explicit resume or a newer, related external fingerprint that differs from the blocker's bound evidence. Unrelated external changes do nothing. Paused runs require an explicit resume signal. Reactivation resets blocker identity and count.

## Persistence, audit, and recovery

Persist machine state and human audit separately:

```text
.ohmycodex/runtime/loops/<run-id>.json
.ohmycodex/plans/loop-runs/<run-id>.md
```

Use per-run locking, exclusive run creation, repository-contained paths, and symlink-escape checks. Write JSON with a same-directory temporary file, flush, `fsync`, atomic replacement, and directory synchronization. A failed replacement must leave the previous JSON parseable and unchanged.

Every semantic change first commits JSON with a hashed pending audit event, then appends one Markdown block with matching begin/end markers, then atomically clears `audit.pending`. Every mutating operation repairs an interrupted audit idempotently; read-only `load_run` reports pending state without writing. A complete matching block is reused, an incomplete matching block is replaced, and conflicting, duplicated, out-of-order, or invalid-hash markers are rejected.

Each audit event records action, tools, exact command arguments, bounded result summary, material-progress decision, blocker, residual risks, next action, and concise evidence references. Never copy raw `stdout`, `stderr`, logs, or raw output into the audit.

## CLI mapping

The adapter form is `loop_ledger.py --repository PATH <subcommand> ...`. Input-taking commands read exactly one JSON object with `json.load` from `--input FILE` (use `-` for stdin), call exactly one public ledger method, and emit exactly one JSON result to stdout.

| Subcommand | Positional input | JSON payload | Method | Output |
| --- | --- | --- | --- | --- |
| `create` | none | create payload | `create_run` | `LoopState` |
| `activate` | `--run-id RUN_ID` | activate payload | `activate_run` | `LoopState` |
| `iterate` | `--run-id RUN_ID` | iteration payload | `record_iteration` | `LoopDecision` |
| `wait` | `--run-id RUN_ID` | wait payload | `record_wait` | `LoopState` |
| `reconcile` | `--run-id RUN_ID` | reconcile payload | `reconcile_run` | `LoopDecision` |
| `finish` | `--run-id RUN_ID` | finish payload | `finish_run` | `LoopState` |
| `show` | `--run-id RUN_ID` | none | `load_run` | `LoopState` |

CLI errors go to stderr and return non-zero without a success JSON object. The CLI remains a state adapter; it must never drive Goal, Scheduled, model, MCP, or installation behavior.
