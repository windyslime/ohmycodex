# OMC Native Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `implement` with `tdd` to execute this plan task-by-task. The Superpowers execution skills are not installed in this workspace, so keep one primary writer and use read-only subagents for focused investigation and review. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Release OhMyCodex v0.3.0 with native Goal-backed continuation, capability-aware routing, autonomous intent handling, and transactional English/Simplified Chinese metadata switching.

**Architecture:** Keep Codex in control of Goals, Scheduled tasks, permissions, subagents, and MCP installation. Add three dependency-free Python modules behind small interfaces: a read-only Capability Resolver, a state-only Loop Ledger, and a transactional Locale Manager. Skills call those modules and describe host-control behavior; no script acts as an agent runtime.

**Tech Stack:** Codex Skills and `agents/openai.yaml`, Python 3.12+ standard library, `unittest`, JSON-compatible YAML metadata, GitHub Actions.

## Global Constraints

- Keep the plugin and marketplace identity `ohmycodex`; hard-rename all public Skills to `omc-*` with no compatibility aliases.
- Release base version is `0.3.0`; a local cachebuster may be appended only by the official plugin update helper after all validation passes.
- English is the checked-in default; locale switching changes only plugin-owned translatable metadata and `$CODEX_HOME/ohmycodex/preferences.json`.
- A continuation run has no total iteration, time, or token limit. The no-progress threshold is `X >= 3`, defaults to `3`, and counts consecutive native Goal turns with the same evidence-backed blocker.
- Direct `omc-loop` and `omc-intentgate` ask for `X` once per new run. `omc-letgo` chooses and records `X` without an extra OhMyCodex confirmation.
- Host Capability Input is authoritative for active Goal, Scheduled, subagent, permission, and exposed-tool support. CLI probes can supplement configuration facts but cannot promote unavailable host capabilities.
- Use Scheduled heartbeat only for external waits. Never add a daemon, Stop Hook loop, shell loop, custom command parser, telemetry, bundled MCP/LSP/AST server, custom model provider, or independent scheduler.
- Prefer exposed Codex tools, then installed project or local tools, then documented degradation routes. Text search may discover structural candidates but must never masquerade as a structural rewrite.
- Never bypass Codex sandbox, trust, administrator, MCP installation, Hook, or publication confirmations.
- Use only the Python standard library. Do not add PyYAML or a production dependency for agent tooling.
- Preserve dirty worktrees and project-owned configuration. Do not rewrite the frozen v0.2 design/plan documents or the v0.3 migration table that intentionally records old names.
- Every focused implementation commit must pass its targeted tests and `python3 scripts/validate_plugin.py`.

---

## File Map

`plugins/ohmycodex/scripts/capability_resolver.py` owns host-input validation, bounded read-only probes, project command discovery, redaction, and deterministic capability routes.

`plugins/ohmycodex/scripts/loop_ledger.py` owns strict run-state validation, atomic JSON persistence, audit repair, blocker counting, evidence freshness, reconciliation, and state decisions. It never calls a Goal or scheduler.

`plugins/ohmycodex/scripts/locale_manager.py` owns catalog validation, status inspection, transaction journaling, rollback/recovery, metadata materialization, and the global preference file.

`plugins/ohmycodex/skills/omc-orchestrator/references/{workspace-contract,capability-contract,loop-contract,language-policy}.md` are the shared reference layer. Each Skill keeps only its own ordered steps and points to the relevant contract.

`plugins/ohmycodex/assets/locales/{en,zh-CN}.json` are the single source of truth for 19 Skill interfaces and five translatable manifest fields.

`tests/test_capability_resolver.py`, `tests/test_loop_ledger.py`, and `tests/test_locale_manager.py` exercise the three script interfaces. `tests/test_continuation_contracts.py` and `tests/test_continuation_integration.py` exercise static Skill contracts and host-control decisions without claiming to test Codex internals.

### Task 1: Canonical `omc-*` Namespace and v0.3 Package Metadata

**Files:**
- Rename: `plugins/ohmycodex/skills/ohmycodex-*` to `plugins/ohmycodex/skills/omc-*` for all 13 existing Skills
- Modify: all renamed `SKILL.md` and `agents/openai.yaml` files
- Modify: `plugins/ohmycodex/.codex-plugin/plugin.json`
- Modify: `scripts/validate_plugin.py`
- Modify: `tests/test_install_team_agents.py`
- Test: `tests/test_plugin_contract.py`

**Interfaces:**
- Produces: exactly 13 renamed lifecycle Skills with folder/frontmatter/default-prompt agreement and explicit `policy.allow_implicit_invocation: true`
- Produces: plugin base version `0.3.0` while retaining manifest name and marketplace name `ohmycodex`; the validator accepts one optional `+codex.*` cachebuster suffix
- Preserves: Team installer behavior and the eight existing `omc-*.toml` role templates

- [ ] **Step 1: Add a failing namespace contract test**

```python
class PluginContractTests(unittest.TestCase):
    def test_existing_skills_use_only_the_omc_namespace(self) -> None:
        expected = {
            "omc-orchestrator", "omc-init", "omc-discover", "omc-spec",
            "omc-architecture", "omc-implement", "omc-qa", "omc-debug",
            "omc-refactor", "omc-review", "omc-release", "omc-debt", "omc-team",
        }
        discovered = {path.name for path in SKILLS.iterdir() if (path / "SKILL.md").is_file()}
        self.assertEqual(discovered, expected)
        self.assertFalse(any(name.startswith("ohmycodex-") for name in discovered))
```

- [ ] **Step 2: Run the targeted test and confirm it is red**

Run: `python3 -m unittest tests.test_plugin_contract.PluginContractTests.test_existing_skills_use_only_the_omc_namespace -v`

Expected: failure showing the 13 current `ohmycodex-*` directories.

- [ ] **Step 3: Rename the directories and canonical references**

Use non-interactive `mv` for the directory moves. Update every renamed `SKILL.md` frontmatter name, orchestrator route, internal handoff, workspace-contract relative path, and `$skill` default prompt. Do not change the Team role filenames or role names.

Every renamed metadata file must use this structured shape so later locale switching can parse it with `json.loads`:

```json
{
  "interface": {
    "display_name": "OhMyCodex Orchestrator",
    "short_description": "Route an AI-assisted MVP workflow",
    "default_prompt": "Use $omc-orchestrator to choose the right engineering workflow."
  },
  "policy": {
    "allow_implicit_invocation": true
  }
}
```

- [ ] **Step 4: Update the manifest, validator, and Team installer import**

Set the manifest version to `0.3.0`, change its three starter prompts to canonical `$omc-*` names, update `REQUIRED_SKILLS`, update `TEAM_AGENTS`, and point the installer test to `skills/omc-team/scripts/install_team_agents.py`. Extend the validator to reject old Skill directories and require the explicit invocation policy. Validate the version with `version.partition("+")[0] == "0.3.0"` and reject multiple or non-`codex.` metadata suffixes so the final official cachebuster remains valid.

- [ ] **Step 5: Run namespace and existing tests**

Run: `python3 -m unittest tests.test_plugin_contract tests.test_install_team_agents -v`

Expected: all namespace and installer tests pass.

Run: `python3 scripts/validate_plugin.py`

Expected: `OhMyCodex validation passed.`

- [ ] **Step 6: Validate all 13 Skills with the official quick validator**

Run once per directory:

```bash
for skill in plugins/ohmycodex/skills/omc-*; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

Expected: every Skill reports valid.

- [ ] **Step 7: Commit the breaking namespace migration**

```bash
git add plugins/ohmycodex scripts/validate_plugin.py tests
git commit -m "refactor!: rename public skills to omc namespace"
```

### Task 2: Capability Resolver and `omc-doctor`

**Files:**
- Create: `plugins/ohmycodex/scripts/capability_resolver.py`
- Create: `plugins/ohmycodex/skills/omc-doctor/SKILL.md`
- Create: `plugins/ohmycodex/skills/omc-doctor/agents/openai.yaml`
- Create: `plugins/ohmycodex/skills/omc-orchestrator/references/capability-contract.md`
- Test: `tests/test_capability_resolver.py`
- Modify: `tests/test_plugin_contract.py`
- Modify: `scripts/validate_plugin.py`

**Interfaces:**
- Consumes: `resolve_capabilities(repository: Path, host_capabilities: Mapping[str, object], *, runner, which, timeout_seconds) -> CapabilitySnapshot`
- Produces: `CapabilitySnapshot.as_dict() -> dict[str, object]`
- CLI: `capability_resolver.py --repository PATH --host-input FILE [--no-local-probes]`
- Preserves: host booleans as authoritative; probes report configuration only

- [ ] **Step 1: Write the first red host-authority test**

```python
def test_local_goal_feature_cannot_upgrade_missing_host_controls(self) -> None:
    host = valid_host_input(goal=False)
    snapshot = resolve_capabilities(
        self.repository,
        host,
        runner=fake_runner({("codex", "features", "list"): ProbeResult(0, "goals stable true\n")}),
    ).as_dict()
    self.assertFalse(snapshot["continuation"]["available"])
    self.assertEqual(snapshot["continuation"]["source"], "host")
```

- [ ] **Step 2: Run that test and confirm import failure**

Run: `python3 -m unittest tests.test_capability_resolver.CapabilityResolverTests.test_local_goal_feature_cannot_upgrade_missing_host_controls -v`

Expected: failure because `capability_resolver.py` does not exist.

- [ ] **Step 3: Implement strict host normalization and the snapshot interface**

Define frozen `ProbeResult` and `CapabilitySnapshot` dataclasses. Accept only schema version `1`, absolute writable roots, known control keys, known approval fields, and tool entries with allowlisted capability names. Reject booleans where an integer is required and unknown keys at every strict object level.

Return this stable top-level shape:

```python
{
    "schema_version": 1,
    "surface": surface,
    "continuation": continuation,
    "scheduled": scheduled,
    "subagents": subagents,
    "approval": approval,
    "workspace": workspace,
    "configured_mcp": configured_mcp,
    "local_tools": local_tools,
    "project_commands": project_commands,
    "routes": routes,
    "probe_warnings": warnings,
}
```

- [ ] **Step 4: Run the authority test and confirm green**

Run: `python3 -m unittest tests.test_capability_resolver.CapabilityResolverTests.test_local_goal_feature_cannot_upgrade_missing_host_controls -v`

Expected: pass.

- [ ] **Step 5: Add one red probe-safety test, implement it, and repeat vertically**

Add and implement these behaviors one at a time, running the named test after each addition:

```text
test_rejects_unknown_host_fields_and_unsupported_schema_version
test_rejects_relative_writable_roots_and_bool_as_integer
test_filesystem_permissions_cannot_upgrade_missing_host_writable_root
test_mcp_probe_output_is_reduced_to_allowlisted_fields
test_secret_values_from_mcp_output_never_appear_in_snapshot
test_probe_timeout_records_bounded_warning_without_failing_resolution
test_invalid_probe_json_records_warning_without_raw_output
test_git_probe_reports_head_dirty_state_and_worktree_fingerprint
test_git_unavailable_is_reported_without_aborting_resolution
test_runner_receives_argument_arrays_and_timeout
```

Use argument tuples, `shell=False`, a bounded timeout/capture, and redacted summaries. Retain only MCP `name`, `enabled`, `transport`, and `auth_status`; never retain environment, headers, commands, arguments, raw stderr, or credential-bearing URLs.

- [ ] **Step 6: Add project discovery and deterministic routing vertically**

Test and implement lockfile-aware package script discovery plus ordered routes for `local_search`, `definitions`, `structural_query`, `structural_rewrite`, `external_search`, `official_docs`, `parallel_investigation`, and `external_wait`. Assert that `structural_rewrite` never offers `rg` or plain text replacement. The workspace snapshot must report Git availability, HEAD, dirty state, and a worktree fingerprint when available; the unavailable form must remain explicit rather than fabricating a clean repository.

Run: `python3 -m unittest tests.test_capability_resolver -v`

Expected: all resolver tests pass.

- [ ] **Step 7: Add the `omc-doctor` Skill and shared contract**

The Skill must be read-only, build Host Capability Input from the actual current turn, invoke the resolver, return the normalized snapshot plus degradation plan, and never install or mutate anything. Set `policy.allow_implicit_invocation: false`; callers delegate by explicitly reading and following `$omc-doctor`, not by relying on implicit triggering. Also inspect locale status: if the saved preference is `zh-CN` while materialized metadata is English, report the mismatch and recommend rerunning `$omc-cn`; do not repair it automatically or add a SessionStart Hook. Add a contract scenario named `doctor_reports_saved_chinese_materialized_english_mismatch` so this behavior is not covered only inside the Locale Manager.

- [ ] **Step 8: Run Skill, custom plugin, and official plugin validation**

Run:

```bash
python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py plugins/ohmycodex/skills/omc-doctor
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
```

Expected: all three commands pass.

- [ ] **Step 9: Commit capability discovery**

```bash
git add plugins/ohmycodex scripts/validate_plugin.py tests
git commit -m "feat(doctor): add capability discovery and degradation routing"
```

### Task 3: Loop Ledger State Module

**Files:**
- Create: `plugins/ohmycodex/scripts/loop_ledger.py`
- Create: `plugins/ohmycodex/skills/omc-orchestrator/references/loop-contract.md`
- Test: `tests/test_loop_ledger.py`

**Interfaces:**
- Produces: `LoopLedger.create_run`, `load_run`, `activate_run`, `record_iteration`, `record_wait`, `reconcile_run`, and `finish_run`
- Produces: `LoopDecision(kind, state, reason, material_progress)` where kind is `continue`, `wait`, `complete`, `blocked`, or `paused`
- CLI: `create`, `activate`, `iterate`, `wait`, `reconcile`, `finish`, and `show` subcommands
- Persists: `.ohmycodex/runtime/loops/<run-id>.json` and `.ohmycodex/plans/loop-runs/<run-id>.md`

- [ ] **Step 1: Write the first red run-creation test**

```python
def test_create_rejects_threshold_below_three_without_writing(self) -> None:
    with self.assertRaisesRegex(ValueError, "threshold must be at least 3"):
        self.ledger.create_run(
            objective="Implement retry behavior",
            acceptance=[required_acceptance("AC-1")],
            threshold=2,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
    self.assertFalse((self.repository / ".ohmycodex").exists())
```

- [ ] **Step 2: Run the creation test and confirm red**

Run: `python3 -m unittest tests.test_loop_ledger.LoopLedgerTests.test_create_rejects_threshold_below_three_without_writing -v`

Expected: import or missing-interface failure.

- [ ] **Step 3: Implement strict creation and atomic state writes**

Create concurrent-safe IDs matching `^\d{8}T\d{6}Z-[0-9a-f]{12}$`. Require a non-empty objective, at least one required acceptance item, threshold `>= 3` with no maximum, strict nested objects, and valid repository state. Add `test_threshold_has_no_upper_bound` and `test_concurrent_run_ids_are_unique`. Write `preparing` state to a same-directory temporary file, flush, `fsync`, and commit with `os.replace` before writing audit Markdown.

- [ ] **Step 4: Confirm creation tests green**

Run: `python3 -m unittest tests.test_loop_ledger.LoopLedgerTests.test_create_rejects_threshold_below_three_without_writing tests.test_loop_ledger.LoopLedgerTests.test_create_writes_preparing_state_and_audit -v`

Expected: pass.

- [ ] **Step 5: Add activation and transition tests one behavior at a time**

Test and implement:

```text
test_run_id_validation_prevents_path_traversal
test_activate_binds_goal_and_is_idempotent_for_same_goal
test_activate_rejects_conflicting_goal_id
test_transition_table_rejects_invalid_state_changes
test_duplicate_iteration_id_is_idempotent
test_duplicate_iteration_id_with_different_payload_is_rejected
test_one_goal_turn_records_exactly_one_iteration
```

`activate_run` may bind only a preparing ledger. A retry with the same Goal ID is a no-op; a different ID is rejected.

- [ ] **Step 6: Add evidence-backed blocker counting vertically**

Canonicalize a SHA-256 blocker signature from blocker key, normalized evidence content excluding timestamps/IDs, next action, repository state, and acceptance states. First occurrence is `1`; identical consecutive signatures increment; a changed signature starts at `1`; computed material progress resets to `0`.

Test and implement:

```text
test_three_identical_blockers_block_at_threshold_three
test_changed_evidence_or_next_action_starts_new_blocker_sequence
test_acceptance_improvement_resets_no_progress_count
test_repository_change_requires_evidence_backed_progress_claim
test_new_external_or_user_decision_evidence_resets_count
test_policy_blocker_can_block_immediately_with_bounded_evidence
```

- [ ] **Step 7: Add completion, waiting, reconciliation, and recovery vertically**

Completion requires every required item to be `passed` by current non-stale evidence. `bounded_unavailable` can describe a verification limit but cannot pass a required item. Revision/fingerprint changes invalidate repository-bound evidence. A scheduled wait requires a schedule ID; every terminal transition with a recorded heartbeat requires confirmed schedule cleanup.

Test and implement:

```text
test_completion_requires_all_required_current_pass_evidence
test_reconcile_invalidates_repository_bound_evidence_after_revision_change
test_reconcile_reactivates_blocked_run_after_material_external_change
test_git_unavailable_uses_file_and_acceptance_fingerprints
test_wait_requires_schedule_id_only_for_scheduled_strategy
test_wait_remains_waiting_when_external_fingerprint_is_unchanged
test_terminal_transition_requires_confirmed_schedule_cleanup
test_failed_atomic_replace_leaves_previous_json_parseable_and_unchanged
test_audit_repair_is_idempotent_after_state_succeeds_but_audit_write_fails
test_audit_records_required_fields_without_copying_raw_logs
```

- [ ] **Step 8: Add and test the CLI adapter**

Each subcommand reads JSON using `json.load`, calls exactly one ledger interface method, and emits one JSON result. No command calls Codex, a model, scheduler, or package installer. Audit entries must contain action, tool or exact command, result, material progress, blocker, residual risk, and next action while rejecting raw stdout, stderr, and log fields.

Run: `python3 -m unittest tests.test_loop_ledger -v`

Expected: all ledger tests pass.

- [ ] **Step 9: Commit the state module**

```bash
git add plugins/ohmycodex/scripts/loop_ledger.py plugins/ohmycodex/skills/omc-orchestrator/references/loop-contract.md tests/test_loop_ledger.py
git commit -m "feat(loop): add evidence-backed continuation ledger"
```

### Task 4: `omc-loop`, `omc-intentgate`, and `omc-letgo`

**Files:**
- Create: `plugins/ohmycodex/skills/omc-loop/{SKILL.md,agents/openai.yaml}`
- Create: `plugins/ohmycodex/skills/omc-intentgate/{SKILL.md,agents/openai.yaml}`
- Create: `plugins/ohmycodex/skills/omc-letgo/{SKILL.md,agents/openai.yaml}`
- Modify: `plugins/ohmycodex/skills/omc-orchestrator/SKILL.md`
- Modify: lifecycle Skills that use tools or Team routing
- Test: `tests/test_continuation_contracts.py`
- Test: `tests/test_continuation_integration.py`
- Modify: `scripts/validate_plugin.py`

**Interfaces:**
- `omc-loop`: explicit-only Goal adapter for a validated objective, acceptance contract, and threshold
- `omc-intentgate`: explicit-only capability inspection and lifecycle routing; asks once for threshold only before a new continuation run
- `omc-letgo`: explicit-only autonomous choice between one turn and continuation; records assumptions and chooses threshold when it continues
- Host adapters remain instructions in Skills; Python tests use fake host controls and never claim native Goal coverage

- [ ] **Step 1: Write red static contract tests**

```python
def test_continuation_entries_are_explicit_only(self) -> None:
    for name in {"omc-loop", "omc-intentgate", "omc-letgo"}:
        metadata = json.loads((SKILLS / name / "agents" / "openai.yaml").read_text())
        self.assertFalse(metadata["policy"]["allow_implicit_invocation"])

def test_intentgate_requires_acceptance_before_goal_creation(self) -> None:
    text = (SKILLS / "omc-intentgate" / "SKILL.md").read_text()
    self.assertIn("Do not create a Goal", text)
    self.assertIn("acceptance contract", text)
```

- [ ] **Step 2: Run static tests and confirm missing Skills**

Run: `python3 -m unittest tests.test_continuation_contracts -v`

Expected: failures for missing continuation Skills.

- [ ] **Step 3: Implement `omc-loop` as a native host adapter**

The ordered steps must: load language/capability/loop contracts; identify new versus matching resume; ask once for `X` only on a new direct run; reject `X < 3`; inspect current Goal; refuse to replace a foreign unfinished Goal; create the preparing ledger before the native Goal; bind the confirmed Goal ID; perform exactly one choose/execute/verify/record cycle per Goal turn; reconcile matching/orphaned state; manage Scheduled heartbeat only for external waits; clean heartbeat before terminal state; and degrade to one current turn when Goal support is absent.

The Skill must never claim native pause/edit/resume/clear unless the host confirms the operation.

- [ ] **Step 4: Implement `omc-intentgate` and `omc-letgo`**

IntentGate explicitly follows `omc-doctor`, then `omc-orchestrator`. If acceptance is missing, it routes to discovery/specification and creates no Goal. When continuation is appropriate, it asks once for `X` and passes the answer to Loop so Loop does not ask again. It makes one OhMyCodex MCP proposal before invoking the Codex-native installation flow.

Letgo decides whether one turn is enough. For one-turn work it creates neither ledger nor Goal. For continuation it writes a bounded acceptance contract, records unapproved assumptions honestly, chooses `X >= 3` with a reason, and calls Loop. It may initiate justified native MCP installation without an extra OhMyCodex proposal, but native permissions remain authoritative.

Both entry points accept MCP sources only from an existing registry, a declared Skill dependency, user-supplied documented configuration, or an authoritative project source. They use Codex-native MCP controls and never invent endpoints. Letgo still requires explicit user control immediately before push, deploy, tag, public publication, or any other existing release gate.

- [ ] **Step 5: Add behavior-scenario tests through fake host controls**

Represent the Skill contracts as scenario fixtures with observable decisions. Test:

```text
intentgate_missing_acceptance_routes_without_goal
intentgate_rejects_threshold_below_three
intentgate_asks_once_per_new_run_and_not_on_resume
letgo_uses_one_turn_for_bounded_work
letgo_records_threshold_and_assumptions_for_continuation
matching_goal_resumes_matching_run
foreign_goal_is_never_replaced_or_adopted
orphaned_ledger_recreates_only_for_same_objective
goal_creation_failure_leaves_non_active_ledger
preparing_ledger_write_failure_prevents_goal_creation
goal_created_activation_interruption_recovers_by_run_id_without_duplicate_goal
missing_goal_support_degrades_without_shell_or_hook_loop
read_only_workspace_reports_reduced_audit_and_threshold_recovery
git_unavailable_uses_labeled_weaker_file_and_acceptance_fingerprints
scheduled_heartbeat_is_used_only_for_external_waits
scheduled_heartbeat_returns_to_same_task_and_reschedules_bounded_check
missing_scheduled_uses_bounded_terminal_only_for_short_process
missing_scheduled_keeps_long_wait_as_recoverable_goal
terminal_decisions_require_heartbeat_cleanup
user_stop_cleans_heartbeat_and_marks_ledger_paused
user_stop_does_not_claim_native_goal_pause
objective_change_requires_confirmed_native_goal_edit_or_user_goal_action
intentgate_and_letgo_preserve_distinct_mcp_proposal_behavior
untrusted_mcp_source_is_rejected_without_install_attempt
cli_mcp_install_uses_codex_mcp_without_direct_config_edit
app_mcp_install_uses_exposed_connector_or_dependency_flow
failed_mcp_install_selects_the_next_capability_route
missing_ast_route_never_uses_text_replacement_as_structural_rewrite
one_goal_turn_records_exactly_one_iteration
dirty_worktree_is_preserved
letgo_never_self_authorizes_push_deploy_tag_or_publication
```

- [ ] **Step 6: Run continuation tests and validators**

Run:

```bash
python3 -m unittest tests.test_continuation_contracts tests.test_continuation_integration -v
python3 scripts/validate_plugin.py
for skill in plugins/ohmycodex/skills/omc-loop plugins/ohmycodex/skills/omc-intentgate plugins/ohmycodex/skills/omc-letgo; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

Expected: all tests and validators pass.

- [ ] **Step 7: Commit native continuation workflows**

```bash
git add plugins/ohmycodex scripts/validate_plugin.py tests
git commit -m "feat(loop): add native continuation workflows"
```

### Task 5: Transactional English and Simplified Chinese Switching

**Files:**
- Create: `plugins/ohmycodex/scripts/locale_manager.py`
- Create: `plugins/ohmycodex/assets/locales/en.json`
- Create: `plugins/ohmycodex/assets/locales/zh-CN.json`
- Create: `plugins/ohmycodex/skills/omc-cn/{SKILL.md,agents/openai.yaml}`
- Create: `plugins/ohmycodex/skills/omc-en/{SKILL.md,agents/openai.yaml}`
- Create: `plugins/ohmycodex/skills/omc-orchestrator/references/language-policy.md`
- Test: `tests/test_locale_manager.py`
- Modify: all 19 `agents/openai.yaml` files
- Modify: `scripts/validate_plugin.py`

**Interfaces:**
- Produces: `validate_catalogs(plugin_root)`, `inspect_locale(plugin_root, codex_home)`, and `apply_locale(plugin_root, codex_home, locale) -> LocaleResult`
- CLI: `locale_manager.py {en,zh-CN} --plugin-root PATH --codex-home PATH [--json]`
- Persists: `$CODEX_HOME/ohmycodex/preferences.json` with schema version `1` and selected language
- Recovers: `$CODEX_HOME/ohmycodex/.locale-transaction.json` before beginning a new switch

- [ ] **Step 1: Write the first red exact-coverage test**

```python
def test_catalogs_cover_exactly_all_nineteen_skills(self) -> None:
    skill_names = {path.name for path in self.skills.iterdir() if (path / "SKILL.md").is_file()}
    for locale in ("en", "zh-CN"):
        catalog = json.loads((self.locales / f"{locale}.json").read_text())
        self.assertEqual(set(catalog["skills"]), skill_names)
```

- [ ] **Step 2: Run the coverage test and confirm red**

Run: `python3 -m unittest tests.test_locale_manager.LocaleManagerTests.test_catalogs_cover_exactly_all_nineteen_skills -v`

Expected: failure because catalogs are absent.

- [ ] **Step 3: Create canonical catalogs and structured metadata**

Each catalog contains schema version, locale, the manifest description plus `displayName`, `shortDescription`, `longDescription`, and three `defaultPrompt` values, and exactly three interface fields for each of the 19 Skills. The English catalog must byte-for-byte regenerate the checked-in default metadata. Stable manifest fields and invocation policies are excluded from translation data.

- [ ] **Step 4: Implement catalog validation and locale inspection**

Validate exact keys, prompt references to the matching `$omc-*` Skill, supported locales, manifest prompt count, and English-materialized consistency. `inspect_locale` reports saved preference, materialized locale, consistency, and restart/new-task recommendation without writing.

- [ ] **Step 5: Add red/green switch and preservation tests vertically**

Test and implement:

```text
test_catalogs_have_identical_keys_and_valid_skill_prompts
test_checked_in_metadata_matches_english_catalog
test_switch_to_chinese_updates_all_translatable_fields_and_preference
test_switch_preserves_policy_icons_dependencies_and_manifest_identity
test_english_to_chinese_to_english_restores_canonical_english_bytes
test_switch_is_idempotent
test_invalid_catalog_fails_before_any_target_is_changed
test_invalid_metadata_fails_before_any_target_is_changed
```

Pre-parse every target before the first write. Merge only the translatable interface keys. Write canonical JSON, which is valid YAML, and preserve every unknown non-translatable field.

- [ ] **Step 6: Add transaction rollback and crash recovery vertically**

Stage same-directory replacements, flush and `fsync`, write sibling backups, then write the transaction journal. On any exception, restore all committed targets and remove newly created files. At the next invocation, recover any leftover journal before validating a new transaction.

Test and implement:

```text
test_permission_failure_reports_unavailable_without_partial_changes
test_failure_on_nth_replace_rolls_back_every_file_and_preference
test_interrupted_transaction_journal_is_recovered_on_next_invocation
test_inspect_locale_detects_saved_chinese_preference_with_english_metadata
test_cli_success_message_requests_restart_or_new_task
```

- [ ] **Step 7: Add language policy plus `omc-cn` and `omc-en`**

The shared policy sets English as default, lets an explicit current-task language override the global preference for that task, translates OhMyCodex conversation/artifacts only, and never translates code, identifiers, commands, paths, or raw logs. Both Skills are explicit-only and run the locale CLI. Chinese success output asks in Chinese for a restart or new task; English success output does so in English.

- [ ] **Step 8: Run locale tests and all Skill validators**

Run:

```bash
python3 -m unittest tests.test_locale_manager -v
python3 scripts/validate_plugin.py
for skill in plugins/ohmycodex/skills/omc-*; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
```

Expected: all tests and validators pass with English materialized at the end.

- [ ] **Step 9: Commit localization**

```bash
git add plugins/ohmycodex scripts/validate_plugin.py tests/test_locale_manager.py
git commit -m "feat(i18n): add transactional English and Chinese switching"
```

### Task 6: Workspace Contracts, Documentation, CI, and Release Migration

**Files:**
- Modify: `plugins/ohmycodex/skills/omc-orchestrator/references/workspace-contract.md`
- Modify: all lifecycle `SKILL.md` files that must load shared language/capability policy
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/compatibility.md`
- Modify: `docs/evaluation-matrix.md`
- Modify: `docs/skill-catalog.md`
- Modify: `docs/team-mode.md`
- Create: `docs/releases/v0.3.0.md`
- Modify: `CONTRIBUTING.md`
- Modify: `.github/workflows/validate.yml`
- Modify: `.github/pull_request_template.md`
- Test: `tests/test_documentation_contract.py`

**Interfaces:**
- Documents: portable `$omc-*` and `/skills`; slash-style `/omc-*` only as a surface convenience
- Documents: breaking v0.3 migration, Goal/Scheduled degradation, MCP authority, locale restart requirement, and runtime paths
- CI: runs the full unit suite, custom validator, and official plugin validator-compatible checks

- [ ] **Step 1: Write red documentation contract tests**

Test that current runtime documentation contains no `ohmycodex-*` invocation, every new Skill appears in the catalog, README and `docs/releases/v0.3.0.md` call the rename breaking, compatibility names Goal/Scheduled fallback limits, and frozen historical files are excluded from the legacy-name scan. Also assert that the manifest and plugin tree declare or bundle no app, MCP server, Hook, daemon, or telemetry implementation.

- [ ] **Step 2: Run the documentation tests and confirm red**

Run: `python3 -m unittest tests.test_documentation_contract -v`

Expected: failures list current README/docs references to old names.

- [ ] **Step 3: Update the shared workspace and language/capability pointers**

Add `runtime/loops/` and `plans/loop-runs/` to the workspace contract. State that JSON runtime files are exempt from Markdown headers. Require all 19 Skills to load the language policy and require tool-using lifecycle Skills to follow the capability contract.

- [ ] **Step 4: Update user and contributor documentation**

Document v0.3 installation and invocation, the six new entries, threshold semantics, Letgo autonomy boundaries, no aliases, restart/new-task after locale switching, and native permission preservation. Add `docs/releases/v0.3.0.md` with the breaking rename table, migration instructions, new capabilities, and exclusions. Do not advertise custom slash command registration; describe `$omc-*`, `/skills`, and surface-provided slash resolution accurately. The surface table must not claim local files, local commands, project agent templates, or plugin metadata rewriting on ChatGPT Work Web.

- [ ] **Step 5: Expand the evaluation matrix**

Add positive, negative, recovery, and degradation scenarios for threshold prompting, matching/foreign/orphan Goal state, stale evidence, Scheduled cleanup, MCP install failure, structural tool absence, read-only workspaces, one-turn Letgo, and locale rollback/round-trip.

- [ ] **Step 6: Update CI and the PR checklist**

The workflow must run:

```yaml
- run: python3 -m unittest discover -s tests -v
- run: python3 scripts/validate_plugin.py
```

Keep the plugin dependency-free and ensure the PR template asks for unit tests, custom validation, official plugin validation, and a new-task smoke test.

- [ ] **Step 7: Run documentation and full repository validation**

Run:

```bash
python3 -m unittest discover -s tests -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
```

Expected: all tests and both validators pass.

- [ ] **Step 8: Commit docs and CI**

```bash
git add .github CONTRIBUTING.md README.md README.zh-CN.md docs plugins/ohmycodex/skills tests
git commit -m "docs: document v0.3 continuation and migration"
```

### Task 7: Independent Review, Cachebuster, Reinstall, and Smoke Test

**Files:**
- Modify only if review finds defects: files already in this plan
- Modify through official helper: `plugins/ohmycodex/.codex-plugin/plugin.json` cachebuster suffix

**Interfaces:**
- Review fixed point: the implementation-plan commit
- Spec source: `docs/superpowers/specs/2026-07-12-omc-native-continuation-design.md`
- Reinstall source: existing local `ohmycodex` marketplace entry

- [ ] **Step 1: Run two independent read-only reviews**

Dispatch one reviewer for repository standards and one for spec conformance using `git diff <plan-commit>...HEAD` and `git log <plan-commit>..HEAD --oneline`. Require file/line findings, no edits, and separate Standards and Spec results.

- [ ] **Step 2: Fix every confirmed blocker with a red/green regression test**

For each confirmed behavioral defect, add one failing public-interface test, run it red, make the minimal change, run it green, then rerun the owning module suite. Do not make speculative refactors from judgement-only review notes.

- [ ] **Step 3: Run final validation from a clean English materialization**

Run:

```bash
python3 plugins/ohmycodex/scripts/locale_manager.py en --plugin-root plugins/ohmycodex --codex-home "${CODEX_HOME:-$HOME/.codex}" --json
python3 -m unittest discover -s tests -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
for skill in plugins/ohmycodex/skills/omc-*; do
  python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill" || exit 1
done
git status --short
```

Expected: locale is `en`, every test/validator passes, and status contains only intentional final edits.

- [ ] **Step 4: Commit review fixes before changing the cachebuster**

```bash
git add plugins/ohmycodex scripts tests docs .github README.md README.zh-CN.md CONTRIBUTING.md
git commit -m "fix: address v0.3 implementation review"
```

Skip this commit only when review finds no confirmed issue and the worktree is clean.

- [ ] **Step 5: Update the cachebuster using the official helper**

Run:

```bash
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/update_plugin_cachebuster.py plugins/ohmycodex
```

Expected: the base remains `0.3.0` and exactly one `+codex.local-<UTC timestamp>` suffix is present.

- [ ] **Step 6: Re-run manifest validation and commit the cachebuster**

Run:

```bash
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
git add plugins/ohmycodex/.codex-plugin/plugin.json
git commit -m "chore: refresh local plugin cachebuster"
```

- [ ] **Step 7: Reinstall from the existing local marketplace**

Confirm the marketplace name from `.agents/plugins/marketplace.json`, then run:

```bash
codex plugin add ohmycodex@ohmycodex
```

Do not edit marketplace configuration by hand.

- [ ] **Step 8: Smoke-test in a new Codex task**

Verify the new task discovers all 19 canonical Skills and no legacy aliases, shows English descriptions by default, and resolves slash input to a Skill mention where the current surface supports it. Exercise read-only `$omc-doctor`, a non-mutating `$omc-letgo` one-turn request, the `$omc-cn` restart message in a disposable plugin copy or followed by restoration to English, and a real Goal-backed continuation on a harmless fixture when Goal controls are exposed. Record any host limitation rather than simulating unavailable Goal or Scheduled controls.

- [ ] **Step 9: Report final commits and evidence**

Include the implementation commit list, test count, custom and official validator results, reinstall result, new-task smoke result, and any residual host-only behavior that cannot be automated in repository tests.
