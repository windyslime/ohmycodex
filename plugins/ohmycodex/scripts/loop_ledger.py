#!/usr/bin/env python3
"""Persist OhMyCodex continuation state without controlling native Goals."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
import threading
from collections.abc import Callable, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

try:
    import fcntl
except ImportError:  # pragma: no cover - exercised only on non-POSIX hosts
    fcntl = None


DecisionKind = Literal["continue", "wait", "complete", "blocked", "paused"]
RUN_ID_RE = re.compile(r"^\d{8}T\d{6}Z-[0-9a-f]{12}$")
AUDIT_MARKER_RE = re.compile(
    r"<!-- omc-audit-(begin|end):(\d+):([0-9a-f]{64}) -->"
)
ACCEPTANCE_FIELDS = {"id", "description", "required"}
REPOSITORY_STATE_FIELDS = {"git_head", "worktree_fingerprint", "evidence_strength"}
ENTRYPOINTS = {"omc-loop", "omc-intentgate", "omc-letgo"}
STATUSES = {"preparing", "active", "waiting", "complete", "blocked", "paused"}
ACCEPTANCE_STATE_FIELDS = {"id", "description", "required", "status", "evidence"}
AUDIT_FIELDS = {"sequence", "pending"}
AUDIT_EVENT_FIELDS = {"sequence", "kind", "observed_at", "summary", "details", "hash"}
AUDIT_DETAIL_FIELDS = {
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
AUDIT_COMMAND_FIELDS = {"argv", "result", "summary"}
RAW_AUDIT_FIELDS = {
    "stdout",
    "stderr",
    "log",
    "logs",
    "raw_log",
    "raw_logs",
    "raw_output",
}
ITERATION_FIELDS = {
    "iteration_number",
    "iteration_id",
    "observed_at",
    "action",
    "tools",
    "commands",
    "repository_state",
    "acceptance_updates",
    "check_updates",
    "progress_claim",
    "blocker",
    "residual_risks",
    "next_action",
}
COMMAND_FIELDS = {"id", "argv", "exit_code", "result", "summary"}
EVIDENCE_FIELDS = {
    "id",
    "kind",
    "summary",
    "reference",
    "repository_fingerprint",
    "external_fingerprint",
    "decision_id",
}
EVIDENCE_STATE_FIELDS = EVIDENCE_FIELDS | {"stale"}
ACCEPTANCE_UPDATE_FIELDS = {"id", "status", "evidence"}
CHECK_UPDATE_FIELDS = {"id", "description", "status", "evidence"}
CHECK_STATE_FIELDS = {"id", "description", "status", "evidence"}
PROGRESS_FIELDS = {"kind", "reason", "evidence_ids"}
BLOCKER_FIELDS = {"kind", "key", "summary", "evidence_ids", "next_action"}
LAST_ITERATION_FIELDS = ITERATION_FIELDS | {
    "payload_hash",
    "material_progress",
    "decision_kind",
    "decision_reason",
}
OUTCOME_FIELDS = {"kind", "reason"}
EXTERNAL_WAIT_FIELDS = {
    "strategy",
    "condition",
    "fingerprint",
    "observed_at",
    "next_action",
}
CLEANUP_CONFIRMATION_FIELDS = {"schedule_id", "deleted", "observed_at"}
RESUME_SIGNAL_FIELDS = {"kind", "id", "reason", "observed_at"}
FINISH_EVIDENCE_FIELDS = {
    "observed_at",
    "action",
    "tools",
    "commands",
    "residual_risks",
    "next_action",
}
EVIDENCE_KINDS = {"command", "inspection", "external", "user_decision", "bounded_unavailable"}
RESULTS = {"passed", "failed", "unavailable"}
ACCEPTANCE_STATUSES = {"unknown", "failed", "passed", "bounded_unavailable"}
STATE_FIELDS = {
    "schema_version",
    "run_id",
    "revision",
    "status",
    "entrypoint",
    "objective",
    "assumptions",
    "goal_id",
    "threshold",
    "threshold_reason",
    "iteration_count",
    "iteration_ids",
    "no_progress_count",
    "blocker_key",
    "blocker_signature",
    "baseline",
    "repository_state",
    "acceptance",
    "checks",
    "capability_snapshot",
    "scheduled_task_id",
    "external_wait",
    "last_iteration",
    "outcome",
    "closed_at",
    "audit",
    "created_at",
    "updated_at",
}
MAX_TEXT = 2_000
MAX_CAPABILITY_BYTES = 1_000_000
MAX_STATE_BYTES = 5_000_000
MAX_AUDIT_EVENT_BYTES = 64_000
_PROCESS_LOCKS: dict[str, threading.RLock] = {}
_PROCESS_LOCKS_GUARD = threading.Lock()


@dataclass(frozen=True)
class LoopDecision:
    kind: DecisionKind
    state: dict[str, object]
    reason: str
    material_progress: bool


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_run_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(6)}"


def _expect_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")


def _text(value: object, label: str, *, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > limit:
        raise ValueError(f"{label} exceeds {limit} characters")
    return normalized


def _timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("clock must return a timezone-aware datetime")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_timestamp(value: object, label: str) -> str:
    text = _text(value, label, limit=64)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return _timestamp(parsed)


def _parsed_timestamp(value: object, label: str) -> datetime:
    normalized = _normalize_timestamp(value, label)
    return datetime.fromisoformat(normalized.replace("Z", "+00:00"))


def _normalize_repository_state(value: Mapping[str, object]) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("repository state must be an object")
    strength = value.get("evidence_strength")
    expected = set(REPOSITORY_STATE_FIELDS)
    if strength == "files":
        expected.update({"file_fingerprint", "acceptance_fingerprint"})
    _expect_exact_keys(value, expected, "repository state")
    git_head = value["git_head"]
    if git_head is not None:
        git_head = _text(git_head, "git_head", limit=256)
    fingerprint = _text(
        value["worktree_fingerprint"], "worktree_fingerprint", limit=256
    )
    if strength not in {"git", "files"}:
        raise ValueError("evidence_strength must be git or files")
    if strength == "git" and git_head is None:
        raise ValueError("git evidence requires git_head")
    normalized = {
        "git_head": git_head,
        "worktree_fingerprint": fingerprint,
        "evidence_strength": strength,
    }
    if strength == "files":
        normalized["file_fingerprint"] = _text(
            value["file_fingerprint"], "file_fingerprint", limit=256
        )
        normalized["acceptance_fingerprint"] = _text(
            value["acceptance_fingerprint"], "acceptance_fingerprint", limit=256
        )
    return normalized


def _normalize_acceptance(
    items: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    if not isinstance(items, (list, tuple)) or not items:
        raise ValueError("acceptance must contain at least one item")
    normalized: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"acceptance[{index}] must be an object")
        _expect_exact_keys(item, ACCEPTANCE_FIELDS, f"acceptance[{index}]")
        identifier = _text(item["id"], f"acceptance[{index}].id", limit=64)
        if identifier in identifiers:
            raise ValueError(f"duplicate acceptance id: {identifier}")
        identifiers.add(identifier)
        required = item["required"]
        if type(required) is not bool:
            raise ValueError(f"acceptance[{index}].required must be a boolean")
        normalized.append(
            {
                "id": identifier,
                "description": _text(
                    item["description"], f"acceptance[{index}].description"
                ),
                "required": required,
                "status": "unknown",
                "evidence": [],
            }
        )
    if not any(item["required"] for item in normalized):
        raise ValueError("acceptance must contain at least one required item")
    return normalized


def _normalize_assumptions(values: Sequence[str]) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise ValueError("assumptions must be a list of strings")
    if len(values) > 100:
        raise ValueError("assumptions contains too many items")
    return [_text(value, f"assumptions[{index}]", limit=1_000) for index, value in enumerate(values)]


def _text_list(value: object, label: str, *, limit: int = 100) -> list[str]:
    if not isinstance(value, list) or len(value) > limit:
        raise ValueError(f"{label} must be a bounded list")
    return [_text(item, f"{label}[{index}]", limit=1_000) for index, item in enumerate(value)]


def _normalize_command(value: object, index: int) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"commands[{index}] must be an object")
    _expect_exact_keys(value, COMMAND_FIELDS, f"commands[{index}]")
    argv = _text_list(value["argv"], f"commands[{index}].argv", limit=100)
    if not argv:
        raise ValueError(f"commands[{index}].argv must not be empty")
    exit_code = value["exit_code"]
    if type(exit_code) is not int:
        raise ValueError(f"commands[{index}].exit_code must be an integer")
    result = value["result"]
    if result not in RESULTS:
        raise ValueError(f"commands[{index}].result is invalid")
    return {
        "id": _text(value["id"], f"commands[{index}].id", limit=128),
        "argv": argv,
        "exit_code": exit_code,
        "result": result,
        "summary": _text(value["summary"], f"commands[{index}].summary"),
    }


def _normalize_evidence(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    _expect_exact_keys(value, EVIDENCE_FIELDS, label)
    kind = value["kind"]
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"{label}.kind is invalid")
    normalized: dict[str, object] = {
        "id": _text(value["id"], f"{label}.id", limit=128),
        "kind": kind,
        "summary": _text(value["summary"], f"{label}.summary"),
        "reference": _text(value["reference"], f"{label}.reference", limit=1_000),
    }
    for field in ("repository_fingerprint", "external_fingerprint", "decision_id"):
        field_value = value[field]
        normalized[field] = (
            None
            if field_value is None
            else _text(field_value, f"{label}.{field}", limit=256)
        )
    return normalized


def _normalize_status_updates(
    values: object,
    *,
    checks: bool,
) -> list[dict[str, object]]:
    label = "check_updates" if checks else "acceptance_updates"
    expected = CHECK_UPDATE_FIELDS if checks else ACCEPTANCE_UPDATE_FIELDS
    if not isinstance(values, list) or len(values) > 1_000:
        raise ValueError(f"{label} must be a bounded list")
    normalized: list[dict[str, object]] = []
    identifiers: set[str] = set()
    for index, value in enumerate(values):
        if not isinstance(value, Mapping):
            raise ValueError(f"{label}[{index}] must be an object")
        _expect_exact_keys(value, expected, f"{label}[{index}]")
        identifier = _text(value["id"], f"{label}[{index}].id", limit=64)
        if identifier in identifiers:
            raise ValueError(f"duplicate update id: {identifier}")
        identifiers.add(identifier)
        status = value["status"]
        if status not in ACCEPTANCE_STATUSES:
            raise ValueError(f"{label}[{index}].status is invalid")
        evidence_values = value["evidence"]
        if not isinstance(evidence_values, list) or len(evidence_values) > 1_000:
            raise ValueError(f"{label}[{index}].evidence must be a bounded list")
        item: dict[str, object] = {
            "id": identifier,
            "status": status,
            "evidence": [
                _normalize_evidence(evidence, f"{label}[{index}].evidence[{evidence_index}]")
                for evidence_index, evidence in enumerate(evidence_values)
            ],
        }
        if checks:
            item["description"] = _text(
                value["description"], f"{label}[{index}].description"
            )
        normalized.append(item)
    return normalized


def _normalize_progress(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("progress_claim must be an object")
    _expect_exact_keys(value, PROGRESS_FIELDS, "progress_claim")
    kind = value["kind"]
    if kind not in {"none", "repository_change", "external_change", "user_decision"}:
        raise ValueError("progress_claim.kind is invalid")
    reason = value["reason"]
    if kind == "none":
        if reason != "":
            raise ValueError("a none progress claim must have an empty reason")
    else:
        reason = _text(reason, "progress_claim.reason")
    return {
        "kind": kind,
        "reason": reason,
        "evidence_ids": _text_list(value["evidence_ids"], "progress_claim.evidence_ids"),
    }


def _normalize_blocker(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError("blocker must be an object or null")
    _expect_exact_keys(value, BLOCKER_FIELDS, "blocker")
    kind = value["kind"]
    if kind not in {"technical", "policy"}:
        raise ValueError("blocker.kind must be technical or policy")
    evidence_ids = _text_list(value["evidence_ids"], "blocker.evidence_ids")
    if not evidence_ids:
        raise ValueError("blocker.evidence_ids must not be empty")
    return {
        "kind": kind,
        "key": _text(value["key"], "blocker.key", limit=256),
        "summary": _text(value["summary"], "blocker.summary"),
        "evidence_ids": evidence_ids,
        "next_action": _text(value["next_action"], "blocker.next_action"),
    }


def _normalize_external_wait(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("external_state must be an object")
    _expect_exact_keys(value, EXTERNAL_WAIT_FIELDS, "external_state")
    strategy = value["strategy"]
    if strategy not in {"scheduled", "background_terminal", "recoverable_goal"}:
        raise ValueError("external_state.strategy is invalid")
    return {
        "strategy": strategy,
        "condition": _text(value["condition"], "external_state.condition"),
        "fingerprint": _text(
            value["fingerprint"], "external_state.fingerprint", limit=256
        ),
        "observed_at": _normalize_timestamp(
            value["observed_at"], "external_state.observed_at"
        ),
        "next_action": _text(value["next_action"], "external_state.next_action"),
    }


def _normalize_iteration(value: Mapping[str, object]) -> dict[str, object]:
    _expect_exact_keys(value, ITERATION_FIELDS, "iteration")
    number = value["iteration_number"]
    if type(number) is not int or number < 1:
        raise ValueError("iteration_number must be a positive integer")
    commands_value = value["commands"]
    if not isinstance(commands_value, list) or len(commands_value) > 100:
        raise ValueError("commands must be a bounded list")
    normalized = {
        "iteration_number": number,
        "iteration_id": _text(value["iteration_id"], "iteration_id", limit=128),
        "observed_at": _normalize_timestamp(value["observed_at"], "observed_at"),
        "action": _text(value["action"], "action"),
        "tools": _text_list(value["tools"], "tools"),
        "commands": [
            _normalize_command(command, index) for index, command in enumerate(commands_value)
        ],
        "repository_state": _normalize_repository_state(value["repository_state"]),
        "acceptance_updates": _normalize_status_updates(
            value["acceptance_updates"], checks=False
        ),
        "check_updates": _normalize_status_updates(value["check_updates"], checks=True),
        "progress_claim": _normalize_progress(value["progress_claim"]),
        "blocker": _normalize_blocker(value["blocker"]),
        "residual_risks": _text_list(value["residual_risks"], "residual_risks"),
        "next_action": _text(value["next_action"], "next_action"),
    }
    evidence_ids: set[str] = set()
    for command in normalized["commands"]:
        identifier = str(command["id"])
        if identifier in evidence_ids:
            raise ValueError(f"duplicate evidence id: {identifier}")
        evidence_ids.add(identifier)
    for collection_name in ("acceptance_updates", "check_updates"):
        for update in normalized[collection_name]:
            for evidence_item in update["evidence"]:
                identifier = str(evidence_item["id"])
                if identifier in evidence_ids:
                    raise ValueError(f"duplicate evidence id: {identifier}")
                evidence_ids.add(identifier)
    return normalized


def _payload_hash(value: Mapping[str, object]) -> str:
    canonical = json.dumps(value, allow_nan=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _evidence_index(iteration: Mapping[str, object]) -> dict[str, dict[str, object]]:
    index: dict[str, dict[str, object]] = {}
    for command in iteration["commands"]:
        assert isinstance(command, dict)
        index[str(command["id"])] = {
            "kind": "command",
            "argv": command["argv"],
            "exit_code": command["exit_code"],
            "result": command["result"],
            "summary": command["summary"],
        }
    for collection_name in ("acceptance_updates", "check_updates"):
        for update in iteration[collection_name]:
            for evidence in update["evidence"]:
                index[str(evidence["id"])] = {
                    key: evidence[key]
                    for key in (
                        "kind",
                        "summary",
                        "reference",
                        "repository_fingerprint",
                        "external_fingerprint",
                        "decision_id",
                    )
                }
    return index


def _blocker_signature(
    state: Mapping[str, object], iteration: Mapping[str, object]
) -> str:
    blocker = iteration["blocker"]
    assert isinstance(blocker, Mapping)
    evidence = _evidence_index(iteration)
    selected: list[dict[str, object]] = []
    for evidence_id in blocker["evidence_ids"]:
        if evidence_id not in evidence:
            raise ValueError(f"blocker references unknown evidence: {evidence_id}")
        selected.append(evidence[evidence_id])
    acceptance_states = sorted(
        (str(item["id"]), str(item["status"])) for item in state["acceptance"]
    )
    semantic = {
        "kind": blocker["kind"],
        "key": blocker["key"],
        "summary": blocker["summary"],
        "evidence": selected,
        "next_action": blocker["next_action"],
        "repository_state": iteration["repository_state"],
        "acceptance_states": acceptance_states,
    }
    return _payload_hash(semantic)


def _evidence_is_current(evidence: Mapping[str, object], fingerprint: str) -> bool:
    return (
        evidence["kind"] != "bounded_unavailable"
        and evidence["repository_fingerprint"] == fingerprint
    )


def _invalidate_stale_evidence(
    state: dict[str, object],
    repository: Mapping[str, object],
    *,
    repository_changed: bool = False,
    external_fingerprint: str | None = None,
) -> None:
    fingerprint = str(repository["worktree_fingerprint"])
    for collection_name in ("acceptance", "checks"):
        collection = state[collection_name]
        assert isinstance(collection, list)
        for item in collection:
            assert isinstance(item, dict)
            evidence_values = item["evidence"]
            assert isinstance(evidence_values, list)
            for evidence in evidence_values:
                assert isinstance(evidence, dict)
                repository_stale = repository_changed or not _evidence_is_current(
                    evidence, fingerprint
                )
                external_stale = (
                    external_fingerprint is not None
                    and evidence["external_fingerprint"] is not None
                    and evidence["external_fingerprint"] != external_fingerprint
                )
                evidence["stale"] = repository_stale or external_stale
            if item["status"] == "passed" and not any(
                not evidence["stale"] and evidence["kind"] != "bounded_unavailable"
                for evidence in evidence_values
            ):
                item["status"] = "unknown"


def _apply_status_updates(
    state: dict[str, object],
    updates: list[dict[str, object]],
    *,
    checks: bool,
) -> bool:
    collection_name = "checks" if checks else "acceptance"
    collection = state[collection_name]
    assert isinstance(collection, list)
    by_id = {str(item["id"]): item for item in collection}
    fingerprint = str(state["repository_state"]["worktree_fingerprint"])
    material_progress = False
    for update in updates:
        identifier = str(update["id"])
        if checks and identifier not in by_id:
            item = {
                "id": identifier,
                "description": update["description"],
                "status": "unknown",
                "evidence": [],
            }
            collection.append(item)
            by_id[identifier] = item
        if identifier not in by_id:
            raise ValueError(f"unknown acceptance id: {identifier}")
        item = by_id[identifier]
        previous = item["status"]
        evidence_values = copy.deepcopy(update["evidence"])
        for evidence in evidence_values:
            evidence["stale"] = not _evidence_is_current(evidence, fingerprint)
        status = update["status"]
        if status == "passed" and not any(
            not evidence["stale"] and evidence["kind"] != "bounded_unavailable"
            for evidence in evidence_values
        ):
            raise ValueError(f"{collection_name} {identifier} lacks current pass evidence")
        item["status"] = status
        item["evidence"] = evidence_values
        if checks:
            item["description"] = update["description"]
        if previous != "passed" and status == "passed":
            material_progress = True
    return material_progress


def _normalize_cleanup_confirmation(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("cleanup_confirmation must be an object")
    _expect_exact_keys(value, CLEANUP_CONFIRMATION_FIELDS, "cleanup_confirmation")
    if type(value["deleted"]) is not bool:
        raise ValueError("cleanup_confirmation.deleted must be a boolean")
    return {
        "schedule_id": _text(
            value["schedule_id"], "cleanup_confirmation.schedule_id", limit=256
        ),
        "deleted": value["deleted"],
        "observed_at": _normalize_timestamp(
            value["observed_at"], "cleanup_confirmation.observed_at"
        ),
    }


def _normalize_resume_signal(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("resume_signal must be an object")
    _expect_exact_keys(value, RESUME_SIGNAL_FIELDS, "resume_signal")
    kind = value["kind"]
    if kind not in {"user", "host"}:
        raise ValueError("resume_signal.kind must be user or host")
    return {
        "kind": kind,
        "id": _text(value["id"], "resume_signal.id", limit=256),
        "reason": _text(value["reason"], "resume_signal.reason"),
        "observed_at": _normalize_timestamp(
            value["observed_at"], "resume_signal.observed_at"
        ),
    }


def _normalize_outcome(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("outcome must be an object")
    _expect_exact_keys(value, OUTCOME_FIELDS, "outcome")
    kind = value["kind"]
    if kind not in {"complete", "blocked", "paused"}:
        raise ValueError("outcome.kind must be complete, blocked, or paused")
    return {
        "kind": kind,
        "reason": _text(value["reason"], "outcome.reason"),
    }


def _normalize_finish_evidence(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("finish evidence must be an object")
    _expect_exact_keys(value, FINISH_EVIDENCE_FIELDS, "finish evidence")
    commands = value["commands"]
    if not isinstance(commands, list) or len(commands) > 100:
        raise ValueError("finish evidence commands must be a bounded list")
    return {
        "observed_at": _normalize_timestamp(
            value["observed_at"], "finish evidence observed_at"
        ),
        "action": _text(value["action"], "finish evidence action"),
        "tools": _text_list(value["tools"], "finish evidence tools"),
        "commands": [
            _normalize_command(command, index) for index, command in enumerate(commands)
        ],
        "residual_risks": _text_list(
            value["residual_risks"], "finish evidence residual_risks"
        ),
        "next_action": _text(value["next_action"], "finish evidence next_action"),
    }


def _confirm_schedule_cleanup(
    schedule_id: object,
    confirmation: dict[str, object] | None,
) -> None:
    if schedule_id is None:
        if confirmation is not None:
            raise ValueError("cleanup_confirmation requires a recorded schedule")
        return
    if confirmation is None:
        raise ValueError("leaving a scheduled wait requires cleanup_confirmation")
    if confirmation["schedule_id"] != schedule_id:
        raise ValueError("cleanup_confirmation does not match the recorded schedule")
    if confirmation["deleted"] is not True:
        raise ValueError("cleanup_confirmation must confirm deletion")


def _blocked_external_bindings(
    state: Mapping[str, object],
) -> dict[str, set[str]]:
    last = state["last_iteration"]
    if not isinstance(last, Mapping) or not isinstance(last["blocker"], Mapping):
        return {}
    blocker_ids = {str(identifier) for identifier in last["blocker"]["evidence_ids"]}
    acceptance_descriptions = {
        str(item["id"]): str(item["description"]) for item in state["acceptance"]
    }
    bindings: dict[str, set[str]] = {}
    for collection_name in ("acceptance_updates", "check_updates"):
        for update in last[collection_name]:
            condition = (
                str(update["description"])
                if collection_name == "check_updates"
                else acceptance_descriptions.get(str(update["id"]), "")
            )
            for evidence in update["evidence"]:
                fingerprint = evidence["external_fingerprint"]
                if (
                    str(evidence["id"]) in blocker_ids
                    and evidence["kind"] == "external"
                    and fingerprint is not None
                    and condition
                ):
                    bindings.setdefault(condition, set()).add(str(fingerprint))
    return bindings


def _known_progress_bindings(state: Mapping[str, object]) -> tuple[set[str], set[str]]:
    external_fingerprints: set[str] = set()
    decision_ids: set[str] = set()
    for collection_name in ("acceptance", "checks"):
        for item in state[collection_name]:
            for evidence in item["evidence"]:
                external = evidence["external_fingerprint"]
                decision = evidence["decision_id"]
                if external is not None:
                    external_fingerprints.add(str(external))
                if decision is not None:
                    decision_ids.add(str(decision))
    return external_fingerprints, decision_ids


def _required_acceptance_complete(state: Mapping[str, object]) -> bool:
    return all(
        not item["required"]
        or (
            item["status"] == "passed"
            and any(
                not evidence.get("stale", True)
                and evidence["kind"] != "bounded_unavailable"
                for evidence in item["evidence"]
            )
        )
        for item in state["acceptance"]
    )


def _validate_state_evidence(value: object, label: str) -> None:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    _expect_exact_keys(value, EVIDENCE_STATE_FIELDS, label)
    _normalize_evidence(
        {field: value[field] for field in EVIDENCE_FIELDS},
        label,
    )
    if type(value["stale"]) is not bool:
        raise ValueError(f"{label}.stale must be a boolean")


def _ensure_safe_parent(repository: Path, path: Path) -> None:
    try:
        relative_parent = path.parent.relative_to(repository)
    except ValueError as error:
        raise ValueError("ledger path escapes the repository") from error
    current = repository
    for part in relative_parent.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("ledger path traverses a symlink")
    if path.is_symlink():
        raise ValueError("ledger path is a symlink")


def _fsync_directory(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _staged_text(repository: Path, path: Path, content: str) -> Path:
    _ensure_safe_parent(repository, path)
    path.parent.mkdir(parents=True, exist_ok=True)
    _ensure_safe_parent(repository, path)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise
    return temporary_path


def _atomic_write_text(repository: Path, path: Path, content: str) -> None:
    temporary_path = _staged_text(repository, path, content)
    try:
        os.replace(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _atomic_create_text(repository: Path, path: Path, content: str) -> None:
    temporary_path = _staged_text(repository, path, content)
    try:
        os.link(temporary_path, path)
        _fsync_directory(path.parent)
    finally:
        temporary_path.unlink(missing_ok=True)


def _json_text(payload: Mapping[str, object]) -> str:
    return json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"


def _strict_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_json_constant(value: str) -> object:
    raise ValueError(f"non-standard JSON constant: {value}")


def _strict_json_loads(content: str) -> object:
    return json.loads(
        content,
        object_pairs_hook=_strict_json_object,
        parse_constant=_reject_json_constant,
    )


def _atomic_write_json(repository: Path, path: Path, payload: Mapping[str, object]) -> None:
    _atomic_write_text(repository, path, _json_text(payload))


def _atomic_create_json(repository: Path, path: Path, payload: Mapping[str, object]) -> None:
    _atomic_create_text(repository, path, _json_text(payload))


def _render_audit_header(state: Mapping[str, object]) -> str:
    return (
        f"# Loop Run {state['run_id']}\n\n"
        f"Status: {state['status']}\n"
        "Owner: Codex\n"
        f"Updated: {state['updated_at']}\n\n"
        f"Objective: {state['objective']}\n\n"
        f"No-progress threshold: {state['threshold']}\n"
    )


def _audit_safe(value: object) -> str:
    return str(value).replace("<!--", "&lt;!--").replace("\r", " ").replace("\n", " ")


def _reject_raw_audit_fields(value: object, label: str = "audit details") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).lower() in RAW_AUDIT_FIELDS:
                raise ValueError(f"{label} contains forbidden raw log field: {key}")
            _reject_raw_audit_fields(item, f"{label}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_raw_audit_fields(item, f"{label}[{index}]")


def _normalize_audit_details(value: object) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("audit details must be an object")
    _expect_exact_keys(value, AUDIT_DETAIL_FIELDS, "audit details")
    commands = value["commands"]
    if not isinstance(commands, list) or len(commands) > 100:
        raise ValueError("audit details commands must be a bounded list")
    normalized_commands: list[dict[str, object]] = []
    for index, command in enumerate(commands):
        if not isinstance(command, Mapping):
            raise ValueError(f"audit details commands[{index}] must be an object")
        _expect_exact_keys(
            command,
            AUDIT_COMMAND_FIELDS,
            f"audit details commands[{index}]",
        )
        normalized_commands.append(
            {
                "argv": _text_list(
                    command["argv"], f"audit details commands[{index}].argv"
                ),
                "result": _text(
                    command["result"], f"audit details commands[{index}].result"
                ),
                "summary": _text(
                    command["summary"], f"audit details commands[{index}].summary"
                ),
            }
        )
    if type(value["material_progress"]) is not bool:
        raise ValueError("audit details material_progress must be a boolean")
    for field in ("blocker", "evidence"):
        try:
            encoded = json.dumps(value[field], allow_nan=False, sort_keys=True)
        except (TypeError, ValueError) as error:
            raise ValueError(f"audit details {field} must be JSON serializable") from error
        if len(encoded.encode("utf-8")) > MAX_AUDIT_EVENT_BYTES:
            raise ValueError(f"audit details {field} exceeds the size limit")
    normalized = {
        "action": _text(value["action"], "audit details action"),
        "tools": _text_list(value["tools"], "audit details tools"),
        "commands": normalized_commands,
        "result": _text(value["result"], "audit details result", limit=256),
        "material_progress": value["material_progress"],
        "blocker": copy.deepcopy(value["blocker"]),
        "residual_risks": _text_list(
            value["residual_risks"], "audit details residual_risks"
        ),
        "next_action": _text(value["next_action"], "audit details next_action"),
        "evidence": copy.deepcopy(value["evidence"]),
    }
    _reject_raw_audit_fields(normalized)
    return normalized


def _audit_event(
    sequence: int,
    kind: str,
    observed_at: str,
    summary: str,
    details: Mapping[str, object],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "sequence": sequence,
        "kind": _text(kind, "audit kind", limit=64),
        "observed_at": _normalize_timestamp(observed_at, "audit observed_at"),
        "summary": _text(summary, "audit summary"),
        "details": _normalize_audit_details(details),
    }
    canonical = json.dumps(payload, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(canonical.encode("utf-8")) > MAX_AUDIT_EVENT_BYTES:
        raise ValueError("audit event exceeds the size limit")
    payload["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return payload


def _render_audit_block(event: Mapping[str, object]) -> str:
    sequence = event["sequence"]
    event_hash = event["hash"]
    details = json.dumps(event["details"], ensure_ascii=False, sort_keys=True)
    details = details.replace("<!--", "&lt;!--")
    return (
        f"\n<!-- omc-audit-begin:{sequence}:{event_hash} -->\n"
        f"## Event {sequence}: {_audit_safe(event['kind'])}\n\n"
        f"- Observed: {_audit_safe(event['observed_at'])}\n"
        f"- Summary: {_audit_safe(event['summary'])}\n"
        f"- Details: `{details.replace('`', '&#96;')}`\n"
        f"<!-- omc-audit-end:{sequence}:{event_hash} -->\n"
    )


def _validate_loaded_state(state: Mapping[str, object], run_id: str) -> None:
    _expect_exact_keys(state, STATE_FIELDS, "loop state")
    if type(state["schema_version"]) is not int or state["schema_version"] != 1:
        raise ValueError("loop state schema_version must be 1")
    if state["run_id"] != run_id:
        raise ValueError("loop state run_id does not match its path")
    if state["status"] not in STATUSES:
        raise ValueError("loop state has an invalid status")
    if type(state["revision"]) is not int or state["revision"] < 1:
        raise ValueError("loop state revision must be a positive integer")
    if type(state["threshold"]) is not int or state["threshold"] < 3:
        raise ValueError("loop state threshold must be at least 3")
    if type(state["no_progress_count"]) is not int or state["no_progress_count"] < 0:
        raise ValueError("loop state no_progress_count must be non-negative")
    if type(state["iteration_count"]) is not int or state["iteration_count"] < 0:
        raise ValueError("loop state iteration_count must be non-negative")
    iteration_ids = state["iteration_ids"]
    if not isinstance(iteration_ids, list):
        raise ValueError("loop state iteration_ids must be a list")
    normalized_iteration_ids = _text_list(
        iteration_ids,
        "loop state iteration_ids",
        limit=max(int(state["iteration_count"]), 1),
    )
    if len(normalized_iteration_ids) != int(state["iteration_count"]):
        raise ValueError("loop state iteration_ids must match iteration_count")
    if len(set(normalized_iteration_ids)) != len(normalized_iteration_ids):
        raise ValueError("loop state iteration_ids must be unique")
    _text(state["objective"], "loop state objective")
    _normalize_assumptions(state["assumptions"])
    _text(state["threshold_reason"], "loop state threshold_reason")
    if state["entrypoint"] not in ENTRYPOINTS:
        raise ValueError("loop state has an invalid entrypoint")
    for field in ("goal_id", "scheduled_task_id", "blocker_key", "blocker_signature"):
        if state[field] is not None:
            _text(state[field], f"loop state {field}", limit=256)
    _normalize_repository_state(state["baseline"])
    _normalize_repository_state(state["repository_state"])
    current_fingerprint = str(state["repository_state"]["worktree_fingerprint"])
    items = state["acceptance"]
    if not isinstance(items, list) or not items or len(items) > 1_000:
        raise ValueError("loop state acceptance must be a non-empty list")
    acceptance_ids: set[str] = set()
    has_required = False
    for index, item in enumerate(items):
        if not isinstance(item, Mapping):
            raise ValueError(f"loop state acceptance[{index}] must be an object")
        _expect_exact_keys(item, ACCEPTANCE_STATE_FIELDS, f"loop state acceptance[{index}]")
        identifier = _text(item["id"], f"loop state acceptance[{index}].id", limit=64)
        if identifier in acceptance_ids:
            raise ValueError(f"duplicate acceptance id: {identifier}")
        acceptance_ids.add(identifier)
        _text(item["description"], f"loop state acceptance[{index}].description")
        if type(item["required"]) is not bool:
            raise ValueError(f"loop state acceptance[{index}].required must be a boolean")
        has_required = has_required or bool(item["required"])
        if item["status"] not in ACCEPTANCE_STATUSES:
            raise ValueError(f"loop state acceptance[{index}] has an invalid status")
        if not isinstance(item["evidence"], list) or len(item["evidence"]) > 1_000:
            raise ValueError(
                f"loop state acceptance[{index}].evidence must be a bounded list"
            )
        for evidence_index, evidence in enumerate(item["evidence"]):
            _validate_state_evidence(
                evidence,
                f"loop state acceptance[{index}].evidence[{evidence_index}]",
            )
            if evidence["stale"] is False and not _evidence_is_current(
                evidence, current_fingerprint
            ):
                raise ValueError(
                    f"loop state acceptance[{index}] evidence freshness is inconsistent"
                )
        if item["status"] == "passed" and not any(
            evidence["stale"] is False
            and evidence["kind"] != "bounded_unavailable"
            for evidence in item["evidence"]
        ):
            raise ValueError(
                f"loop state acceptance[{index}] passed status lacks current evidence"
            )
    if not has_required:
        raise ValueError("loop state acceptance must contain at least one required item")
    checks = state["checks"]
    if not isinstance(checks, list) or len(checks) > 1_000:
        raise ValueError("loop state checks must be a bounded list")
    check_ids: set[str] = set()
    for index, item in enumerate(checks):
        if not isinstance(item, Mapping):
            raise ValueError(f"loop state checks[{index}] must be an object")
        _expect_exact_keys(item, CHECK_STATE_FIELDS, f"loop state checks[{index}]")
        identifier = _text(item["id"], f"loop state checks[{index}].id", limit=64)
        if identifier in check_ids:
            raise ValueError(f"duplicate check id: {identifier}")
        check_ids.add(identifier)
        _text(item["description"], f"loop state checks[{index}].description")
        if item["status"] not in ACCEPTANCE_STATUSES:
            raise ValueError(f"loop state checks[{index}] has an invalid status")
        if not isinstance(item["evidence"], list) or len(item["evidence"]) > 1_000:
            raise ValueError(
                f"loop state checks[{index}].evidence must be a bounded list"
            )
        for evidence_index, evidence in enumerate(item["evidence"]):
            _validate_state_evidence(
                evidence,
                f"loop state checks[{index}].evidence[{evidence_index}]",
            )
            if evidence["stale"] is False and not _evidence_is_current(
                evidence, current_fingerprint
            ):
                raise ValueError(
                    f"loop state checks[{index}] evidence freshness is inconsistent"
                )
        if item["status"] == "passed" and not any(
            evidence["stale"] is False
            and evidence["kind"] != "bounded_unavailable"
            for evidence in item["evidence"]
        ):
            raise ValueError(f"loop state checks[{index}] passed status lacks current evidence")
    if not isinstance(state["capability_snapshot"], Mapping):
        raise ValueError("loop state capability_snapshot must be an object")
    if state["external_wait"] is not None:
        _normalize_external_wait(state["external_wait"])
    if state["status"] == "waiting" and state["external_wait"] is None:
        raise ValueError("a waiting loop state requires external_wait")
    if state["status"] != "waiting" and state["external_wait"] is not None:
        raise ValueError("only a waiting loop state may retain external_wait")
    if state["external_wait"] is not None:
        strategy = state["external_wait"]["strategy"]
        if strategy == "scheduled" and state["scheduled_task_id"] is None:
            raise ValueError("a scheduled wait requires scheduled_task_id")
        if strategy != "scheduled" and state["scheduled_task_id"] is not None:
            raise ValueError("a non-scheduled wait forbids scheduled_task_id")
    elif state["scheduled_task_id"] is not None:
        raise ValueError("scheduled_task_id requires an external wait")
    last_iteration = state["last_iteration"]
    if last_iteration is not None:
        if not isinstance(last_iteration, Mapping):
            raise ValueError("loop state last_iteration must be an object or null")
        _expect_exact_keys(last_iteration, LAST_ITERATION_FIELDS, "loop state last_iteration")
        normalized_last_iteration = _normalize_iteration(
            {field: last_iteration[field] for field in ITERATION_FIELDS}
        )
        payload_hash = _text(
            last_iteration["payload_hash"], "last_iteration.payload_hash", limit=64
        )
        if not re.fullmatch(r"[0-9a-f]{64}", payload_hash):
            raise ValueError("last_iteration.payload_hash must be lowercase SHA-256")
        if payload_hash != _payload_hash(normalized_last_iteration):
            raise ValueError("last_iteration.payload_hash does not match its payload")
        if last_iteration["iteration_number"] != state["iteration_count"]:
            raise ValueError("last_iteration must match iteration_count")
        if type(last_iteration["material_progress"]) is not bool:
            raise ValueError("last_iteration.material_progress must be a boolean")
        if last_iteration["decision_kind"] not in {
            "continue",
            "wait",
            "complete",
            "blocked",
            "paused",
        }:
            raise ValueError("last_iteration.decision_kind is invalid")
        _text(last_iteration["decision_reason"], "last_iteration.decision_reason")
        if not iteration_ids or last_iteration["iteration_id"] != iteration_ids[-1]:
            raise ValueError("last_iteration must match the final iteration_id")
    elif iteration_ids:
        raise ValueError("loop state with iterations requires last_iteration")
    outcome = state["outcome"]
    if outcome is not None:
        if not isinstance(outcome, Mapping):
            raise ValueError("loop state outcome must be an object or null")
        _expect_exact_keys(outcome, OUTCOME_FIELDS, "loop state outcome")
        outcome_kind = _text(outcome["kind"], "loop state outcome.kind", limit=64)
        if outcome_kind not in {"complete", "threshold", "policy", "blocked", "paused"}:
            raise ValueError("loop state outcome.kind is invalid")
        _text(outcome["reason"], "loop state outcome.reason")
    if state["closed_at"] is not None:
        _text(state["closed_at"], "loop state closed_at", limit=64)
    status = state["status"]
    if status in {"preparing", "active", "waiting"}:
        if outcome is not None or state["closed_at"] is not None:
            raise ValueError(f"{status} loop state cannot have an outcome or closed_at")
    elif status == "complete":
        if outcome is None or outcome["kind"] != "complete":
            raise ValueError("complete loop state requires a complete outcome")
        if state["closed_at"] is None or not _required_acceptance_complete(state):
            raise ValueError("complete loop state requires current acceptance evidence")
    elif status == "blocked":
        if outcome is None or outcome["kind"] not in {"threshold", "policy", "blocked"}:
            raise ValueError("blocked loop state requires a blocked outcome")
    elif status == "paused":
        if outcome is None or outcome["kind"] != "paused" or state["closed_at"] is None:
            raise ValueError("paused loop state requires a paused outcome and closed_at")
    audit = state["audit"]
    if not isinstance(audit, Mapping):
        raise ValueError("loop state audit must be an object")
    _expect_exact_keys(audit, AUDIT_FIELDS, "loop state audit")
    if type(audit["sequence"]) is not int or audit["sequence"] < 1:
        raise ValueError("loop state audit sequence must be a positive integer")
    pending = audit["pending"]
    if pending is not None:
        if not isinstance(pending, Mapping):
            raise ValueError("loop state pending audit must be an object")
        _expect_exact_keys(pending, AUDIT_EVENT_FIELDS, "loop state pending audit")
        if pending["sequence"] != audit["sequence"]:
            raise ValueError("pending audit sequence does not match audit sequence")
        if not isinstance(pending["details"], Mapping):
            raise ValueError("pending audit details must be an object")
        reconstructed = _audit_event(
            int(pending["sequence"]),
            str(pending["kind"]),
            str(pending["observed_at"]),
            str(pending["summary"]),
            pending["details"],
        )
        if dict(pending) != reconstructed:
            raise ValueError("pending audit hash is invalid")
    for field in ("created_at", "updated_at"):
        _normalize_timestamp(state[field], f"loop state {field}")


class LoopLedger:
    def __init__(
        self,
        repository: Path,
        *,
        clock: Callable[[], datetime] = utc_now,
        run_id_factory: Callable[[datetime], str] = new_run_id,
    ) -> None:
        self.repository = repository.resolve()
        self.clock = clock
        self.run_id_factory = run_id_factory

    @property
    def state_directory(self) -> Path:
        return self.repository / ".ohmycodex" / "runtime" / "loops"

    @property
    def audit_directory(self) -> Path:
        return self.repository / ".ohmycodex" / "plans" / "loop-runs"

    def _state_path(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError("invalid run_id")
        return self.state_directory / f"{run_id}.json"

    def _audit_path(self, run_id: str) -> Path:
        if not RUN_ID_RE.fullmatch(run_id):
            raise ValueError("invalid run_id")
        return self.audit_directory / f"{run_id}.md"

    @contextmanager
    def _run_lock(self, run_id: str):
        self._state_path(run_id)
        lock_path = self.state_directory / f".{run_id}.lock"
        _ensure_safe_parent(self.repository, lock_path)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        _ensure_safe_parent(self.repository, lock_path)
        if fcntl is not None:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
                os.close(descriptor)
            return

        key = str(lock_path)
        with _PROCESS_LOCKS_GUARD:
            lock = _PROCESS_LOCKS.setdefault(key, threading.RLock())
        with lock:
            yield

    def _repair_pending_audit(self, state: dict[str, object]) -> dict[str, object]:
        audit = state["audit"]
        assert isinstance(audit, dict)
        pending = audit["pending"]
        if pending is None:
            return state
        assert isinstance(pending, Mapping)
        path = self._audit_path(str(state["run_id"]))
        _ensure_safe_parent(self.repository, path)
        if path.exists():
            existing = path.read_text(encoding="utf-8")
        else:
            existing = _render_audit_header(state)
        end_marker = (
            f"<!-- omc-audit-end:{pending['sequence']}:{pending['hash']} -->"
        )
        begin_marker = (
            f"<!-- omc-audit-begin:{pending['sequence']}:{pending['hash']} -->"
        )
        sequence = int(pending["sequence"])
        event_hash = str(pending["hash"])
        matching_begin: list[re.Match[str]] = []
        matching_end: list[re.Match[str]] = []
        for marker in AUDIT_MARKER_RE.finditer(existing):
            marker_sequence = int(marker.group(2))
            marker_hash = marker.group(3)
            if marker_sequence > sequence:
                raise ValueError("audit marker sequence exceeds pending state")
            if marker_sequence == sequence:
                if marker_hash != event_hash:
                    raise ValueError("audit marker conflicts with pending event")
                if marker.group(1) == "begin":
                    matching_begin.append(marker)
                else:
                    matching_end.append(marker)
        if len(matching_begin) > 1 or len(matching_end) > 1:
            raise ValueError("audit marker is duplicated")
        if matching_end and not matching_begin:
            raise ValueError("audit marker end has no matching begin")
        if matching_begin and matching_end:
            begin = matching_begin[0]
            end = matching_end[0]
            if begin.start() >= end.start():
                raise ValueError("audit marker order is invalid")
            actual_block = existing[begin.start() : end.end()]
            expected_block = _render_audit_block(pending).strip()
            if actual_block != expected_block:
                raise ValueError("audit marker block does not match pending event")
        else:
            if matching_begin:
                existing = existing[: matching_begin[0].start()].rstrip() + "\n"
            _atomic_write_text(
                self.repository,
                path,
                existing.rstrip() + "\n" + _render_audit_block(pending),
            )
        audit["pending"] = None
        _atomic_write_json(
            self.repository,
            self._state_path(str(state["run_id"])),
            state,
        )
        return state

    def _commit_semantic_change(
        self,
        state: dict[str, object],
        *,
        kind: str,
        summary: str,
        details: Mapping[str, object],
    ) -> dict[str, object]:
        audit = state["audit"]
        assert isinstance(audit, dict)
        sequence = int(audit["sequence"]) + 1
        audit["sequence"] = sequence
        audit["pending"] = _audit_event(
            sequence,
            kind,
            str(state["updated_at"]),
            summary,
            details,
        )
        _atomic_write_json(
            self.repository,
            self._state_path(str(state["run_id"])),
            state,
        )
        self._repair_pending_audit(state)
        return copy.deepcopy(state)

    def load_run(self, run_id: str) -> dict[str, object]:
        path = self._state_path(run_id)
        _ensure_safe_parent(self.repository, path)
        try:
            if path.stat().st_size > MAX_STATE_BYTES:
                raise ValueError("loop state exceeds the size limit")
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise
        except (OSError, UnicodeError) as error:
            raise ValueError("loop state is not valid JSON") from error
        try:
            state = _strict_json_loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("loop state is not valid JSON") from error
        if not isinstance(state, Mapping):
            raise ValueError("loop state must be a JSON object")
        _validate_loaded_state(state, run_id)
        return copy.deepcopy(dict(state))

    def create_run(
        self,
        *,
        objective: str,
        acceptance: Sequence[Mapping[str, object]],
        threshold: int,
        baseline: Mapping[str, object],
        capabilities: Mapping[str, object],
        entrypoint: str,
        assumptions: Sequence[str] = (),
        threshold_reason: str | None = None,
    ) -> dict[str, object]:
        if type(threshold) is not int or threshold < 3:
            raise ValueError("threshold must be at least 3")
        objective = _text(objective, "objective")
        if entrypoint not in ENTRYPOINTS:
            raise ValueError("entrypoint must be an OhMyCodex continuation skill")
        normalized_acceptance = _normalize_acceptance(acceptance)
        normalized_assumptions = _normalize_assumptions(assumptions)
        if threshold_reason is None:
            if entrypoint == "omc-letgo":
                raise ValueError("omc-letgo must provide a threshold_reason")
            threshold_reason = "User selected the no-progress threshold"
        threshold_reason = _text(threshold_reason, "threshold_reason")
        normalized_baseline = _normalize_repository_state(baseline)
        if not isinstance(capabilities, Mapping):
            raise ValueError("capabilities must be an object")
        try:
            capability_json = json.dumps(
                capabilities,
                allow_nan=False,
                sort_keys=True,
            )
        except (TypeError, ValueError) as error:
            raise ValueError("capabilities must be JSON serializable") from error
        if len(capability_json.encode("utf-8")) > MAX_CAPABILITY_BYTES:
            raise ValueError("capabilities exceeds the size limit")
        normalized_capabilities = json.loads(capability_json)

        now = self.clock()
        updated_at = _timestamp(now)
        run_id = self.run_id_factory(now)
        state_path = self._state_path(run_id)
        initial_audit = _audit_event(
            1,
            "created",
            updated_at,
            "Created preparing continuation run",
            {
                "action": "Create the continuation ledger",
                "tools": ["loop_ledger"],
                "commands": [],
                "result": "preparing",
                "material_progress": False,
                "blocker": None,
                "residual_risks": [],
                "next_action": "Create or reconcile the native Goal",
                "evidence": {
                    "entrypoint": entrypoint,
                    "threshold": threshold,
                    "threshold_reason": threshold_reason,
                },
            },
        )
        state: dict[str, object] = {
            "schema_version": 1,
            "run_id": run_id,
            "revision": 1,
            "status": "preparing",
            "entrypoint": entrypoint,
            "objective": objective,
            "assumptions": normalized_assumptions,
            "goal_id": None,
            "threshold": threshold,
            "threshold_reason": threshold_reason,
            "iteration_count": 0,
            "iteration_ids": [],
            "no_progress_count": 0,
            "blocker_key": None,
            "blocker_signature": None,
            "baseline": normalized_baseline,
            "repository_state": copy.deepcopy(normalized_baseline),
            "acceptance": normalized_acceptance,
            "checks": [],
            "capability_snapshot": normalized_capabilities,
            "scheduled_task_id": None,
            "external_wait": None,
            "last_iteration": None,
            "outcome": None,
            "closed_at": None,
            "audit": {"sequence": 1, "pending": initial_audit},
            "created_at": updated_at,
            "updated_at": updated_at,
        }
        _atomic_create_json(self.repository, state_path, state)
        self._repair_pending_audit(state)
        return copy.deepcopy(state)

    def activate_run(self, run_id: str, goal_id: str) -> dict[str, object]:
        goal_id = _text(goal_id, "goal_id", limit=256)
        with self._run_lock(run_id):
            state = self.load_run(run_id)
            self._repair_pending_audit(state)
            current_goal = state["goal_id"]
            if current_goal is not None:
                if current_goal == goal_id and state["status"] == "active":
                    return copy.deepcopy(state)
                raise ValueError("run is already bound to a different Goal")
            if state["status"] != "preparing":
                raise ValueError("only a preparing run can be activated")

            state["goal_id"] = goal_id
            state["status"] = "active"
            state["revision"] = int(state["revision"]) + 1
            state["updated_at"] = _timestamp(self.clock())
            return self._commit_semantic_change(
                state,
                kind="activated",
                summary="Bound the continuation run to a native Goal",
                details={
                    "action": "Bind the ledger to the native Goal",
                    "tools": ["goal_control", "loop_ledger"],
                    "commands": [],
                    "result": "active",
                    "material_progress": False,
                    "blocker": None,
                    "residual_risks": [],
                    "next_action": "Execute the first objective-aligned iteration",
                    "evidence": {"goal_id": goal_id},
                },
            )

    def record_iteration(
        self,
        run_id: str,
        evidence: Mapping[str, object],
    ) -> LoopDecision:
        if not isinstance(evidence, Mapping):
            raise ValueError("iteration must be an object")
        iteration = _normalize_iteration(evidence)
        iteration_hash = _payload_hash(iteration)

        with self._run_lock(run_id):
            state = self.load_run(run_id)
            self._repair_pending_audit(state)
            last = state["last_iteration"]
            if isinstance(last, Mapping) and last.get("iteration_id") == iteration["iteration_id"]:
                if last.get("payload_hash") != iteration_hash:
                    raise ValueError("iteration_id was already used with a different payload")
                return LoopDecision(
                    kind=str(last["decision_kind"]),
                    state=copy.deepcopy(state),
                    reason=str(last["decision_reason"]),
                    material_progress=bool(last["material_progress"]),
                )
            if state["status"] != "active":
                raise ValueError("iterations can be recorded only for an active run")
            if iteration["iteration_id"] in state["iteration_ids"]:
                raise ValueError("iteration_id was already used for an earlier turn")
            expected_number = int(state["iteration_count"]) + 1
            if iteration["iteration_number"] != expected_number:
                raise ValueError(f"iteration_number must be {expected_number}")

            previous_repository = state["repository_state"]
            repository_changed = previous_repository != iteration["repository_state"]
            state["repository_state"] = copy.deepcopy(iteration["repository_state"])
            if repository_changed:
                _invalidate_stale_evidence(
                    state,
                    iteration["repository_state"],
                    repository_changed=True,
                )

            known_external, known_decisions = _known_progress_bindings(state)
            material_progress = _apply_status_updates(
                state,
                iteration["acceptance_updates"],
                checks=False,
            )
            material_progress = (
                _apply_status_updates(state, iteration["check_updates"], checks=True)
                or material_progress
            )

            progress = iteration["progress_claim"]
            assert isinstance(progress, Mapping)
            evidence_index = _evidence_index(iteration)
            progress_ids = progress["evidence_ids"]
            if progress["kind"] == "none" and progress_ids:
                raise ValueError("a none progress claim cannot reference evidence")
            if progress["kind"] != "none":
                if not progress_ids:
                    raise ValueError("a material progress claim requires evidence")
                missing = [identifier for identifier in progress_ids if identifier not in evidence_index]
                if missing:
                    raise ValueError(f"progress references unknown evidence: {missing[0]}")
            if progress["kind"] == "repository_change" and repository_changed:
                material_progress = True
            elif progress["kind"] == "external_change" and any(
                evidence_index[identifier]["kind"] == "external"
                and evidence_index[identifier]["external_fingerprint"] is not None
                and str(evidence_index[identifier]["external_fingerprint"])
                not in known_external
                for identifier in progress_ids
            ):
                material_progress = True
            elif progress["kind"] == "user_decision" and any(
                evidence_index[identifier]["kind"] == "user_decision"
                and evidence_index[identifier]["decision_id"] is not None
                and str(evidence_index[identifier]["decision_id"])
                not in known_decisions
                for identifier in progress_ids
            ):
                material_progress = True

            blocker = iteration["blocker"]
            signature: str | None = None
            if blocker is not None:
                signature = _blocker_signature(state, iteration)

            if _required_acceptance_complete(state):
                kind: DecisionKind = "complete"
                reason = "all required acceptance items have current pass evidence"
                state["status"] = "complete"
                state["no_progress_count"] = 0
                state["blocker_key"] = None
                state["blocker_signature"] = None
                state["outcome"] = {"kind": "complete", "reason": reason}
                state["closed_at"] = _timestamp(self.clock())
            elif isinstance(blocker, Mapping) and blocker["kind"] == "policy":
                kind = "blocked"
                reason = "a current policy blocker prevents safe progress"
                state["status"] = "blocked"
                state["no_progress_count"] = 0
                state["blocker_key"] = blocker["key"]
                state["blocker_signature"] = signature
                state["outcome"] = {"kind": "policy", "reason": reason}
            elif blocker is not None and not material_progress:
                if signature == state["blocker_signature"]:
                    count = int(state["no_progress_count"]) + 1
                else:
                    count = 1
                state["no_progress_count"] = count
                state["blocker_key"] = blocker["key"]
                state["blocker_signature"] = signature
                if count >= int(state["threshold"]):
                    kind = "blocked"
                    reason = "the same blocker reached the no-progress threshold"
                    state["status"] = "blocked"
                    state["outcome"] = {"kind": "threshold", "reason": reason}
                else:
                    kind = "continue"
                    reason = "the blocker remains below the no-progress threshold"
            else:
                kind = "continue"
                reason = (
                    "material progress reset the blocker sequence"
                    if material_progress
                    else "no blocking condition was recorded"
                )
                state["no_progress_count"] = 0
                state["blocker_key"] = None
                state["blocker_signature"] = None

            state["iteration_count"] = iteration["iteration_number"]
            state["iteration_ids"].append(iteration["iteration_id"])
            state["revision"] = int(state["revision"]) + 1
            state["updated_at"] = _timestamp(self.clock())
            state["last_iteration"] = {
                **copy.deepcopy(iteration),
                "payload_hash": iteration_hash,
                "material_progress": material_progress,
                "decision_kind": kind,
                "decision_reason": reason,
            }
            committed = self._commit_semantic_change(
                state,
                kind="iteration",
                summary=f"Recorded iteration {iteration['iteration_number']}: {kind}",
                details={
                    "action": iteration["action"],
                    "tools": iteration["tools"],
                    "commands": [
                        {
                            "argv": command["argv"],
                            "result": command["result"],
                            "summary": command["summary"],
                        }
                        for command in iteration["commands"]
                    ],
                    "result": kind,
                    "material_progress": material_progress,
                    "blocker": blocker,
                    "residual_risks": iteration["residual_risks"],
                    "next_action": iteration["next_action"],
                    "evidence": {
                        "iteration_id": iteration["iteration_id"],
                        "observed_at": iteration["observed_at"],
                        "repository_state": iteration["repository_state"],
                        "acceptance_updates": [
                            {
                                "id": update["id"],
                                "status": update["status"],
                                "evidence_ids": [
                                    item["id"] for item in update["evidence"]
                                ],
                            }
                            for update in iteration["acceptance_updates"]
                        ],
                        "check_updates": [
                            {
                                "id": update["id"],
                                "status": update["status"],
                                "evidence_ids": [
                                    item["id"] for item in update["evidence"]
                                ],
                            }
                            for update in iteration["check_updates"]
                        ],
                    },
                },
            )
            return LoopDecision(
                kind=kind,
                state=committed,
                reason=reason,
                material_progress=material_progress,
            )

    def record_wait(
        self,
        run_id: str,
        external_state: Mapping[str, object],
        schedule_id: str | None,
    ) -> dict[str, object]:
        wait = _normalize_external_wait(external_state)
        strategy = wait["strategy"]
        if schedule_id is not None:
            schedule_id = _text(schedule_id, "schedule_id", limit=256)
        if strategy == "scheduled" and schedule_id is None:
            raise ValueError("scheduled wait requires a schedule_id")
        if strategy != "scheduled" and schedule_id is not None:
            raise ValueError("non-scheduled wait forbids a schedule_id")

        with self._run_lock(run_id):
            state = self.load_run(run_id)
            self._repair_pending_audit(state)
            if state["status"] == "waiting":
                if (
                    state["external_wait"] == wait
                    and state["scheduled_task_id"] == schedule_id
                ):
                    return copy.deepcopy(state)
                raise ValueError("run is already waiting for a different condition")
            if state["status"] != "active":
                raise ValueError("only an active run can enter waiting")

            state["status"] = "waiting"
            state["external_wait"] = wait
            state["scheduled_task_id"] = schedule_id
            state["revision"] = int(state["revision"]) + 1
            state["updated_at"] = _timestamp(self.clock())
            return self._commit_semantic_change(
                state,
                kind="waiting",
                summary="Recorded an external wait",
                details={
                    "action": "Wait for external state to change",
                    "tools": [strategy],
                    "commands": [],
                    "result": "wait",
                    "material_progress": False,
                    "blocker": {
                        "kind": "external",
                        "condition": wait["condition"],
                        "fingerprint": wait["fingerprint"],
                    },
                    "residual_risks": [],
                    "next_action": wait["next_action"],
                    "evidence": {
                        "external_state": wait,
                        "schedule_id": schedule_id,
                    },
                },
            )

    def reconcile_run(
        self,
        run_id: str,
        current_repository_state: Mapping[str, object],
        *,
        external_state: Mapping[str, object] | None = None,
        resume_signal: Mapping[str, object] | None = None,
        cleanup_confirmation: Mapping[str, object] | None = None,
    ) -> LoopDecision:
        repository = _normalize_repository_state(current_repository_state)
        current_external = (
            None if external_state is None else _normalize_external_wait(external_state)
        )
        resume = None if resume_signal is None else _normalize_resume_signal(resume_signal)
        cleanup = (
            None
            if cleanup_confirmation is None
            else _normalize_cleanup_confirmation(cleanup_confirmation)
        )

        with self._run_lock(run_id):
            state = self.load_run(run_id)
            self._repair_pending_audit(state)
            status = state["status"]
            if status == "preparing":
                raise ValueError("a preparing run must be activated before reconciliation")
            if status == "complete":
                if current_external is not None or resume is not None or cleanup is not None:
                    raise ValueError("a complete run is terminal")
                return LoopDecision(
                    kind="complete",
                    state=copy.deepcopy(state),
                    reason="the continuation run is already complete",
                    material_progress=False,
                )

            repository_changed = state["repository_state"] != repository
            if repository_changed:
                state["repository_state"] = copy.deepcopy(repository)
                _invalidate_stale_evidence(
                    state,
                    repository,
                    repository_changed=True,
                    external_fingerprint=(
                        None
                        if current_external is None
                        else str(current_external["fingerprint"])
                    ),
                )

            material_progress = False
            kind: DecisionKind
            reason: str
            next_action = "Continue the next objective-aligned iteration"

            if status == "waiting":
                recorded_wait = state["external_wait"]
                assert isinstance(recorded_wait, Mapping)
                if current_external is None:
                    raise ValueError("reconciling a waiting run requires external_state")
                if (
                    current_external["strategy"] != recorded_wait["strategy"]
                    or current_external["condition"] != recorded_wait["condition"]
                ):
                    raise ValueError("external_state does not match the recorded wait")
                external_changed = (
                    current_external["fingerprint"] != recorded_wait["fingerprint"]
                )
                if external_changed and _parsed_timestamp(
                    current_external["observed_at"], "external_state.observed_at"
                ) <= _parsed_timestamp(
                    recorded_wait["observed_at"], "recorded external wait observed_at"
                ):
                    raise ValueError(
                        "external_state must be newer than the recorded wait"
                    )
                if resume is not None and _parsed_timestamp(
                    resume["observed_at"], "resume_signal.observed_at"
                ) <= _parsed_timestamp(
                    recorded_wait["observed_at"], "recorded external wait observed_at"
                ):
                    raise ValueError("resume_signal must be newer than the recorded wait")
                if not external_changed and resume is None:
                    if cleanup is not None:
                        raise ValueError(
                            "cleanup_confirmation is invalid while the wait remains active"
                        )
                    if not repository_changed:
                        return LoopDecision(
                            kind="wait",
                            state=copy.deepcopy(state),
                            reason="the external fingerprint is unchanged",
                            material_progress=False,
                        )
                    kind = "wait"
                    reason = "repository evidence changed but the external wait remains"
                    next_action = str(recorded_wait["next_action"])
                else:
                    _confirm_schedule_cleanup(state["scheduled_task_id"], cleanup)
                    if cleanup is not None:
                        newest_trigger = (
                            current_external["observed_at"]
                            if external_changed
                            else resume["observed_at"]
                        )
                        if _parsed_timestamp(
                            cleanup["observed_at"],
                            "cleanup_confirmation.observed_at",
                        ) < _parsed_timestamp(newest_trigger, "wait resolution observed_at"):
                            raise ValueError(
                                "cleanup_confirmation predates the wait resolution"
                            )
                    if external_changed:
                        _invalidate_stale_evidence(
                            state,
                            repository,
                            external_fingerprint=str(current_external["fingerprint"]),
                        )
                    state["status"] = "active"
                    state["external_wait"] = None
                    state["scheduled_task_id"] = None
                    state["outcome"] = None
                    state["closed_at"] = None
                    state["no_progress_count"] = 0
                    state["blocker_key"] = None
                    state["blocker_signature"] = None
                    kind = "continue"
                    material_progress = external_changed
                    reason = (
                        "the external fingerprint changed materially"
                        if external_changed
                        else "an explicit resume signal ended the wait"
                    )
            elif status in {"blocked", "paused"}:
                if cleanup is not None:
                    raise ValueError("cleanup_confirmation requires a waiting run")
                external_changed = False
                if current_external is not None:
                    bindings = _blocked_external_bindings(state)
                    known = bindings.get(str(current_external["condition"]), set())
                    external_changed = bool(known) and str(
                        current_external["fingerprint"]
                    ) not in known
                    last = state["last_iteration"]
                    if external_changed and isinstance(last, Mapping) and _parsed_timestamp(
                        current_external["observed_at"], "external_state.observed_at"
                    ) <= _parsed_timestamp(last["observed_at"], "last iteration observed_at"):
                        raise ValueError(
                            "external_state must be newer than the blocking evidence"
                        )
                if resume is not None and _parsed_timestamp(
                    resume["observed_at"], "resume_signal.observed_at"
                ) <= _parsed_timestamp(state["updated_at"], "loop state updated_at"):
                    raise ValueError("resume_signal must be newer than the loop state")
                if resume is None and not external_changed:
                    kind = "blocked" if status == "blocked" else "paused"
                    reason = (
                        "the run remains blocked without a material external change or resume"
                        if status == "blocked"
                        else "the run remains paused without an explicit resume"
                    )
                    if not repository_changed:
                        return LoopDecision(
                            kind=kind,
                            state=copy.deepcopy(state),
                            reason=reason,
                            material_progress=False,
                        )
                else:
                    if status == "paused" and resume is None:
                        raise ValueError("a paused run requires an explicit resume_signal")
                    if external_changed:
                        assert current_external is not None
                        _invalidate_stale_evidence(
                            state,
                            repository,
                            external_fingerprint=str(current_external["fingerprint"]),
                        )
                    state["status"] = "active"
                    state["outcome"] = None
                    state["closed_at"] = None
                    state["no_progress_count"] = 0
                    state["blocker_key"] = None
                    state["blocker_signature"] = None
                    kind = "continue"
                    material_progress = external_changed
                    reason = (
                        "material external state changed after the blocker"
                        if external_changed
                        else "an explicit resume signal reactivated the run"
                    )
            else:
                if current_external is not None or resume is not None or cleanup is not None:
                    raise ValueError("active reconciliation accepts repository state only")
                kind = "continue"
                reason = (
                    "repository changes invalidated stale evidence"
                    if repository_changed
                    else "the active run is already reconciled"
                )
                if not repository_changed:
                    return LoopDecision(
                        kind=kind,
                        state=copy.deepcopy(state),
                        reason=reason,
                        material_progress=False,
                    )

            state["revision"] = int(state["revision"]) + 1
            state["updated_at"] = _timestamp(self.clock())
            committed = self._commit_semantic_change(
                state,
                kind="reconciled",
                summary=f"Reconciled continuation state: {kind}",
                details={
                    "action": "Reconcile recorded and current state",
                    "tools": ["loop_ledger"],
                    "commands": [],
                    "result": kind,
                    "material_progress": material_progress,
                    "blocker": None if kind == "continue" else state["blocker_key"],
                    "residual_risks": [],
                    "next_action": next_action,
                    "evidence": {
                        "repository_state": repository,
                        "external_state": current_external,
                        "resume_signal": resume,
                        "cleanup_confirmation": cleanup,
                    },
                },
            )
            return LoopDecision(
                kind=kind,
                state=committed,
                reason=reason,
                material_progress=material_progress,
            )

    def finish_run(
        self,
        run_id: str,
        outcome: Mapping[str, object],
        evidence: Mapping[str, object],
        *,
        cleanup_confirmation: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        normalized_outcome = _normalize_outcome(outcome)
        normalized_evidence = _normalize_finish_evidence(evidence)
        cleanup = (
            None
            if cleanup_confirmation is None
            else _normalize_cleanup_confirmation(cleanup_confirmation)
        )

        with self._run_lock(run_id):
            state = self.load_run(run_id)
            self._repair_pending_audit(state)
            desired_status = normalized_outcome["kind"]
            if state["status"] == "complete":
                if desired_status == "complete" and state["outcome"] == normalized_outcome:
                    return copy.deepcopy(state)
                raise ValueError("a complete run is terminal")
            if state["status"] == desired_status and state["outcome"] == normalized_outcome:
                return copy.deepcopy(state)
            if state["status"] in {"blocked", "paused"}:
                raise ValueError(
                    "invalid finish transition; reconcile the run before changing its outcome"
                )
            if desired_status == "complete" and not _required_acceptance_complete(state):
                raise ValueError(
                    "complete outcome requires current evidence for all required acceptance"
                )

            _confirm_schedule_cleanup(state["scheduled_task_id"], cleanup)
            recorded_wait = state["external_wait"]
            if isinstance(recorded_wait, Mapping) and cleanup is not None:
                if _parsed_timestamp(
                    cleanup["observed_at"], "cleanup_confirmation.observed_at"
                ) < _parsed_timestamp(
                    recorded_wait["observed_at"], "recorded external wait observed_at"
                ):
                    raise ValueError("cleanup_confirmation predates the recorded wait")
            state["status"] = desired_status
            state["outcome"] = normalized_outcome
            state["closed_at"] = _timestamp(self.clock())
            state["external_wait"] = None
            state["scheduled_task_id"] = None
            state["revision"] = int(state["revision"]) + 1
            state["updated_at"] = _timestamp(self.clock())
            if desired_status != "blocked":
                state["no_progress_count"] = 0
                state["blocker_key"] = None
                state["blocker_signature"] = None

            committed = self._commit_semantic_change(
                state,
                kind="finished",
                summary=f"Finished continuation run as {desired_status}",
                details={
                    "action": normalized_evidence["action"],
                    "tools": normalized_evidence["tools"],
                    "commands": [
                        {
                            "argv": command["argv"],
                            "result": command["result"],
                            "summary": command["summary"],
                        }
                        for command in normalized_evidence["commands"]
                    ],
                    "result": desired_status,
                    "material_progress": False,
                    "blocker": (
                        normalized_outcome["reason"]
                        if desired_status == "blocked"
                        else None
                    ),
                    "residual_risks": normalized_evidence["residual_risks"],
                    "next_action": normalized_evidence["next_action"],
                    "evidence": {
                        "observed_at": normalized_evidence["observed_at"],
                        "outcome": normalized_outcome,
                        "cleanup_confirmation": cleanup,
                    },
                },
            )
            return committed


def _read_cli_json(path: str) -> Mapping[str, object]:
    if path == "-":
        payload = json.load(
            sys.stdin,
            object_pairs_hook=_strict_json_object,
            parse_constant=_reject_json_constant,
        )
    else:
        input_path = Path(path)
        if input_path.stat().st_size > MAX_STATE_BYTES:
            raise ValueError("CLI input exceeds the size limit")
        with input_path.open("r", encoding="utf-8") as handle:
            payload = json.load(
                handle,
                object_pairs_hook=_strict_json_object,
                parse_constant=_reject_json_constant,
            )
    if not isinstance(payload, Mapping):
        raise ValueError("CLI input must be a JSON object")
    return payload


def _expect_cli_fields(
    payload: Mapping[str, object],
    *,
    required: set[str],
    optional: set[str] = frozenset(),
    label: str,
) -> None:
    unknown = set(payload) - required - optional
    missing = required - set(payload)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")


def _decision_payload(decision: LoopDecision) -> dict[str, object]:
    return {
        "kind": decision.kind,
        "state": decision.state,
        "reason": decision.reason,
        "material_progress": decision.material_progress,
    }


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persist OhMyCodex continuation evidence without controlling Codex"
    )
    parser.add_argument("--repository", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create")
    create.add_argument("--input", required=True)

    for name in ("activate", "iterate", "wait", "reconcile", "finish"):
        command = subparsers.add_parser(name)
        command.add_argument("--run-id", required=True)
        command.add_argument("--input", required=True)

    show = subparsers.add_parser("show")
    show.add_argument("--run-id", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_cli_parser().parse_args(argv)
    ledger = LoopLedger(Path(args.repository))

    if args.command == "show":
        result: dict[str, object] = ledger.load_run(args.run_id)
    else:
        payload = _read_cli_json(args.input)
        if args.command == "create":
            _expect_cli_fields(
                payload,
                required={
                    "objective",
                    "acceptance",
                    "threshold",
                    "baseline",
                    "capabilities",
                    "entrypoint",
                },
                optional={"assumptions", "threshold_reason"},
                label="create input",
            )
            create_args = dict(payload)
            result = ledger.create_run(**create_args)
        elif args.command == "activate":
            _expect_cli_fields(
                payload,
                required={"goal_id"},
                label="activate input",
            )
            result = ledger.activate_run(args.run_id, payload["goal_id"])
        elif args.command == "iterate":
            decision = ledger.record_iteration(args.run_id, payload)
            result = _decision_payload(decision)
        elif args.command == "wait":
            _expect_cli_fields(
                payload,
                required={"external_state", "schedule_id"},
                label="wait input",
            )
            result = ledger.record_wait(
                args.run_id,
                payload["external_state"],
                payload["schedule_id"],
            )
        elif args.command == "reconcile":
            _expect_cli_fields(
                payload,
                required={"current_repository_state"},
                optional={
                    "external_state",
                    "resume_signal",
                    "cleanup_confirmation",
                },
                label="reconcile input",
            )
            decision = ledger.reconcile_run(
                args.run_id,
                payload["current_repository_state"],
                external_state=payload.get("external_state"),
                resume_signal=payload.get("resume_signal"),
                cleanup_confirmation=payload.get("cleanup_confirmation"),
            )
            result = _decision_payload(decision)
        else:
            _expect_cli_fields(
                payload,
                required={"outcome", "evidence"},
                optional={"cleanup_confirmation"},
                label="finish input",
            )
            result = ledger.finish_run(
                args.run_id,
                payload["outcome"],
                payload["evidence"],
                cleanup_confirmation=payload.get("cleanup_confirmation"),
            )

    print(
        json.dumps(
            result,
            allow_nan=False,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
