# OMC Native Continuation Design

Status: approved for implementation planning

Date: 2026-07-12

## Goal

Extend OhMyCodex with persistent automatic continuation, explicit intent routing, autonomous operation, capability discovery, optional Codex-native tool installation, and global English/Chinese switching without turning the plugin into a second agent runtime.

The implementation must reuse stable Codex facilities whenever the active surface exposes them. Persisted Goals provide automatic continuation. Scheduled tasks provide delayed wakeups while waiting on external state. Native subagents provide parallel investigation. Skills remain the public workflow interface. MCP configuration remains owned by Codex. Project compilers, type checkers, language servers, and structural tools remain the preferred code intelligence implementations.

The plugin remains one installable OhMyCodex package. It adds no daemon, bundled MCP server, telemetry service, custom model provider, command parser, or independent scheduling runtime.

## Design principles

The native-first rule applies to every capability. OhMyCodex defines engineering policy, acceptance gates, evidence, and routing; Codex performs continuation, scheduling, delegation, permissions, and tool execution.

Automatic does not mean unbounded spinning. A run has no fixed iteration, time, or token limit, but it stops when its acceptance contract is verified, the user stops it, Codex policy prevents further work, or the same evidence-backed blocker repeats for the configured threshold.

Every consequential claim must be tied to current evidence. Git revisions, worktree state, command results, acceptance states, and external wait state are recorded. Evidence captured for an older revision becomes stale when relevant files change.

Tool installation is demand-driven. Existing tools are preferred, Codex-native installation and trust flows remain authoritative, and every missing capability has an explicit degradation path.

## Naming and migration

The plugin and marketplace package retain the `ohmycodex` identity. All public Skill names move from the `ohmycodex-*` prefix to the shorter `omc-*` namespace in the target v0.3.0 release.

| Previous name | Canonical v0.3.0 name |
| --- | --- |
| `ohmycodex-orchestrator` | `omc-orchestrator` |
| `ohmycodex-init` | `omc-init` |
| `ohmycodex-discover` | `omc-discover` |
| `ohmycodex-spec` | `omc-spec` |
| `ohmycodex-architecture` | `omc-architecture` |
| `ohmycodex-implement` | `omc-implement` |
| `ohmycodex-qa` | `omc-qa` |
| `ohmycodex-debug` | `omc-debug` |
| `ohmycodex-refactor` | `omc-refactor` |
| `ohmycodex-review` | `omc-review` |
| `ohmycodex-release` | `omc-release` |
| `ohmycodex-debt` | `omc-debt` |
| `ohmycodex-team` | `omc-team` |

The release adds `omc-loop`, `omc-intentgate`, `omc-letgo`, `omc-doctor`, `omc-cn`, and `omc-en`. The old Skill names are removed rather than retained as shallow aliases. Release notes and the README must call out the breaking invocation rename.

Codex surfaces that resolve Skill mentions from slash input can present `/omc-*` as a convenience. Portable invocation remains `$omc-*` or selection through `/skills`. The plugin does not install deprecated Custom Prompt shims.

## Public interfaces

| Skill | Invocation policy | Interface |
| --- | --- | --- |
| `omc-orchestrator` | Explicit or implicit | Route the current product-engineering stage using existing `.ohmycodex` evidence. |
| `omc-loop` | Explicit only | Start a Goal-backed continuation run for an objective with acceptance criteria and a user-selected no-progress threshold. |
| `omc-intentgate` | Explicit only | Inspect intent and capabilities, route through `omc-orchestrator`, ask for the threshold, and start `omc-loop` when continuation is appropriate. |
| `omc-letgo` | Explicit only | Autonomously decide whether continuation adds value, select the workflow, agents, tools, and justified MCP installation, and choose a threshold only when it starts `omc-loop`. |
| `omc-doctor` | Explicit or delegated | Return a read-only capability snapshot and degradation plan. |
| `omc-cn` | Explicit only | Set global OhMyCodex metadata and workflow language to Simplified Chinese, then request a Codex restart or new task. |
| `omc-en` | Explicit only | Restore the default English metadata and workflow language, then request a Codex restart or new task. |

The existing lifecycle Skills keep their current responsibilities after the rename. Neither IntentGate nor Letgo duplicates stage routing. They call `omc-orchestrator`, and every path that chooses continuation calls `omc-loop`.

## Module shape

The design introduces two internal modules with small interfaces and no resident process.

### Capability Resolver

The Capability Resolver accepts a repository root and a Host Capability Input constructed by the active Skill or orchestrator from tools and policy that Codex actually exposed to the current turn. It returns a normalized Capability Snapshot containing Goal support, Scheduled support, native subagent support, writable roots, approval constraints, configured MCP servers and tools, local code-intelligence tools, Git state, project commands, and supported degradation paths.

The interface is conceptually:

```text
resolve_capabilities(repository, host_capabilities) -> CapabilitySnapshot
```

The Host Capability Input is authoritative for active-turn tools, Goal controls, Scheduled controls, writable roots, and approval policy. A local script cannot infer those capabilities from CLI output. The implementation may supplement the injected input with bounded, read-only probes such as `codex features list`, `codex mcp list`, `command -v`, manifest inspection, and project-script discovery, but those probes describe local configuration and executables only. They must not upgrade an unavailable active-turn tool into an available capability. Probe commands use argument arrays rather than shell interpolation, apply timeouts, redact sensitive environment values, and never print credentials or raw authorization configuration.

### Loop Ledger

The Loop Ledger owns only OhMyCodex run state and evidence. It does not schedule turns, call models, install tools, or prevent Codex from stopping.

Its interface is conceptually:

```text
create_run(objective, acceptance, threshold, baseline, capabilities) -> LoopState
record_iteration(run_id, evidence) -> LoopDecision
record_wait(run_id, external_state, schedule_id) -> LoopState
reconcile_run(run_id, current_repository_state) -> LoopDecision
finish_run(run_id, outcome, evidence) -> LoopState
```

`LoopDecision` is one of `continue`, `wait`, `complete`, `blocked`, or `paused`. The module validates structured input, computes state transitions, and writes state atomically. The model remains responsible for explaining why supplied evidence maps to the objective; the module prevents malformed transitions and inconsistent counters.

The deletion test is intentional. Removing the Capability Resolver would spread probing and fallback logic across every workflow. Removing the Loop Ledger would spread threshold counting, revision reconciliation, and evidence invalidation across every continuation turn. Both modules therefore concentrate meaningful complexity behind small interfaces.

## Continuation lifecycle

Every run starts with an objective and an acceptance contract. If the repository already contains an approved specification, the acceptance contract is derived from it. If no reliable completion definition exists, IntentGate routes to discovery or specification before creating a Goal. Letgo first decides whether the request is answerable or bounded enough to complete in one workflow turn. In that case it creates neither a Goal nor a Loop Ledger. When Letgo selects continuation, it may author a bounded acceptance contract autonomously, but must record its assumptions and may not claim user approval that did not occur.

The following states belong to the Loop Ledger. They do not imply that the native Goal supports an identically named callable transition.

| State | Meaning | Allowed next states |
| --- | --- | --- |
| `preparing` | Resolve capabilities, route the workflow, establish acceptance, and choose the threshold. | `active`, `blocked`, `paused` |
| `active` | Select the next action, execute it, verify the result, and record evidence. | `active`, `waiting`, `complete`, `blocked`, `paused` |
| `waiting` | External state must change before useful work can continue. | `active`, `complete`, `blocked`, `paused` |
| `complete` | Every required acceptance item has current verification evidence. | Terminal |
| `blocked` | The same blocker has reached the threshold or Codex policy prevents safe progress. | `active` after an explicit resume or material external change |
| `paused` | The user or host paused the run. | `active`, terminal after clear |

One ledger iteration maps to exactly one native Goal continuation turn. That turn contains one full choose, execute, verify, and record cycle and may contain multiple tool calls, but it writes only one iteration result. This keeps the configurable no-progress counter in the same unit as the native Goal blocker rule.

`omc-intentgate` and direct `omc-loop` invocation ask the user for the no-progress threshold before each new run. The default is three. The minimum is three because the native Codex Goal contract requires the same blocker to recur for at least three consecutive Goal turns before it can be marked blocked. There is no fixed maximum and no total iteration limit.

When it selects continuation, `omc-letgo` chooses the threshold itself and records its reason. It does not add an OhMyCodex confirmation prompt. Codex sandbox approvals, MCP trust prompts, administrator requirements, Hook trust, and platform restrictions remain in force.

The no-progress count resets when at least one acceptance item improves, a relevant check changes from failing or unknown to passing, a code or configuration change directly advances the objective, new external evidence changes the available decision, or an approved decision removes the blocker. The count increments only when the blocker key, evidence, recommended next action, relevant repository state, and acceptance state remain materially unchanged.

Completion requires current evidence for every required acceptance item. A model statement without a command result, inspection path, or explicit bounded reason that verification is unavailable is not completion evidence.

## Native Goal and Scheduled behavior

When the current surface exposes persisted Goals, `omc-loop` inspects the current Goal before creating one. If no unfinished Goal exists, it writes a `preparing` ledger, creates a Goal whose objective references that run identifier and acceptance contract, then activates the ledger. If Goal creation fails, the ledger records the failure and never becomes active. If Goal creation succeeds but ledger activation is interrupted, the matching run identifier allows resume to finish reconciliation without creating another Goal. If the active Goal contains the same run identifier, `omc-loop` reconciles and resumes that run. If a different unfinished Goal exists, it creates no ledger or replacement Goal and asks the user to finish, pause, or clear the existing Goal through Codex's native controls. Letgo cannot override this host constraint.

An active ledger without an active Goal is an orphaned run. `omc-loop` reconciles its repository state and may create a replacement Goal only when the invocation targets the same objective. An active Goal without a matching ledger is treated as foreign state and is never silently adopted. Tests cover matching resume, conflicting active Goals, orphaned ledgers, foreign Goals, and Goal creation failures that occur before a ledger can be committed.

Automatic continuation is owned by Codex. OhMyCodex calls exposed Goal status tools only to create, inspect, complete, or block the native Goal according to the approved contract. Pause, resume, edit, and clear remain user or host controls unless the active surface explicitly exposes a callable control for them.

When Goal support is unavailable, the plugin does not emulate it with a Stop Hook or shell loop. It performs the current turn, writes whatever evidence the host permits, and reports that automatic continuation is unavailable.

Scheduled heartbeat is used only when useful work depends on external state such as CI, a pull request, a deployment, or a remote job. The heartbeat returns to the same task, checks the recorded condition, and either resumes the Goal or schedules the next bounded check. The schedule is deleted when the condition resolves, the Goal completes or blocks, or the user stops the run.

On surfaces without Scheduled management, a bounded background terminal may watch a short-lived process. A long external wait leaves the Goal recoverable and reports the surface limitation. The plugin does not create a background daemon.

## Capability routing

The Capability Snapshot defines a deterministic preference order.

| Need | Preferred route | Degradation route |
| --- | --- | --- |
| Local text and file discovery | Current Codex search tool, then `rg` | Repository-native search command |
| Definitions, references, and diagnostics | Existing native or MCP LSP tool | Existing project language server, compiler, or type checker |
| Structural query or rewrite | Existing AST tool, then `sg` or ast-grep | Project codemod or a standard parser; textual search may discover candidates but must not perform unsafe structural rewrites |
| External source search | Existing connected code-search MCP | Codex browser or web capability when permitted |
| Official documentation | Existing official documentation MCP | Official documentation site through an available browser or fetch capability |
| Parallel investigation | Native Codex subagents | The same role sequence in the parent turn |
| External wait | Scheduled heartbeat | Bounded background terminal, then recoverable Goal |

The resolver never treats tool absence as proof that a task is impossible until the defined degradation routes have been considered.

MCP installation is demand-driven. IntentGate presents one OhMyCodex installation proposal before invoking the Codex-native flow. Letgo may choose and initiate a justified installation without the additional OhMyCodex proposal. Both modes preserve native authorization and trust prompts. An MCP must come from an existing registry, a Skill dependency declaration, or a documented configuration supplied by the user or an authoritative project source. OhMyCodex does not generate an MCP server or invent an unverified endpoint.

CLI installation uses `codex mcp` rather than editing user configuration directly. App surfaces use their exposed dependency or connector flow. A failed installation records the exact bounded error and selects the next degradation route.

No workflow adds a production dependency merely to improve agent tooling. A repository-local development tool may be installed only when it follows the project's package-manager conventions, is justified by the task, and passes the active Codex permission policy.

## Persistent state and recovery

Native Goal state remains the source of truth for continuation. OhMyCodex state lives under the project workspace:

```text
.ohmycodex/
  runtime/
    loops/
      <run-id>.json
  plans/
    loop-runs/
      <run-id>.md
```

Each run receives a unique identifier so concurrent tasks never write the same state file. The JSON file stores current machine state; the Markdown file stores the compact human audit trail.

A representative state shape is:

```json
{
  "schema_version": 1,
  "run_id": "20260712T120000Z-a1b2c3",
  "status": "active",
  "entrypoint": "omc-intentgate",
  "objective": "Implement the approved checkout retry behavior",
  "goal_id": "host-owned-or-null",
  "threshold": 3,
  "no_progress_count": 0,
  "blocker_key": null,
  "baseline": {
    "git_head": "abc123",
    "worktree_fingerprint": "sha256:..."
  },
  "acceptance": [],
  "capability_snapshot": {},
  "scheduled_task_id": null,
  "last_iteration": null,
  "updated_at": "2026-07-12T12:00:00Z"
}
```

The state writer uses JSON parsing and atomic replacement. It never constructs JSON through ad hoc string concatenation. The audit Markdown records the action, tool or exact command, result, material progress, blocker, residual risk, and next action for each iteration. It does not copy complete logs when a concise evidence reference is sufficient.

On resume, the Loop Ledger compares the current Git revision and worktree fingerprint with the recorded baseline. Relevant external changes mark affected verification evidence stale. The run then refreshes its acceptance state before taking another action. A user-authorized objective change updates the contract and, only when the host exposes the required control, the native Goal; otherwise the user performs the native `/goal edit` action before continuation. A user stop cancels the heartbeat and marks the ledger paused. The user then pauses or clears the Goal through native UI or `/goal` controls. OhMyCodex never claims that the native Goal was paused, edited, resumed, or cleared without host confirmation.

If the project is not writable, continuation may still use a native Goal, but the plugin must state that durable audit and custom threshold recovery are reduced. If Git is unavailable, file and acceptance fingerprints replace revision identity and the evidence record labels the weaker guarantee.

## Language switching

English is the package default. The plugin includes structured translation catalogs rather than duplicate Skills:

```text
plugins/ohmycodex/assets/locales/en.json
plugins/ohmycodex/assets/locales/zh-CN.json
```

Every catalog covers `display_name`, `short_description`, and `default_prompt` for all public Skills. It also covers the plugin manifest's top-level description and its translatable interface fields: `displayName`, `shortDescription`, `longDescription`, and `defaultPrompt`. Stable identifiers, version, paths, category values, URLs, and developer identity are never translated. A deterministic standard-library script validates full coverage and materializes the selected catalog into the plugin-owned `agents/openai.yaml` files and `.codex-plugin/plugin.json` using structured parsers.

`omc-cn` atomically applies Simplified Chinese metadata, writes the global OhMyCodex preference to `$CODEX_HOME/ohmycodex/preferences.json`, and tells the user to restart Codex or start a new task. `omc-en` performs the inverse operation and restores the checked-in English default. Neither command restarts Codex itself.

Every OMC Skill points to one shared language-policy reference. That reference instructs the workflow to read `$CODEX_HOME/ohmycodex/preferences.json` when the host permits it, default to English when the file is absent or unavailable, and use the selected language for conversation output and generated OhMyCodex artifacts. An explicit language instruction in the current task takes precedence. This keeps language behavior in one implementation while each Skill exposes the same small interface. The setting does not change the rest of the Codex UI, other plugins, or application source files.

The locale writer validates all target files before the first replacement and treats the preference, Skill YAML files, and plugin manifest as one transaction. It rolls back the batch if any write fails. If the active surface does not expose a writable installed-plugin root or Codex home preference location, the command changes nothing and reports that global language switching is unavailable there. If a plugin upgrade restores English metadata while the saved preference remains Chinese, `omc-doctor` reports the mismatch and recommends rerunning `omc-cn`. No SessionStart Hook mutates a newly upgraded plugin automatically.

## Permissions and safety

`omc-loop`, `omc-intentgate`, `omc-letgo`, `omc-cn`, and `omc-en` disallow implicit invocation in `agents/openai.yaml`. Their side effects require explicit Skill selection. Existing lifecycle Skills may retain implicit invocation when their descriptions have narrow, unambiguous triggers.

Letgo grants autonomy over OhMyCodex policy choices, not over Codex security controls. It cannot change administrator requirements, bypass the sandbox, suppress native trust prompts, broaden writable roots, expose secrets, or authorize external publication. Existing release rules continue to require explicit user control immediately before pushes, deployments, tags, or public publication.

Dirty worktrees are preserved. A loop records its baseline and works with user changes rather than resetting, discarding, or replacing them. Locale commands modify only plugin-owned metadata and the explicit global OhMyCodex preference.

Capability probes are read-only. They use timeouts and bounded output. Environment variables whose names or values indicate credentials are never included in reports or persisted snapshots.

## Surface behavior

| Surface | Expected behavior |
| --- | --- |
| Codex Desktop | Skill mention entry points, native Goals when exposed, Scheduled heartbeat, plugin metadata switching after restart, project artifacts when writable, and native subagents. |
| Codex CLI | `$omc-*` and `/skills` entry points, native `/goal` or Goal tools when exposed, `codex mcp` management, native subagents, and no Scheduled management UI. |
| Codex IDE extension | `$omc-*` and `/skills` entry points, available Goal and subagent behavior, project artifacts, and no Scheduled management UI. |
| ChatGPT Work Web | Installed Skill invocation and Scheduled tasks when enabled, but no claim of local project files, local commands, project-local agent templates, or plugin metadata rewriting. |

Every capability claim is conditional on the active surface and workspace policy. `omc-doctor` reports the observed environment rather than inferring parity from another surface.

## Validation strategy

Static validation requires exactly nineteen canonical `omc-*` Skills, matching folder and frontmatter names, complete `agents/openai.yaml` metadata, complete locale catalogs, explicit invocation policy on consequential entry points, and no legacy `ohmycodex-*` references outside migration documentation. The plugin remains free of bundled MCP, app, Hook, telemetry, and daemon declarations.

Module tests exercise injected Host Capability Input validation, Capability Resolver normalization and degradation selection, Loop Ledger transition validity, Goal-turn-aligned threshold enforcement, progress reset, blocker counting, atomic state writes, stale-revision invalidation, locale coverage across Skill and plugin metadata, locale rollback, and English-to-Chinese-to-English round trips.

Behavior evaluations exercise IntentGate threshold prompting, missing acceptance routing, Letgo choosing no loop for a bounded request, Letgo choosing a Goal for continuing work, matching and conflicting active Goals, orphaned Goal and ledger state, native permission preservation, MCP installation fallback, LSP and AST degradation, external waiting, heartbeat cleanup, dirty-worktree preservation, user stop without fabricated Goal control, stale evidence, and evidence-backed completion.

Integration tests run against temporary fixture repositories and fake Codex capability output. They do not install a real MCP, create a real Scheduled task, alter the user's Codex configuration, or call an external model. A manual Codex Desktop smoke test verifies Skill discovery, default English descriptions, slash-to-Skill mention behavior where supported, the `omc-cn` restart message, and Goal-backed continuation.

## Acceptance criteria

| Area | Required result |
| --- | --- |
| Naming | All public Skills use the `omc-*` namespace; old names no longer invoke a Skill after upgrade. |
| Continuation | A supported surface uses native persisted Goals and never a custom Stop Hook or shell loop for automatic continuation. |
| Goal conflicts | A matching Goal resumes its ledger; a foreign unfinished Goal is never replaced or silently adopted; interrupted registration reconciles by run identifier. |
| Threshold | IntentGate and direct Loop ask for `X >= 3`; Letgo selects and records `X` only when it chooses continuation; there is no total iteration cap. |
| Progress | Repeated identical blockers increment the counter, material evidence resets it, and reaching `X` blocks the Goal. |
| Completion | Every required acceptance item has current evidence tied to the relevant repository state. |
| Waiting | External waits use a same-task Scheduled heartbeat when available and clean it up on every terminal outcome. |
| Tooling | Existing Codex, project, LSP, AST, search, and MCP capabilities are preferred before installation or fallback. |
| Installation | MCP changes use Codex-native flows and preserve native authorization and policy. |
| Recovery | Resume reconciles Git and worktree changes and invalidates stale evidence. |
| Language | English is default; `omc-cn` and `omc-en` switch all OMC metadata atomically and request a restart. |
| Safety | Letgo cannot bypass Codex permissions, external release confirmation, or worktree preservation rules. |
| Portability | Unsupported capabilities degrade honestly without fabricated success or a replacement runtime. |

## Release boundary

The target release is v0.3.0. It includes the hard Skill rename, the six new entry-point Skills, the two internal modules, locale catalogs, workspace-contract updates, documentation, validation, tests, and evaluation scenarios described above.

The release does not include an MCP server, LSP server, AST engine, background daemon, custom slash-command parser, telemetry, cross-provider model router, Hashline editor, or tmux visualization. Those implementations remain owned by Codex, the project, or an existing external tool.
