from __future__ import annotations

import copy
import io
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
LEDGER_SCRIPT = ROOT / "plugins" / "ohmycodex" / "scripts" / "loop_ledger.py"
SPEC = importlib.util.spec_from_file_location("loop_ledger", LEDGER_SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

LoopDecision = MODULE.LoopDecision
LoopLedger = MODULE.LoopLedger


NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)
RUN_ID = "20260712T120000Z-abcdef123456"


def repository_state(fingerprint: str = "sha256:baseline") -> dict[str, object]:
    return {
        "git_head": "abc123",
        "worktree_fingerprint": fingerprint,
        "evidence_strength": "git",
    }


def file_repository_state(
    *,
    worktree: str = "sha256:file-baseline",
    files: str = "sha256:files-v1",
    acceptance_fingerprint: str = "sha256:acceptance-v1",
) -> dict[str, object]:
    return {
        "git_head": None,
        "worktree_fingerprint": worktree,
        "evidence_strength": "files",
        "file_fingerprint": files,
        "acceptance_fingerprint": acceptance_fingerprint,
    }


def acceptance() -> list[dict[str, object]]:
    return [
        {
            "id": "AC-1",
            "description": "All required tests pass",
            "required": True,
        }
    ]


def capability_snapshot() -> dict[str, object]:
    return {
        "schema_version": 1,
        "continuation": {"available": True, "source": "host"},
    }


def blocked_iteration(
    number: int,
    *,
    fingerprint: str = "sha256:baseline",
    command_summary: str = "One retry assertion still fails",
    next_action: str = "Inspect retry counter update",
) -> dict[str, object]:
    command_id = f"command-{number}"
    return {
        "iteration_number": number,
        "iteration_id": f"turn-{number:04d}",
        "observed_at": f"2026-07-12T12:00:{number:02d}Z",
        "action": "Run the checkout retry tests",
        "tools": ["exec_command"],
        "commands": [
            {
                "id": command_id,
                "argv": ["python3", "-m", "unittest"],
                "exit_code": 1,
                "result": "failed",
                "summary": command_summary,
            }
        ],
        "repository_state": repository_state(fingerprint),
        "acceptance_updates": [],
        "check_updates": [],
        "progress_claim": {"kind": "none", "reason": "", "evidence_ids": []},
        "blocker": {
            "kind": "technical",
            "key": "retry-assertion",
            "summary": "Expected three calls, observed two",
            "evidence_ids": [command_id],
            "next_action": next_action,
        },
        "residual_risks": [],
        "next_action": next_action,
    }


def passing_iteration(number: int, acceptance_id: str = "AC-1") -> dict[str, object]:
    command_id = f"command-{number}"
    return {
        "iteration_number": number,
        "iteration_id": f"turn-{number:04d}",
        "observed_at": f"2026-07-12T12:00:{number:02d}Z",
        "action": "Run the required tests",
        "tools": ["exec_command"],
        "commands": [
            {
                "id": command_id,
                "argv": ["python3", "-m", "unittest"],
                "exit_code": 0,
                "result": "passed",
                "summary": "Required tests passed",
            }
        ],
        "repository_state": repository_state(),
        "acceptance_updates": [
            {
                "id": acceptance_id,
                "status": "passed",
                "evidence": [
                    {
                        "id": f"evidence-{number}",
                        "kind": "command",
                        "summary": "Required tests passed",
                        "reference": command_id,
                        "repository_fingerprint": "sha256:baseline",
                        "external_fingerprint": None,
                        "decision_id": None,
                    }
                ],
            }
        ],
        "check_updates": [],
        "progress_claim": {"kind": "none", "reason": "", "evidence_ids": []},
        "blocker": None,
        "residual_risks": [],
        "next_action": "Evaluate remaining acceptance items",
    }


def external_progress_iteration(
    number: int,
    *,
    kind: str = "external",
) -> dict[str, object]:
    evidence_id = f"external-{number}"
    progress_kind = "external_change" if kind == "external" else "user_decision"
    return {
        "iteration_number": number,
        "iteration_id": f"turn-{number:04d}",
        "observed_at": f"2026-07-12T12:01:{number:02d}Z",
        "action": "Inspect new external evidence",
        "tools": ["inspection"],
        "commands": [],
        "repository_state": repository_state(),
        "acceptance_updates": [],
        "check_updates": [
            {
                "id": f"external-check-{number}",
                "description": "External state changed",
                "status": "unknown",
                "evidence": [
                    {
                        "id": evidence_id,
                        "kind": kind,
                        "summary": "New evidence changes the available decision",
                        "reference": f"reference-{number}",
                        "repository_fingerprint": "sha256:baseline",
                        "external_fingerprint": f"external:{number}",
                        "decision_id": f"decision-{number}" if kind == "user_decision" else None,
                    }
                ],
            }
        ],
        "progress_claim": {
            "kind": progress_kind,
            "reason": "New evidence removes the previous blocker",
            "evidence_ids": [evidence_id],
        },
        "blocker": None,
        "residual_risks": [],
        "next_action": "Continue with the newly available route",
    }


def external_blocked_iteration(
    number: int,
    fingerprint: str = "ci:pending",
) -> dict[str, object]:
    payload = blocked_iteration(number)
    evidence_id = f"external-blocker-{number}"
    payload["commands"] = []
    payload["check_updates"] = [
        {
            "id": "ci-status",
            "description": "Wait for the required CI checks",
            "status": "unknown",
            "evidence": [
                {
                    "id": evidence_id,
                    "kind": "external",
                    "summary": "Required CI remains pending",
                    "reference": "ci-run-123",
                    "repository_fingerprint": "sha256:baseline",
                    "external_fingerprint": fingerprint,
                    "decision_id": None,
                }
            ],
        }
    ]
    payload["blocker"]["evidence_ids"] = [evidence_id]
    return payload


def external_wait(
    fingerprint: str = "ci:pending",
    *,
    strategy: str = "scheduled",
    observed_at: str = "2026-07-12T12:05:00Z",
) -> dict[str, object]:
    return {
        "strategy": strategy,
        "condition": "Wait for the required CI checks",
        "fingerprint": fingerprint,
        "observed_at": observed_at,
        "next_action": "Reconcile the CI check state",
    }


def cleanup_confirmation(schedule_id: str = "schedule-123") -> dict[str, object]:
    return {
        "schedule_id": schedule_id,
        "deleted": True,
        "observed_at": "2026-07-12T12:06:00Z",
    }


def finish_evidence() -> dict[str, object]:
    return {
        "observed_at": "2026-07-12T12:07:00Z",
        "action": "Honor the user stop request",
        "tools": ["goal_control"],
        "commands": [],
        "residual_risks": ["Acceptance remains incomplete"],
        "next_action": "Resume only after an explicit user or host signal",
    }


def resume_signal() -> dict[str, object]:
    return {
        "kind": "user",
        "id": "resume-123",
        "reason": "The user explicitly requested continuation",
        "observed_at": "2026-07-12T12:08:00Z",
    }


class LoopLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = Path(self.tempdir.name).resolve()
        self.ledger = LoopLedger(
            self.repository,
            clock=lambda: NOW,
            run_id_factory=lambda _now: RUN_ID,
        )

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def create_active_run(
        self,
        *,
        threshold: int = 3,
        acceptance_items: list[dict[str, object]] | None = None,
    ) -> dict[str, object]:
        self.ledger.create_run(
            objective="Implement retry behavior",
            acceptance=acceptance_items or acceptance(),
            threshold=threshold,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
        return self.ledger.activate_run(RUN_ID, "goal-123")

    def state_path(self, run_id: str = RUN_ID) -> Path:
        return self.repository / ".ohmycodex" / "runtime" / "loops" / f"{run_id}.json"

    def test_create_rejects_threshold_below_three_without_writing(self) -> None:
        with self.assertRaisesRegex(ValueError, "threshold must be at least 3"):
            self.ledger.create_run(
                objective="Implement retry behavior",
                acceptance=acceptance(),
                threshold=2,
                baseline=repository_state(),
                capabilities=capability_snapshot(),
                entrypoint="omc-loop",
            )

        self.assertFalse((self.repository / ".ohmycodex").exists())

    def test_create_writes_preparing_state_and_audit(self) -> None:
        state = self.ledger.create_run(
            objective="Implement retry behavior",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )

        self.assertEqual(state["run_id"], RUN_ID)
        self.assertEqual(state["status"], "preparing")
        self.assertEqual(state["revision"], 1)
        self.assertEqual(state["threshold"], 3)
        self.assertEqual(state["no_progress_count"], 0)
        self.assertIsNone(state["goal_id"])
        self.assertEqual(state["repository_state"], repository_state())
        self.assertEqual(state["acceptance"][0]["status"], "unknown")
        self.assertEqual(state["acceptance"][0]["evidence"], [])

        state_path = self.repository / ".ohmycodex" / "runtime" / "loops" / f"{RUN_ID}.json"
        audit_path = self.repository / ".ohmycodex" / "plans" / "loop-runs" / f"{RUN_ID}.md"
        self.assertEqual(json.loads(state_path.read_text(encoding="utf-8")), state)
        audit = audit_path.read_text(encoding="utf-8")
        self.assertIn("# Loop Run", audit)
        self.assertIn("Implement retry behavior", audit)
        self.assertIn("Status: preparing", audit)

    def test_create_rejects_empty_objective_or_no_required_acceptance(self) -> None:
        with self.assertRaisesRegex(ValueError, "objective must be a non-empty string"):
            self.ledger.create_run(
                objective=" ",
                acceptance=acceptance(),
                threshold=3,
                baseline=repository_state(),
                capabilities=capability_snapshot(),
                entrypoint="omc-loop",
            )

        optional = acceptance()
        optional[0]["required"] = False
        with self.assertRaisesRegex(ValueError, "at least one required item"):
            self.ledger.create_run(
                objective="Implement retry behavior",
                acceptance=optional,
                threshold=3,
                baseline=repository_state(),
                capabilities=capability_snapshot(),
                entrypoint="omc-loop",
            )

        self.assertFalse((self.repository / ".ohmycodex").exists())

    def test_threshold_has_no_upper_bound(self) -> None:
        state = self.ledger.create_run(
            objective="Long-running objective",
            acceptance=acceptance(),
            threshold=10**12,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-letgo",
            threshold_reason="A large threshold is intentional",
        )

        self.assertEqual(state["threshold"], 10**12)

    def test_run_id_validation_prevents_path_traversal(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid run_id"):
            self.ledger.load_run("../../outside")

    def test_state_symlink_cannot_escape_repository(self) -> None:
        outside = self.repository.parent / f"outside-{RUN_ID}.json"
        outside.write_text("{}", encoding="utf-8")
        self.addCleanup(outside.unlink)
        path = self.state_path()
        path.parent.mkdir(parents=True)
        path.symlink_to(outside)

        with self.assertRaisesRegex(ValueError, "symlink"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_duplicate_json_keys(self) -> None:
        self.create_active_run()
        path = self.state_path()
        raw = path.read_text(encoding="utf-8")
        raw = raw.replace(
            '  "schema_version": 1,',
            '  "schema_version": 1,\n  "schema_version": 1,',
            1,
        )
        path.write_text(raw, encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_nonstandard_nan_json(self) -> None:
        self.create_active_run()
        path = self.state_path()
        state = json.loads(path.read_text(encoding="utf-8"))
        state["capability_snapshot"]["probe"] = float("nan")
        path.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "non-standard JSON constant"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_duplicate_acceptance_ids_and_float_schema(self) -> None:
        self.create_active_run()
        path = self.state_path()
        state = json.loads(path.read_text(encoding="utf-8"))
        state["acceptance"].append(copy.deepcopy(state["acceptance"][0]))
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate acceptance id"):
            self.ledger.load_run(RUN_ID)

        state["acceptance"] = state["acceptance"][:1]
        state["schema_version"] = 1.0
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "schema_version"):
            self.ledger.load_run(RUN_ID)

        state["schema_version"] = 1
        state["acceptance"][0]["required"] = False
        path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "at least one required"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_corrupt_iteration_hash_and_cross_field_state(self) -> None:
        self.create_active_run(threshold=5)
        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        path = self.state_path()
        original = json.loads(path.read_text(encoding="utf-8"))

        corrupt_hash = copy.deepcopy(original)
        corrupt_hash["last_iteration"]["payload_hash"] = "0" * 64
        path.write_text(json.dumps(corrupt_hash), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "payload_hash"):
            self.ledger.load_run(RUN_ID)

        corrupt_outcome = copy.deepcopy(original)
        corrupt_outcome["outcome"] = {"kind": "invented", "reason": "Not valid"}
        path.write_text(json.dumps(corrupt_outcome), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "outcome"):
            self.ledger.load_run(RUN_ID)

    def test_load_recomputes_repository_evidence_freshness(self) -> None:
        items = acceptance()
        items.append(
            {
                "id": "AC-2",
                "description": "Review confirms no regression",
                "required": True,
            }
        )
        self.create_active_run(acceptance_items=items)
        self.ledger.record_iteration(RUN_ID, passing_iteration(1))
        path = self.state_path()
        state = json.loads(path.read_text(encoding="utf-8"))
        evidence = state["acceptance"][0]["evidence"][0]
        evidence["repository_fingerprint"] = "sha256:stale"
        evidence["stale"] = False
        path.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "freshness is inconsistent"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_oversized_pending_audit_event(self) -> None:
        self.create_active_run()
        path = self.state_path()
        state = json.loads(path.read_text(encoding="utf-8"))
        details = {
            "action": "Recover an audit event",
            "tools": ["loop_ledger"],
            "commands": [
                {
                    "argv": ["command"],
                    "result": "failed",
                    "summary": "x" * 1800,
                }
                for _ in range(40)
            ],
            "result": "blocked",
            "material_progress": False,
            "blocker": None,
            "residual_risks": [],
            "next_action": "Repair the event",
            "evidence": {},
        }
        event = {
            "sequence": state["audit"]["sequence"],
            "kind": "oversized",
            "observed_at": "2026-07-12T12:09:00Z",
            "summary": "An oversized pending event",
            "details": details,
        }
        event["hash"] = MODULE._payload_hash(event)
        state["audit"]["pending"] = event
        path.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "audit event exceeds"):
            self.ledger.load_run(RUN_ID)

    def test_load_rejects_duplicate_check_ids(self) -> None:
        self.create_active_run()
        self.ledger.record_iteration(RUN_ID, external_progress_iteration(1))
        path = self.state_path()
        state = json.loads(path.read_text(encoding="utf-8"))
        state["checks"].append(copy.deepcopy(state["checks"][0]))
        path.write_text(json.dumps(state), encoding="utf-8")

        with self.assertRaisesRegex(ValueError, "duplicate check id"):
            self.ledger.load_run(RUN_ID)

    def test_create_records_letgo_assumptions_and_threshold_reason(self) -> None:
        state = self.ledger.create_run(
            objective="Autonomously complete the migration",
            acceptance=acceptance(),
            threshold=5,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-letgo",
            assumptions=["The public API must remain compatible"],
            threshold_reason="Five turns allow two recovery strategies",
        )

        self.assertEqual(
            state["assumptions"],
            ["The public API must remain compatible"],
        )
        self.assertEqual(
            state["threshold_reason"],
            "Five turns allow two recovery strategies",
        )

    def test_same_run_id_never_overwrites_existing_state_when_precheck_races(self) -> None:
        original = self.ledger.create_run(
            objective="Original objective",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )

        with patch.object(Path, "exists", return_value=False):
            with self.assertRaises(FileExistsError):
                self.ledger.create_run(
                    objective="Conflicting objective",
                    acceptance=acceptance(),
                    threshold=3,
                    baseline=repository_state(),
                    capabilities=capability_snapshot(),
                    entrypoint="omc-loop",
                )

        self.assertEqual(self.ledger.load_run(RUN_ID)["objective"], original["objective"])

    def test_concurrent_run_ids_are_unique(self) -> None:
        ledger = LoopLedger(self.repository, clock=lambda: NOW)

        def create(index: int) -> str:
            state = ledger.create_run(
                objective=f"Concurrent objective {index}",
                acceptance=acceptance(),
                threshold=3,
                baseline=repository_state(),
                capabilities=capability_snapshot(),
                entrypoint="omc-loop",
            )
            return str(state["run_id"])

        with ThreadPoolExecutor(max_workers=8) as pool:
            run_ids = list(pool.map(create, range(24)))

        self.assertEqual(len(run_ids), len(set(run_ids)))
        self.assertTrue(all(MODULE.RUN_ID_RE.fullmatch(run_id) for run_id in run_ids))

    def test_files_strength_requires_file_and_acceptance_fingerprints(self) -> None:
        weak = {
            "git_head": None,
            "worktree_fingerprint": "sha256:combined",
            "evidence_strength": "files",
        }
        with self.assertRaisesRegex(ValueError, "file_fingerprint"):
            self.ledger.create_run(
                objective="Work without Git",
                acceptance=acceptance(),
                threshold=3,
                baseline=weak,
                capabilities=capability_snapshot(),
                entrypoint="omc-loop",
            )

        weak["file_fingerprint"] = "sha256:files"
        weak["acceptance_fingerprint"] = "sha256:acceptance"
        state = self.ledger.create_run(
            objective="Work without Git",
            acceptance=acceptance(),
            threshold=3,
            baseline=weak,
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
        self.assertEqual(state["repository_state"]["evidence_strength"], "files")

    def test_successful_mutation_clears_pending_audit(self) -> None:
        state = self.ledger.create_run(
            objective="Audit this run",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )

        self.assertEqual(state["audit"]["sequence"], 1)
        self.assertIsNone(state["audit"]["pending"])

    def test_failed_atomic_replace_leaves_previous_json_parseable_and_unchanged(self) -> None:
        self.create_active_run()
        path = self.state_path()
        before = path.read_bytes()

        with patch.object(MODULE.os, "replace", side_effect=OSError("replace failed")):
            with self.assertRaisesRegex(OSError, "replace failed"):
                self.ledger.record_iteration(RUN_ID, blocked_iteration(1))

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(json.loads(before), json.loads(path.read_text(encoding="utf-8")))

    def test_audit_repair_is_idempotent_after_state_succeeds_but_audit_fails(self) -> None:
        self.create_active_run()
        original_write = MODULE._atomic_write_text

        def fail_audit(repository: Path, path: Path, content: str) -> None:
            if path.suffix == ".md":
                raise OSError("audit write failed")
            original_write(repository, path, content)

        payload = blocked_iteration(1)
        with patch.object(MODULE, "_atomic_write_text", side_effect=fail_audit):
            with self.assertRaisesRegex(OSError, "audit write failed"):
                self.ledger.record_iteration(RUN_ID, payload)

        pending = self.ledger.load_run(RUN_ID)
        self.assertIsNotNone(pending["audit"]["pending"])
        recovered = self.ledger.record_iteration(RUN_ID, payload)
        self.assertEqual(recovered.state["iteration_count"], 1)
        self.assertIsNone(recovered.state["audit"]["pending"])
        audit_path = (
            self.repository
            / ".ohmycodex"
            / "plans"
            / "loop-runs"
            / f"{RUN_ID}.md"
        )
        audit = audit_path.read_text(encoding="utf-8")
        self.assertEqual(audit.count("omc-audit-begin:3:"), 1)
        self.assertEqual(audit.count("omc-audit-end:3:"), 1)

    def test_audit_repair_is_idempotent_after_pending_clear_fails(self) -> None:
        self.create_active_run()
        original_write = MODULE._atomic_write_json
        writes = 0

        def fail_pending_clear(
            repository: Path,
            path: Path,
            payload: dict[str, object],
        ) -> None:
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("pending clear failed")
            original_write(repository, path, payload)

        payload = blocked_iteration(1)
        with patch.object(MODULE, "_atomic_write_json", side_effect=fail_pending_clear):
            with self.assertRaisesRegex(OSError, "pending clear failed"):
                self.ledger.record_iteration(RUN_ID, payload)

        self.assertIsNotNone(self.ledger.load_run(RUN_ID)["audit"]["pending"])
        recovered = self.ledger.record_iteration(RUN_ID, payload)
        self.assertIsNone(recovered.state["audit"]["pending"])
        audit_path = (
            self.repository
            / ".ohmycodex"
            / "plans"
            / "loop-runs"
            / f"{RUN_ID}.md"
        )
        audit = audit_path.read_text(encoding="utf-8")
        self.assertEqual(audit.count("omc-audit-begin:3:"), 1)
        self.assertEqual(audit.count("omc-audit-end:3:"), 1)

    def test_audit_repair_rejects_end_marker_without_complete_event(self) -> None:
        self.create_active_run()
        original_write = MODULE._atomic_write_text

        def fail_audit(repository: Path, path: Path, content: str) -> None:
            if path.suffix == ".md":
                raise OSError("audit write failed")
            original_write(repository, path, content)

        payload = blocked_iteration(1)
        with patch.object(MODULE, "_atomic_write_text", side_effect=fail_audit):
            with self.assertRaises(OSError):
                self.ledger.record_iteration(RUN_ID, payload)

        pending = self.ledger.load_run(RUN_ID)["audit"]["pending"]
        audit_path = (
            self.repository
            / ".ohmycodex"
            / "plans"
            / "loop-runs"
            / f"{RUN_ID}.md"
        )
        audit_path.write_text(
            audit_path.read_text(encoding="utf-8")
            + f"\n<!-- omc-audit-end:{pending['sequence']}:{pending['hash']} -->\n",
            encoding="utf-8",
        )

        with self.assertRaisesRegex(ValueError, "audit marker"):
            self.ledger.record_iteration(RUN_ID, payload)
        self.assertIsNotNone(self.ledger.load_run(RUN_ID)["audit"]["pending"])

    def test_audit_records_required_fields_without_copying_raw_logs(self) -> None:
        self.create_active_run()
        rejected = blocked_iteration(1)
        rejected["commands"][0]["stdout"] = "SECRET RAW OUTPUT"
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            self.ledger.record_iteration(RUN_ID, rejected)

        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        audit_path = (
            self.repository
            / ".ohmycodex"
            / "plans"
            / "loop-runs"
            / f"{RUN_ID}.md"
        )
        audit = audit_path.read_text(encoding="utf-8")
        required = {
            "action",
            "tools",
            "commands",
            "result",
            "material_progress",
            "blocker",
            "residual_risks",
            "next_action",
            "evidence",
        }
        detail_lines = [
            line for line in audit.splitlines() if line.startswith("- Details: `")
        ]
        self.assertEqual(len(detail_lines), 3)
        for line in detail_lines:
            details = json.loads(line.removeprefix("- Details: `").removesuffix("`"))
            self.assertEqual(set(details), required)
        self.assertNotIn("SECRET RAW OUTPUT", audit)
        self.assertNotIn('"stdout"', audit)
        self.assertNotIn('"stderr"', audit)
        self.assertNotIn('"logs"', audit)

    def test_activate_binds_goal_and_is_idempotent_for_same_goal(self) -> None:
        created = self.ledger.create_run(
            objective="Activate this run",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )

        active = self.ledger.activate_run(RUN_ID, "goal-123")
        repeated = self.ledger.activate_run(RUN_ID, "goal-123")

        self.assertEqual(active["status"], "active")
        self.assertEqual(active["goal_id"], "goal-123")
        self.assertEqual(active["revision"], created["revision"] + 1)
        self.assertEqual(repeated, active)

    def test_activate_rejects_conflicting_goal_id(self) -> None:
        self.ledger.create_run(
            objective="Activate this run",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
        self.ledger.activate_run(RUN_ID, "goal-123")

        with self.assertRaisesRegex(ValueError, "different Goal"):
            self.ledger.activate_run(RUN_ID, "goal-456")

    def test_three_identical_blockers_block_at_threshold_three(self) -> None:
        self.create_active_run(threshold=3)

        first = self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        second = self.ledger.record_iteration(RUN_ID, blocked_iteration(2))
        third = self.ledger.record_iteration(RUN_ID, blocked_iteration(3))

        self.assertEqual(first.kind, "continue")
        self.assertEqual(first.state["no_progress_count"], 1)
        self.assertEqual(second.kind, "continue")
        self.assertEqual(second.state["no_progress_count"], 2)
        self.assertEqual(third.kind, "blocked")
        self.assertEqual(third.state["no_progress_count"], 3)
        self.assertEqual(third.state["status"], "blocked")

    def test_duplicate_iteration_id_is_idempotent(self) -> None:
        self.create_active_run()
        payload = blocked_iteration(1)

        first = self.ledger.record_iteration(RUN_ID, payload)
        repeated = self.ledger.record_iteration(RUN_ID, payload)

        self.assertEqual(repeated, first)
        self.assertEqual(repeated.state["iteration_count"], 1)
        self.assertEqual(repeated.state["no_progress_count"], 1)

    def test_duplicate_iteration_id_with_different_payload_is_rejected(self) -> None:
        self.create_active_run()
        payload = blocked_iteration(1)
        self.ledger.record_iteration(RUN_ID, payload)
        changed = copy.deepcopy(payload)
        changed["commands"][0]["summary"] = "A different failure"

        with self.assertRaisesRegex(ValueError, "different payload"):
            self.ledger.record_iteration(RUN_ID, changed)

    def test_iteration_rejects_duplicate_command_and_evidence_ids(self) -> None:
        self.create_active_run()
        payload = passing_iteration(1)
        payload["acceptance_updates"][0]["evidence"][0]["id"] = "command-1"

        with self.assertRaisesRegex(ValueError, "duplicate evidence id"):
            self.ledger.record_iteration(RUN_ID, payload)

    def test_iteration_numbers_must_be_contiguous(self) -> None:
        self.create_active_run()
        with self.assertRaisesRegex(ValueError, "iteration_number must be 1"):
            self.ledger.record_iteration(RUN_ID, blocked_iteration(2))

    def test_old_iteration_id_cannot_be_reused_for_a_new_turn(self) -> None:
        self.create_active_run(threshold=10)
        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        self.ledger.record_iteration(RUN_ID, blocked_iteration(2))
        replay = blocked_iteration(3)
        replay["iteration_id"] = "turn-0001"

        with self.assertRaisesRegex(ValueError, "iteration_id was already used"):
            self.ledger.record_iteration(RUN_ID, replay)

    def test_changed_evidence_or_next_action_starts_new_blocker_sequence(self) -> None:
        self.create_active_run(threshold=5)
        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        second = self.ledger.record_iteration(RUN_ID, blocked_iteration(2))
        changed = self.ledger.record_iteration(
            RUN_ID,
            blocked_iteration(
                3,
                command_summary="A different retry failure",
                next_action="Inspect the request adapter",
            ),
        )

        self.assertEqual(second.state["no_progress_count"], 2)
        self.assertEqual(changed.kind, "continue")
        self.assertEqual(changed.state["no_progress_count"], 1)

    def test_acceptance_improvement_resets_no_progress_count(self) -> None:
        items = acceptance()
        items.append(
            {
                "id": "AC-2",
                "description": "Review confirms no regression",
                "required": True,
            }
        )
        self.create_active_run(threshold=5, acceptance_items=items)
        blocked = self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        improved = self.ledger.record_iteration(RUN_ID, passing_iteration(2))

        self.assertEqual(blocked.state["no_progress_count"], 1)
        self.assertTrue(improved.material_progress)
        self.assertEqual(improved.kind, "continue")
        self.assertEqual(improved.state["no_progress_count"], 0)

    def test_repository_change_requires_evidence_backed_progress_claim(self) -> None:
        self.create_active_run(threshold=5)
        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        changed = blocked_iteration(2, fingerprint="sha256:changed")
        changed["progress_claim"] = {
            "kind": "repository_change",
            "reason": "The implementation changed",
            "evidence_ids": [],
        }

        with self.assertRaisesRegex(ValueError, "requires evidence"):
            self.ledger.record_iteration(RUN_ID, changed)

        changed["progress_claim"]["evidence_ids"] = ["command-2"]
        progressed = self.ledger.record_iteration(RUN_ID, changed)
        self.assertTrue(progressed.material_progress)
        self.assertEqual(progressed.state["no_progress_count"], 0)

    def test_new_external_or_user_decision_evidence_resets_count(self) -> None:
        self.create_active_run(threshold=5)
        self.ledger.record_iteration(RUN_ID, blocked_iteration(1))
        external = self.ledger.record_iteration(RUN_ID, external_progress_iteration(2))
        user = self.ledger.record_iteration(
            RUN_ID,
            external_progress_iteration(3, kind="user_decision"),
        )

        self.assertTrue(external.material_progress)
        self.assertEqual(external.state["no_progress_count"], 0)
        self.assertTrue(user.material_progress)
        self.assertEqual(user.state["no_progress_count"], 0)

    def test_repeated_external_fingerprint_is_not_material_progress(self) -> None:
        self.create_active_run(threshold=5)
        first = external_progress_iteration(1)
        first_result = self.ledger.record_iteration(RUN_ID, first)
        repeated = external_progress_iteration(2)
        repeated_evidence = repeated["check_updates"][0]["evidence"][0]
        repeated_evidence["external_fingerprint"] = "external:1"

        repeated_result = self.ledger.record_iteration(RUN_ID, repeated)

        self.assertTrue(first_result.material_progress)
        self.assertFalse(repeated_result.material_progress)

    def test_repeated_user_decision_is_not_material_progress(self) -> None:
        self.create_active_run(threshold=5)
        first = external_progress_iteration(1, kind="user_decision")
        first_result = self.ledger.record_iteration(RUN_ID, first)
        repeated = external_progress_iteration(2, kind="user_decision")
        repeated["check_updates"][0]["evidence"][0]["decision_id"] = "decision-1"

        repeated_result = self.ledger.record_iteration(RUN_ID, repeated)

        self.assertTrue(first_result.material_progress)
        self.assertFalse(repeated_result.material_progress)

    def test_completion_requires_all_required_current_pass_evidence(self) -> None:
        self.create_active_run()
        completed = self.ledger.record_iteration(RUN_ID, passing_iteration(1))

        self.assertEqual(completed.kind, "complete")
        self.assertEqual(completed.state["status"], "complete")
        self.assertIsNotNone(completed.state["closed_at"])

    def test_bounded_unavailable_cannot_pass_required_acceptance(self) -> None:
        self.create_active_run()
        payload = passing_iteration(1)
        evidence = payload["acceptance_updates"][0]["evidence"][0]
        evidence["kind"] = "bounded_unavailable"
        payload["acceptance_updates"][0]["status"] = "bounded_unavailable"

        unavailable = self.ledger.record_iteration(RUN_ID, payload)
        self.assertEqual(unavailable.kind, "continue")
        self.assertEqual(unavailable.state["acceptance"][0]["status"], "bounded_unavailable")
        self.assertEqual(
            self.ledger.load_run(RUN_ID)["acceptance"][0]["status"],
            "bounded_unavailable",
        )

    def test_policy_blocker_can_block_immediately_with_bounded_evidence(self) -> None:
        self.create_active_run(threshold=100)
        payload = blocked_iteration(1)
        payload["blocker"]["kind"] = "policy"

        blocked = self.ledger.record_iteration(RUN_ID, payload)
        self.assertEqual(blocked.kind, "blocked")
        self.assertEqual(blocked.state["status"], "blocked")
        self.assertEqual(blocked.state["no_progress_count"], 0)

    def test_wait_requires_schedule_id_only_for_scheduled_strategy(self) -> None:
        self.create_active_run()

        with self.assertRaisesRegex(ValueError, "scheduled wait requires a schedule_id"):
            self.ledger.record_wait(RUN_ID, external_wait(), None)

        waiting = self.ledger.record_wait(
            RUN_ID,
            external_wait(),
            "schedule-123",
        )
        self.assertEqual(waiting["status"], "waiting")
        self.assertEqual(waiting["scheduled_task_id"], "schedule-123")

        other_repository = Path(tempfile.mkdtemp()).resolve()
        self.addCleanup(lambda: __import__("shutil").rmtree(other_repository))
        other = LoopLedger(
            other_repository,
            clock=lambda: NOW,
            run_id_factory=lambda _now: "20260712T120001Z-abcdef123457",
        )
        other.create_run(
            objective="Wait without Scheduled support",
            acceptance=acceptance(),
            threshold=3,
            baseline=repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
        other.activate_run("20260712T120001Z-abcdef123457", "goal-456")
        with self.assertRaisesRegex(ValueError, "non-scheduled wait forbids a schedule_id"):
            other.record_wait(
                "20260712T120001Z-abcdef123457",
                external_wait(strategy="recoverable_goal"),
                "schedule-456",
            )

    def test_wait_remains_waiting_when_external_fingerprint_is_unchanged(self) -> None:
        self.create_active_run()
        self.ledger.record_wait(RUN_ID, external_wait(), "schedule-123")

        reconciled = self.ledger.reconcile_run(
            RUN_ID,
            repository_state(),
            external_state=external_wait(),
        )

        self.assertEqual(reconciled.kind, "wait")
        self.assertFalse(reconciled.material_progress)
        self.assertEqual(reconciled.state["status"], "waiting")
        self.assertEqual(reconciled.state["scheduled_task_id"], "schedule-123")

    def test_leaving_scheduled_wait_requires_matching_cleanup_confirmation(self) -> None:
        self.create_active_run()
        self.ledger.record_wait(RUN_ID, external_wait(), "schedule-123")
        changed = external_wait("ci:passed", observed_at="2026-07-12T12:06:00Z")

        with self.assertRaisesRegex(ValueError, "requires cleanup_confirmation"):
            self.ledger.reconcile_run(
                RUN_ID,
                repository_state(),
                external_state=changed,
            )
        with self.assertRaisesRegex(ValueError, "does not match"):
            self.ledger.reconcile_run(
                RUN_ID,
                repository_state(),
                external_state=changed,
                cleanup_confirmation=cleanup_confirmation("schedule-other"),
            )

        resumed = self.ledger.reconcile_run(
            RUN_ID,
            repository_state(),
            external_state=changed,
            cleanup_confirmation=cleanup_confirmation(),
        )
        self.assertEqual(resumed.kind, "continue")
        self.assertTrue(resumed.material_progress)
        self.assertEqual(resumed.state["status"], "active")
        self.assertIsNone(resumed.state["scheduled_task_id"])
        self.assertIsNone(resumed.state["external_wait"])

    def test_stale_external_snapshot_cannot_end_wait(self) -> None:
        self.create_active_run()
        self.ledger.record_wait(RUN_ID, external_wait(), "schedule-123")
        stale = external_wait(
            "ci:passed",
            observed_at="2026-07-12T12:04:00Z",
        )

        with self.assertRaisesRegex(ValueError, "newer than the recorded wait"):
            self.ledger.reconcile_run(
                RUN_ID,
                repository_state(),
                external_state=stale,
                cleanup_confirmation=cleanup_confirmation(),
            )

    def test_reconcile_invalidates_repository_evidence_after_git_revision_change(self) -> None:
        items = acceptance()
        items.append(
            {
                "id": "AC-2",
                "description": "Review confirms no regression",
                "required": True,
            }
        )
        self.create_active_run(acceptance_items=items)
        self.ledger.record_iteration(RUN_ID, passing_iteration(1))
        changed_revision = repository_state()
        changed_revision["git_head"] = "def456"

        reconciled = self.ledger.reconcile_run(RUN_ID, changed_revision)

        first = reconciled.state["acceptance"][0]
        self.assertEqual(first["status"], "unknown")
        self.assertTrue(first["evidence"][0]["stale"])
        self.assertEqual(reconciled.state["repository_state"], changed_revision)

    def test_files_strength_reconciliation_invalidates_changed_fingerprints(self) -> None:
        items = acceptance()
        items.append(
            {
                "id": "AC-2",
                "description": "Review confirms no regression",
                "required": True,
            }
        )
        self.ledger.create_run(
            objective="Verify without Git",
            acceptance=items,
            threshold=3,
            baseline=file_repository_state(),
            capabilities=capability_snapshot(),
            entrypoint="omc-loop",
        )
        self.ledger.activate_run(RUN_ID, "goal-123")
        payload = passing_iteration(1)
        payload["repository_state"] = file_repository_state()
        payload["acceptance_updates"][0]["evidence"][0][
            "repository_fingerprint"
        ] = "sha256:file-baseline"
        self.ledger.record_iteration(RUN_ID, payload)

        changed = file_repository_state(
            acceptance_fingerprint="sha256:acceptance-v2"
        )
        reconciled = self.ledger.reconcile_run(RUN_ID, changed)

        first = reconciled.state["acceptance"][0]
        self.assertEqual(first["status"], "unknown")
        self.assertTrue(first["evidence"][0]["stale"])

    def test_reconcile_reactivates_blocked_run_after_material_external_change(self) -> None:
        self.create_active_run(threshold=3)
        self.ledger.record_iteration(RUN_ID, external_blocked_iteration(1))
        self.ledger.record_iteration(RUN_ID, external_blocked_iteration(2))
        blocked = self.ledger.record_iteration(RUN_ID, external_blocked_iteration(3))
        self.assertEqual(blocked.kind, "blocked")

        changed = external_wait("ci:passed", strategy="recoverable_goal")
        resumed = self.ledger.reconcile_run(
            RUN_ID,
            repository_state(),
            external_state=changed,
        )

        self.assertEqual(resumed.kind, "continue")
        self.assertTrue(resumed.material_progress)
        self.assertEqual(resumed.state["status"], "active")
        self.assertEqual(resumed.state["no_progress_count"], 0)
        self.assertTrue(resumed.state["checks"][0]["evidence"][0]["stale"])

    def test_unrelated_external_change_cannot_reactivate_blocked_run(self) -> None:
        self.create_active_run(threshold=3)
        self.ledger.record_iteration(RUN_ID, external_blocked_iteration(1))
        self.ledger.record_iteration(RUN_ID, external_blocked_iteration(2))
        self.ledger.record_iteration(RUN_ID, external_blocked_iteration(3))
        unrelated = external_wait("deploy:passed", strategy="recoverable_goal")
        unrelated["condition"] = "Wait for an unrelated deployment"

        unchanged = self.ledger.reconcile_run(
            RUN_ID,
            repository_state(),
            external_state=unrelated,
        )

        self.assertEqual(unchanged.kind, "blocked")
        self.assertFalse(unchanged.material_progress)
        self.assertEqual(unchanged.state["status"], "blocked")

    def test_terminal_transition_requires_confirmed_schedule_cleanup(self) -> None:
        self.create_active_run()
        self.ledger.record_wait(RUN_ID, external_wait(), "schedule-123")
        outcome = {"kind": "paused", "reason": "The user stopped the run"}

        with self.assertRaisesRegex(ValueError, "requires cleanup_confirmation"):
            self.ledger.finish_run(RUN_ID, outcome, finish_evidence())

        stale_cleanup = cleanup_confirmation()
        stale_cleanup["observed_at"] = "2026-07-12T12:04:00Z"
        with self.assertRaisesRegex(ValueError, "predates the recorded wait"):
            self.ledger.finish_run(
                RUN_ID,
                outcome,
                finish_evidence(),
                cleanup_confirmation=stale_cleanup,
            )

        paused = self.ledger.finish_run(
            RUN_ID,
            outcome,
            finish_evidence(),
            cleanup_confirmation=cleanup_confirmation(),
        )
        self.assertEqual(paused["status"], "paused")
        self.assertEqual(paused["outcome"], outcome)
        self.assertIsNotNone(paused["closed_at"])
        self.assertIsNone(paused["scheduled_task_id"])
        self.assertIsNone(paused["external_wait"])

    def test_paused_run_requires_explicit_resume_signal(self) -> None:
        self.create_active_run()
        outcome = {"kind": "paused", "reason": "The host paused the run"}
        self.ledger.finish_run(RUN_ID, outcome, finish_evidence())

        unchanged = self.ledger.reconcile_run(RUN_ID, repository_state())
        self.assertEqual(unchanged.kind, "paused")
        self.assertEqual(unchanged.state["status"], "paused")

        resumed = self.ledger.reconcile_run(
            RUN_ID,
            repository_state(),
            resume_signal=resume_signal(),
        )
        self.assertEqual(resumed.kind, "continue")
        self.assertEqual(resumed.state["status"], "active")
        self.assertIsNone(resumed.state["outcome"])
        self.assertIsNone(resumed.state["closed_at"])

    def test_finish_rejects_cross_terminal_state_rewrites(self) -> None:
        self.create_active_run()
        paused_outcome = {"kind": "paused", "reason": "The host paused the run"}
        self.ledger.finish_run(RUN_ID, paused_outcome, finish_evidence())

        with self.assertRaisesRegex(ValueError, "invalid finish transition"):
            self.ledger.finish_run(
                RUN_ID,
                {"kind": "blocked", "reason": "A different terminal claim"},
                finish_evidence(),
            )

    def test_cli_subcommands_dispatch_once_and_emit_one_json_result(self) -> None:
        create_payload = {
            "objective": "CLI objective",
            "acceptance": acceptance(),
            "threshold": 3,
            "baseline": repository_state(),
            "capabilities": capability_snapshot(),
            "entrypoint": "omc-loop",
            "assumptions": [],
            "threshold_reason": "User selected the threshold",
        }
        cases = {
            "create": (create_payload, ["create"]),
            "activate": ({"goal_id": "goal-123"}, ["activate", "--run-id", RUN_ID]),
            "iterate": (blocked_iteration(1), ["iterate", "--run-id", RUN_ID]),
            "wait": (
                {"external_state": external_wait(), "schedule_id": "schedule-123"},
                ["wait", "--run-id", RUN_ID],
            ),
            "reconcile": (
                {
                    "current_repository_state": repository_state(),
                    "external_state": None,
                    "resume_signal": None,
                    "cleanup_confirmation": None,
                },
                ["reconcile", "--run-id", RUN_ID],
            ),
            "finish": (
                {
                    "outcome": {"kind": "paused", "reason": "Stopped"},
                    "evidence": finish_evidence(),
                    "cleanup_confirmation": None,
                },
                ["finish", "--run-id", RUN_ID],
            ),
        }

        class FakeLedger:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def _state(self, name: str) -> dict[str, object]:
                self.calls.append(name)
                return {"called": name}

            def create_run(self, **_kwargs: object) -> dict[str, object]:
                return self._state("create")

            def activate_run(self, *_args: object) -> dict[str, object]:
                return self._state("activate")

            def record_iteration(self, *_args: object) -> LoopDecision:
                state = self._state("iterate")
                return LoopDecision("continue", state, "continue", False)

            def record_wait(self, *_args: object) -> dict[str, object]:
                return self._state("wait")

            def reconcile_run(self, *_args: object, **_kwargs: object) -> LoopDecision:
                state = self._state("reconcile")
                return LoopDecision("continue", state, "reconciled", False)

            def finish_run(self, *_args: object, **_kwargs: object) -> dict[str, object]:
                return self._state("finish")

            def load_run(self, *_args: object) -> dict[str, object]:
                return self._state("show")

        for expected, (payload, command) in cases.items():
            with self.subTest(command=expected):
                input_path = self.repository / f"{expected}.json"
                input_path.write_text(json.dumps(payload), encoding="utf-8")
                fake = FakeLedger()
                output = io.StringIO()
                with patch.object(MODULE, "LoopLedger", return_value=fake):
                    with redirect_stdout(output):
                        exit_code = MODULE.main(
                            [
                                "--repository",
                                str(self.repository),
                                *command,
                                "--input",
                                str(input_path),
                            ]
                        )
                self.assertEqual(exit_code, 0)
                self.assertEqual(fake.calls, [expected])
                self.assertEqual(len(output.getvalue().splitlines()), 1)
                self.assertIn("state", json.loads(output.getvalue())) if expected in {
                    "iterate",
                    "reconcile",
                } else self.assertEqual(json.loads(output.getvalue())["called"], expected)

        fake = FakeLedger()
        output = io.StringIO()
        with patch.object(MODULE, "LoopLedger", return_value=fake):
            with redirect_stdout(output):
                exit_code = MODULE.main(
                    ["--repository", str(self.repository), "show", "--run-id", RUN_ID]
                )
        self.assertEqual(exit_code, 0)
        self.assertEqual(fake.calls, ["show"])
        self.assertEqual(json.loads(output.getvalue())["called"], "show")

    def test_cli_create_and_show_subprocess_smoke(self) -> None:
        input_path = self.repository / "create.json"
        input_path.write_text(
            json.dumps(
                {
                    "objective": "CLI smoke objective",
                    "acceptance": acceptance(),
                    "threshold": 3,
                    "baseline": repository_state(),
                    "capabilities": capability_snapshot(),
                    "entrypoint": "omc-loop",
                    "assumptions": [],
                    "threshold_reason": "User selected the threshold",
                }
            ),
            encoding="utf-8",
        )
        created = subprocess.run(
            [
                sys.executable,
                str(LEDGER_SCRIPT),
                "--repository",
                str(self.repository),
                "create",
                "--input",
                str(input_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        state = json.loads(created.stdout)
        shown = subprocess.run(
            [
                sys.executable,
                str(LEDGER_SCRIPT),
                "--repository",
                str(self.repository),
                "show",
                "--run-id",
                state["run_id"],
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(json.loads(shown.stdout), state)


if __name__ == "__main__":
    unittest.main()
