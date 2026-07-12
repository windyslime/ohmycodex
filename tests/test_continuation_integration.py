from __future__ import annotations

import re
import unittest
from dataclasses import dataclass, replace
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "ohmycodex" / "skills"
REFERENCES = SKILLS / "omc-orchestrator" / "references"


@dataclass(frozen=True)
class FakeHostFixture:
    """Inputs exposed by a fake host; this intentionally contains no runner."""

    surface: str = "desktop"
    goal: bool = True
    scheduled: bool = True
    background_terminal: bool = True
    writable: bool = True
    git: bool = True
    acceptance: str = "valid"
    threshold: int | None = 3
    current_goal: str = "none"
    ledger: str = "none"
    request: str = "continuing"
    wait: str = "none"
    mcp_source: str = "none"
    mcp_install: str = "not_requested"
    interruption: str = "none"
    user_action: str = "none"


@dataclass(frozen=True)
class ContractScenario:
    name: str
    entrypoint: str
    host: FakeHostFixture
    expected_decisions: tuple[str, ...]


@dataclass(frozen=True)
class DecisionRule:
    sources: tuple[str, ...]
    required: tuple[str, ...]
    ordered: tuple[tuple[str, str], ...] = ()


BASE = FakeHostFixture()


# This matrix records fake-host inputs and externally observable adapter decisions.
# It does not pretend to execute Codex Goals or implement a second continuation
# engine inside the tests. The generic assertions below verify that the Skills and
# their loaded contracts declare every decision represented by the matrix.
SCENARIOS = (
    ContractScenario(
        "intentgate_missing_acceptance_routes_without_goal",
        "omc-intentgate",
        replace(BASE, acceptance="missing", threshold=None),
        ("route:acceptance-first-without-state",),
    ),
    ContractScenario(
        "intentgate_rejects_threshold_below_three",
        "omc-intentgate",
        replace(BASE, threshold=2),
        ("threshold:reject-below-three",),
    ),
    ContractScenario(
        "intentgate_asks_once_per_new_run_and_not_on_resume",
        "omc-intentgate",
        BASE,
        ("threshold:ask-once-new-never-resume",),
    ),
    ContractScenario(
        "letgo_uses_one_turn_for_bounded_work",
        "omc-letgo",
        replace(BASE, request="bounded", threshold=None),
        ("letgo:one-turn-without-state",),
    ),
    ContractScenario(
        "letgo_records_threshold_and_assumptions_for_continuation",
        "omc-letgo",
        replace(BASE, threshold=5),
        ("letgo:record-autonomous-contract",),
    ),
    ContractScenario(
        "matching_goal_resumes_matching_run",
        "omc-loop",
        replace(BASE, current_goal="matching", ledger="active"),
        ("goal:resume-matching",),
    ),
    ContractScenario(
        "foreign_goal_is_never_replaced_or_adopted",
        "omc-loop",
        replace(BASE, current_goal="foreign"),
        ("goal:leave-foreign-untouched",),
    ),
    ContractScenario(
        "orphaned_ledger_recreates_only_for_same_objective",
        "omc-loop",
        replace(BASE, ledger="orphaned"),
        ("goal:recreate-orphan-only-for-same-objective",),
    ),
    ContractScenario(
        "goal_creation_failure_leaves_non_active_ledger",
        "omc-loop",
        replace(BASE, interruption="goal_create_failure"),
        ("goal:create-failure-keeps-ledger-non-active",),
    ),
    ContractScenario(
        "preparing_ledger_write_failure_prevents_goal_creation",
        "omc-loop",
        replace(BASE, interruption="ledger_write_failure"),
        ("goal:ledger-first-or-no-goal",),
    ),
    ContractScenario(
        "goal_created_activation_interruption_recovers_by_run_id_without_duplicate_goal",
        "omc-loop",
        replace(BASE, current_goal="matching", ledger="preparing", interruption="activation"),
        ("goal:recover-activation-without-duplicate",),
    ),
    ContractScenario(
        "missing_goal_support_degrades_without_shell_or_hook_loop",
        "omc-loop",
        replace(BASE, goal=False),
        ("fallback:one-turn-without-runtime",),
    ),
    ContractScenario(
        "read_only_workspace_reports_reduced_audit_and_threshold_recovery",
        "omc-loop",
        replace(BASE, writable=False),
        ("workspace:report-reduced-durability",),
    ),
    ContractScenario(
        "git_unavailable_uses_labeled_weaker_file_and_acceptance_fingerprints",
        "omc-loop",
        replace(BASE, git=False),
        ("workspace:weaker-file-acceptance-fingerprints",),
    ),
    ContractScenario(
        "scheduled_heartbeat_is_used_only_for_external_waits",
        "omc-loop",
        replace(BASE, wait="long_external"),
        ("scheduled:external-waits-only",),
    ),
    ContractScenario(
        "scheduled_heartbeat_returns_to_same_task_and_reschedules_bounded_check",
        "omc-loop",
        replace(BASE, wait="unchanged_external"),
        ("scheduled:same-task-bounded-recheck",),
    ),
    ContractScenario(
        "missing_scheduled_uses_bounded_terminal_only_for_short_process",
        "omc-loop",
        replace(BASE, scheduled=False, wait="short_process"),
        ("fallback:bounded-terminal-short-only",),
    ),
    ContractScenario(
        "missing_scheduled_keeps_long_wait_as_recoverable_goal",
        "omc-loop",
        replace(BASE, scheduled=False, wait="long_external"),
        ("fallback:long-wait-recoverable-goal",),
    ),
    ContractScenario(
        "terminal_decisions_require_heartbeat_cleanup",
        "omc-loop",
        replace(BASE, wait="terminal_with_heartbeat"),
        ("scheduled:cleanup-before-terminal",),
    ),
    ContractScenario(
        "user_stop_cleans_heartbeat_and_marks_ledger_paused",
        "omc-loop",
        replace(BASE, wait="long_external", user_action="stop"),
        ("stop:cleanup-and-pause-ledger",),
    ),
    ContractScenario(
        "user_stop_does_not_claim_native_goal_pause",
        "omc-loop",
        replace(BASE, user_action="stop"),
        ("stop:no-unconfirmed-native-pause",),
    ),
    ContractScenario(
        "objective_change_requires_confirmed_native_goal_edit_or_user_goal_action",
        "omc-loop",
        replace(BASE, current_goal="matching", ledger="active", user_action="change_objective"),
        ("goal:objective-change-needs-native-confirmation",),
    ),
    ContractScenario(
        "intentgate_and_letgo_preserve_distinct_mcp_proposal_behavior",
        "omc-intentgate+omc-letgo",
        replace(BASE, mcp_source="registry"),
        ("mcp:distinct-entrypoint-proposals",),
    ),
    ContractScenario(
        "untrusted_mcp_source_is_rejected_without_install_attempt",
        "omc-intentgate+omc-letgo",
        replace(BASE, mcp_source="untrusted"),
        ("mcp:reject-untrusted-source",),
    ),
    ContractScenario(
        "cli_mcp_install_uses_codex_mcp_without_direct_config_edit",
        "omc-intentgate+omc-letgo",
        replace(BASE, surface="cli", mcp_source="registry", mcp_install="requested"),
        ("mcp:cli-native-command",),
    ),
    ContractScenario(
        "app_mcp_install_uses_exposed_connector_or_dependency_flow",
        "omc-intentgate+omc-letgo",
        replace(BASE, surface="app", mcp_source="registry", mcp_install="requested"),
        ("mcp:app-native-flow",),
    ),
    ContractScenario(
        "failed_mcp_install_selects_the_next_capability_route",
        "omc-intentgate+omc-letgo",
        replace(BASE, mcp_source="registry", mcp_install="failed"),
        ("mcp:failure-selects-next-route",),
    ),
    ContractScenario(
        "missing_ast_route_never_uses_text_replacement_as_structural_rewrite",
        "omc-intentgate+omc-letgo",
        BASE,
        ("tooling:no-text-structural-rewrite",),
    ),
    ContractScenario(
        "one_goal_turn_records_exactly_one_iteration",
        "omc-loop",
        replace(BASE, current_goal="matching", ledger="active"),
        ("iteration:one-per-goal-turn",),
    ),
    ContractScenario(
        "dirty_worktree_is_preserved",
        "omc-loop+omc-letgo",
        BASE,
        ("workspace:preserve-dirty-worktree",),
    ),
    ContractScenario(
        "letgo_never_self_authorizes_push_deploy_tag_or_publication",
        "omc-letgo",
        replace(BASE, user_action="release"),
        ("release:explicit-user-gate",),
    ),
)


DECISION_RULES = {
    "route:acceptance-first-without-state": DecisionRule(
        ("skill:omc-intentgate",),
        (
            r"acceptance contract before continuation",
            r"acceptance is missing or ambiguous.+do not create a goal or loop ledger",
            r"route to .+omc-(?:discover|spec)",
        ),
    ),
    "threshold:reject-below-three": DecisionRule(
        ("skill:omc-intentgate",),
        (r"reject .?x\s*<\s*3",),
    ),
    "threshold:ask-once-new-never-resume": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-loop"),
        (
            r"new (?:direct |continuation )?run.+ask once",
            r"(?:matching|resume).+(?:without asking|never ask)",
            r"loop (?:does|must) not ask again",
        ),
    ),
    "letgo:one-turn-without-state": DecisionRule(
        ("skill:omc-letgo",),
        (r"one bounded workflow turn is enough.+without creating a goal or loop ledger",),
    ),
    "letgo:record-autonomous-contract": DecisionRule(
        ("skill:omc-letgo",),
        (
            r"author a bounded acceptance contract",
            r"record every unapproved assumption",
            r"choose .?x\s*>=\s*3",
            r"record why that threshold",
        ),
    ),
    "goal:resume-matching": DecisionRule(
        ("skill:omc-loop",),
        (r"goal names the same run id.+reconcile",),
    ),
    "goal:leave-foreign-untouched": DecisionRule(
        ("skill:omc-loop",),
        (
            r"different unfinished goal.+create no ledger",
            r"do not replace or adopt",
        ),
    ),
    "goal:recreate-orphan-only-for-same-objective": DecisionRule(
        ("skill:omc-loop",),
        (r"active ledger without a goal.+orphaned.+replacement goal only.+same objective",),
    ),
    "goal:create-failure-keeps-ledger-non-active": DecisionRule(
        ("skill:omc-loop",),
        (r"goal creation fails.+leave the ledger non-active",),
    ),
    "goal:ledger-first-or-no-goal": DecisionRule(
        ("skill:omc-loop",),
        (r"write the preparing ledger before.+goal-create", r"ledger creation fails.+create no goal"),
        ((r"write the preparing ledger", r"goal-create"),),
    ),
    "goal:recover-activation-without-duplicate": DecisionRule(
        ("skill:omc-loop",),
        (r"recover an activation interruption.+run id.+never create a duplicate goal",),
    ),
    "fallback:one-turn-without-runtime": DecisionRule(
        ("skill:omc-loop", "ref:loop-contract"),
        (
            r"goal support is unavailable.+perform at most the current.+turn",
            r"do not emulate.+(?:shell loop|stop hook)",
        ),
    ),
    "workspace:report-reduced-durability": DecisionRule(
        ("skill:omc-loop", "ref:loop-contract"),
        (
            r"(?:workspace|project) (?:is )?not writable|read-only workspace",
            r"(?:durable audit|audit durability).+reduced",
            r"(?:threshold recovery|custom threshold).+reduced",
        ),
    ),
    "workspace:weaker-file-acceptance-fingerprints": DecisionRule(
        ("ref:loop-contract",),
        (
            r"git is unavailable",
            r"file(?:_| ).*fingerprint.+acceptance(?:_| ).*fingerprint",
            r"weaker",
        ),
    ),
    "scheduled:external-waits-only": DecisionRule(
        ("skill:omc-loop", "ref:loop-contract"),
        (r"scheduled.+only.+external (?:state|wait)|external (?:state|wait).+scheduled.+only",),
    ),
    "scheduled:same-task-bounded-recheck": DecisionRule(
        ("skill:omc-loop",),
        (
            r"bounded heartbeat.+returns? to (?:this|the) same task",
            r"unchanged external fingerprint remains waiting",
        ),
    ),
    "fallback:bounded-terminal-short-only": DecisionRule(
        ("skill:omc-loop",),
        (r"bounded background terminal only for a short-lived process",),
    ),
    "fallback:long-wait-recoverable-goal": DecisionRule(
        ("skill:omc-loop",),
        (r"keep a long wait as a recoverable goal",),
    ),
    "scheduled:cleanup-before-terminal": DecisionRule(
        ("skill:omc-loop", "ref:loop-contract"),
        (r"delete a recorded heartbeat.+before.+(?:terminal result|terminal)",),
    ),
    "stop:cleanup-and-pause-ledger": DecisionRule(
        ("skill:omc-loop",),
        (r"user stop.+clean the heartbeat.+mark the ledger paused",),
    ),
    "stop:no-unconfirmed-native-pause": DecisionRule(
        ("skill:omc-loop",),
        (r"do not claim the native goal was paused.+unless the host confirms",),
    ),
    "goal:objective-change-needs-native-confirmation": DecisionRule(
        ("skill:omc-loop",),
        (r"objective change.+only after a confirmed native goal edit.+otherwise.+native goal action",),
    ),
    "mcp:distinct-entrypoint-proposals": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo"),
        (
            r"propose mcp installation at most once",
            r"without a separate ohmycodex proposal",
        ),
    ),
    "mcp:reject-untrusted-source": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo"),
        (
            r"existing registry.+declared skill dependency.+user-supplied documented configuration.+authoritative project source",
            r"reject an untrusted or invented endpoint|never invent an endpoint",
        ),
    ),
    "mcp:cli-native-command": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo"),
        (r"codex mcp.+(?:on|for) (?:the )?cli", r"never edit codex (?:mcp )?configuration directly"),
    ),
    "mcp:app-native-flow": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo"),
        (r"exposed connector/dependency flow in an app|app.+exposed.+(?:connector|dependency).+flow",),
    ),
    "mcp:failure-selects-next-route": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo"),
        (r"installation fails.+(?:select|use) the next.+route",),
    ),
    "tooling:no-text-structural-rewrite": DecisionRule(
        ("skill:omc-intentgate", "skill:omc-letgo", "ref:capability-contract"),
        (r"text (?:search|replacement).+(?:must not|may not|never).+structural rewrite|never substitute text replacement.+structural rewrite",),
    ),
    "iteration:one-per-goal-turn": DecisionRule(
        ("skill:omc-loop",),
        (
            r"one native goal turn.+exactly one.+choose.+execute.+verify.+record",
            r"never write multiple ledger iterations for one goal turn",
        ),
    ),
    "workspace:preserve-dirty-worktree": DecisionRule(
        ("skill:omc-loop", "skill:omc-letgo"),
        (r"preserve dirty worktrees",),
    ),
    "release:explicit-user-gate": DecisionRule(
        ("skill:omc-letgo",),
        (
            r"immediately before push, deploy, tag, public publication",
            r"obtain the user.s required confirmation|explicit user (?:control|confirmation)",
        ),
    ),
}


EXPECTED_SCENARIO_NAMES = (
    "intentgate_missing_acceptance_routes_without_goal",
    "intentgate_rejects_threshold_below_three",
    "intentgate_asks_once_per_new_run_and_not_on_resume",
    "letgo_uses_one_turn_for_bounded_work",
    "letgo_records_threshold_and_assumptions_for_continuation",
    "matching_goal_resumes_matching_run",
    "foreign_goal_is_never_replaced_or_adopted",
    "orphaned_ledger_recreates_only_for_same_objective",
    "goal_creation_failure_leaves_non_active_ledger",
    "preparing_ledger_write_failure_prevents_goal_creation",
    "goal_created_activation_interruption_recovers_by_run_id_without_duplicate_goal",
    "missing_goal_support_degrades_without_shell_or_hook_loop",
    "read_only_workspace_reports_reduced_audit_and_threshold_recovery",
    "git_unavailable_uses_labeled_weaker_file_and_acceptance_fingerprints",
    "scheduled_heartbeat_is_used_only_for_external_waits",
    "scheduled_heartbeat_returns_to_same_task_and_reschedules_bounded_check",
    "missing_scheduled_uses_bounded_terminal_only_for_short_process",
    "missing_scheduled_keeps_long_wait_as_recoverable_goal",
    "terminal_decisions_require_heartbeat_cleanup",
    "user_stop_cleans_heartbeat_and_marks_ledger_paused",
    "user_stop_does_not_claim_native_goal_pause",
    "objective_change_requires_confirmed_native_goal_edit_or_user_goal_action",
    "intentgate_and_letgo_preserve_distinct_mcp_proposal_behavior",
    "untrusted_mcp_source_is_rejected_without_install_attempt",
    "cli_mcp_install_uses_codex_mcp_without_direct_config_edit",
    "app_mcp_install_uses_exposed_connector_or_dependency_flow",
    "failed_mcp_install_selects_the_next_capability_route",
    "missing_ast_route_never_uses_text_replacement_as_structural_rewrite",
    "one_goal_turn_records_exactly_one_iteration",
    "dirty_worktree_is_preserved",
    "letgo_never_self_authorizes_push_deploy_tag_or_publication",
)


def contract_source(source: str) -> str:
    kind, name = source.split(":", 1)
    if kind == "skill":
        path = SKILLS / name / "SKILL.md"
    elif kind == "ref":
        path = REFERENCES / f"{name}.md"
    else:  # pragma: no cover - malformed test data
        raise AssertionError(f"unknown contract source: {source}")
    if not path.is_file():
        raise AssertionError(f"missing contract source: {path}")
    return path.read_text(encoding="utf-8").replace("`", "").lower()


class ContinuationIntegrationContractTests(unittest.TestCase):
    def test_fake_host_matrix_covers_every_planned_scenario(self) -> None:
        self.assertEqual(tuple(scenario.name for scenario in SCENARIOS), EXPECTED_SCENARIO_NAMES)
        self.assertEqual(len({scenario.name for scenario in SCENARIOS}), len(SCENARIOS))

    def test_fake_host_scenarios_declare_observable_decisions(self) -> None:
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario.name, host=scenario.host):
                self.assertIn(
                    scenario.entrypoint,
                    {
                        "omc-loop",
                        "omc-intentgate",
                        "omc-letgo",
                        "omc-intentgate+omc-letgo",
                        "omc-loop+omc-letgo",
                    },
                )
                self.assertTrue(scenario.expected_decisions)

                for decision in scenario.expected_decisions:
                    self.assertIn(decision, DECISION_RULES, decision)
                    rule = DECISION_RULES[decision]
                    corpus = "\n".join(contract_source(source) for source in rule.sources)
                    for pattern in rule.required:
                        self.assertRegex(
                            corpus,
                            re.compile(pattern, re.IGNORECASE | re.DOTALL),
                            f"{scenario.name} must declare {decision}: /{pattern}/",
                        )
                    for before, after in rule.ordered:
                        before_match = re.search(before, corpus, re.IGNORECASE | re.DOTALL)
                        after_match = re.search(after, corpus, re.IGNORECASE | re.DOTALL)
                        self.assertIsNotNone(before_match, before)
                        self.assertIsNotNone(after_match, after)
                        assert before_match is not None and after_match is not None
                        self.assertLess(
                            before_match.start(),
                            after_match.start(),
                            f"{scenario.name} must order /{before}/ before /{after}/",
                        )


if __name__ == "__main__":
    unittest.main()
