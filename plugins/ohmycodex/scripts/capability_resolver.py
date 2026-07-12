#!/usr/bin/env python3
"""Resolve active Codex capabilities without mutating the host or repository."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path


ProbeRunner = Callable[[tuple[str, ...], Path, float], "ProbeResult"]
HOST_FIELDS = {"schema_version", "surface", "controls", "access", "tools"}
ACCESS_FIELDS = {"writable_roots", "approval_policy", "sandbox_mode"}
CONTROL_FIELDS = {"goal", "scheduled", "subagents", "background_terminal"}
GOAL_FIELDS = {"inspect", "create", "complete", "block"}
SCHEDULED_FIELDS = {"create", "delete"}
TOOL_FIELDS = {"name", "kind", "server", "capabilities"}
REQUIRED_TOOL_FIELDS = {"name", "kind", "capabilities"}
SUPPORTED_TOOL_CAPABILITIES = {
    "local_search",
    "lsp",
    "ast",
    "code_search",
    "official_docs",
    "browser",
    "web",
}
MAX_PROBE_CHARS = 64_000
MAX_MANIFEST_BYTES = 1_000_000
MAX_HOST_INPUT_CHARS = 1_000_000
PROJECT_SCRIPT_NAMES = (
    "test",
    "lint",
    "typecheck",
    "check",
    "build",
    "format",
    "search",
    "parse",
    "codemod",
)
PACKAGE_LOCKFILES = (
    ("pnpm-lock.yaml", "pnpm"),
    ("yarn.lock", "yarn"),
    ("bun.lock", "bun"),
    ("bun.lockb", "bun"),
    ("package-lock.json", "npm"),
)
MCP_NAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,128}$")
MCP_TRANSPORTS = {"stdio", "streamable_http"}
MCP_AUTH_STATUSES = {"authenticated", "not_authenticated", "unsupported", "disabled", "unknown"}


@dataclass(frozen=True)
class ProbeResult:
    returncode: int
    stdout: str
    stderr: str = ""
    timed_out: bool = False


@dataclass(frozen=True)
class CapabilitySnapshot:
    data: dict[str, object]

    def as_dict(self) -> dict[str, object]:
        return copy.deepcopy(self.data)


def _expect_exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    unknown = set(value) - expected
    missing = expected - set(value)
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")


def _validate_host_envelope(host_capabilities: Mapping[str, object]) -> None:
    _expect_exact_keys(host_capabilities, HOST_FIELDS, "host input")
    if host_capabilities["schema_version"] != 1 or isinstance(
        host_capabilities["schema_version"], bool
    ):
        raise ValueError("schema_version must be 1")


def _validate_access(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("access must be an object")
    _expect_exact_keys(value, ACCESS_FIELDS, "access")
    roots = value["writable_roots"]
    if not isinstance(roots, list) or any(not isinstance(root, str) for root in roots):
        raise ValueError("writable_roots must be a list of paths")
    if any(not Path(root).is_absolute() for root in roots):
        raise ValueError("writable_roots must be absolute")
    for field in ("approval_policy", "sandbox_mode"):
        if not isinstance(value[field], str) or not value[field].strip():
            raise ValueError(f"{field} must be a non-empty string")


def _expect_boolean(value: object, label: str) -> None:
    if type(value) is not bool:
        raise ValueError(f"{label} must be a boolean")


def _validate_controls(value: object) -> None:
    if not isinstance(value, Mapping):
        raise ValueError("controls must be an object")
    _expect_exact_keys(value, CONTROL_FIELDS, "controls")
    goal = value["goal"]
    if not isinstance(goal, Mapping):
        raise ValueError("goal controls must be an object")
    _expect_exact_keys(goal, GOAL_FIELDS, "goal controls")
    for field in GOAL_FIELDS:
        _expect_boolean(goal[field], f"goal.{field}")
    scheduled = value["scheduled"]
    if not isinstance(scheduled, Mapping):
        raise ValueError("scheduled controls must be an object")
    _expect_exact_keys(scheduled, SCHEDULED_FIELDS, "scheduled controls")
    for field in SCHEDULED_FIELDS:
        _expect_boolean(scheduled[field], f"scheduled.{field}")
    _expect_boolean(value["subagents"], "subagents")
    _expect_boolean(value["background_terminal"], "background_terminal")


def _validate_tools(value: object) -> None:
    if not isinstance(value, list):
        raise ValueError("tools must be a list")
    for index, tool in enumerate(value):
        if not isinstance(tool, Mapping):
            raise ValueError(f"tools[{index}] must be an object")
        unknown = set(tool) - TOOL_FIELDS
        missing = REQUIRED_TOOL_FIELDS - set(tool)
        if unknown:
            raise ValueError(f"tools[{index}] has unknown fields: {', '.join(sorted(unknown))}")
        if missing:
            raise ValueError(f"tools[{index}] is missing fields: {', '.join(sorted(missing))}")
        for field in ("name", "kind"):
            if not isinstance(tool[field], str) or not tool[field].strip():
                raise ValueError(f"tools[{index}].{field} must be a non-empty string")
        if "server" in tool and (
            not isinstance(tool["server"], str) or not tool["server"].strip()
        ):
            raise ValueError(f"tools[{index}].server must be a non-empty string")
        capabilities = tool["capabilities"]
        if not isinstance(capabilities, list) or any(
            not isinstance(capability, str) for capability in capabilities
        ):
            raise ValueError(f"tools[{index}].capabilities must be a list of strings")
        unsupported = set(capabilities) - SUPPORTED_TOOL_CAPABILITIES
        if unsupported:
            raise ValueError(
                f"unsupported tool capability: {', '.join(sorted(unsupported))}"
            )


def _host_allows_repository(repository: Path, access: Mapping[str, object]) -> bool:
    roots = access["writable_roots"]
    assert isinstance(roots, list)
    return any(
        repository == Path(root).resolve() or repository.is_relative_to(Path(root).resolve())
        for root in roots
    )


def _feature_state(output: str, feature: str) -> tuple[bool, str | None]:
    values: set[bool] = set()
    for line in output.splitlines():
        columns = line.split()
        if len(columns) < 2 or columns[0] != feature:
            continue
        if columns[-1] not in {"true", "false"}:
            return False, "codex_features_invalid"
        values.add(columns[-1] == "true")
    if len(values) > 1:
        return False, "codex_features_conflict"
    return values == {True}, None


def _reduce_mcp_probe(result: ProbeResult) -> tuple[list[dict[str, object]], list[str]]:
    if result.timed_out:
        return [], ["codex_mcp_timeout"]
    if result.returncode != 0:
        return [], ["codex_mcp_unavailable"]
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return [], ["codex_mcp_invalid_json"]
    if not isinstance(payload, list):
        return [], ["codex_mcp_unexpected_shape"]

    reduced: list[dict[str, object]] = []
    warnings: list[str] = []
    for entry in payload:
        if not isinstance(entry, Mapping):
            continue
        name = entry.get("name")
        enabled = entry.get("enabled")
        auth_status = entry.get("auth_status")
        transport_value = entry.get("transport")
        if isinstance(transport_value, Mapping):
            transport = transport_value.get("type")
        else:
            transport = transport_value
        if (
            not isinstance(name, str)
            or not MCP_NAME_RE.fullmatch(name)
            or not isinstance(enabled, bool)
            or not isinstance(transport, str)
            or not isinstance(auth_status, str)
        ):
            continue
        if transport not in MCP_TRANSPORTS:
            transport = "unknown"
            if "codex_mcp_transport_unknown" not in warnings:
                warnings.append("codex_mcp_transport_unknown")
        if auth_status not in MCP_AUTH_STATUSES:
            auth_status = "unknown"
            if "codex_mcp_auth_unknown" not in warnings:
                warnings.append("codex_mcp_auth_unknown")
        reduced.append(
            {
                "name": name,
                "enabled": enabled,
                "transport": transport,
                "auth_status": auth_status,
            }
        )
    return reduced, warnings


def _probe_git(
    repository: Path,
    runner: ProbeRunner,
    timeout_seconds: float,
) -> tuple[dict[str, object], list[str]]:
    commands = (
        ("git", "rev-parse", "HEAD"),
        ("git", "status", "--porcelain=v1", "-z", "--untracked-files=all"),
        ("git", "diff", "--cached", "--raw", "-z", "HEAD"),
    )
    results = [runner(command, repository, timeout_seconds) for command in commands]
    if any(result.timed_out for result in results):
        return (
            {
                "available": False,
                "head": None,
                "dirty": None,
                "worktree_fingerprint": None,
                "evidence_strength": "files",
            },
            ["git_probe_timeout"],
        )
    if any(result.returncode != 0 for result in results):
        return (
            {
                "available": False,
                "head": None,
                "dirty": None,
                "worktree_fingerprint": None,
                "evidence_strength": "files",
            },
            ["git_state_unavailable"],
        )

    head = results[0].stdout.strip()
    status = results[1].stdout
    cached = results[2].stdout
    digest = hashlib.sha256(
        "\0".join((head, status, cached)).encode("utf-8", errors="replace")
    ).hexdigest()
    return (
        {
            "available": True,
            "head": head,
            "dirty": bool(status or cached),
            "worktree_fingerprint": f"sha256:{digest}",
            "evidence_strength": "git",
        },
        [],
    )


def _discover_project_commands(
    repository: Path,
) -> tuple[list[dict[str, object]], list[str]]:
    manifest_path = repository / "package.json"
    if not manifest_path.is_file():
        return [], []
    try:
        if manifest_path.stat().st_size > MAX_MANIFEST_BYTES:
            return [], ["package_manifest_too_large"]
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return [], ["package_manifest_invalid"]
    if not isinstance(manifest, Mapping):
        return [], ["package_manifest_unexpected_shape"]

    manager: str | None = None
    declared_manager = manifest.get("packageManager")
    if isinstance(declared_manager, str):
        candidate = declared_manager.split("@", 1)[0]
        if candidate in {"npm", "pnpm", "yarn", "bun"}:
            manager = candidate
    if manager is None:
        manager = next(
            (
                candidate
                for lockfile, candidate in PACKAGE_LOCKFILES
                if (repository / lockfile).exists()
            ),
            "npm",
        )

    scripts = manifest.get("scripts", {})
    if not isinstance(scripts, Mapping):
        return [], ["package_scripts_unexpected_shape"]
    commands = [
        {
            "name": name,
            "argv": [manager, "run", name],
            "source": "package.json",
        }
        for name in PROJECT_SCRIPT_NAMES
        if isinstance(scripts.get(name), str)
    ]
    return commands, []


def _route_option(
    identifier: str,
    available: bool,
    source: str,
    *,
    argv: list[str] | None = None,
    limitations: list[str] | None = None,
) -> dict[str, object]:
    option: dict[str, object] = {
        "id": identifier,
        "available": available,
        "source": source,
        "limitations": limitations or [],
    }
    if argv is not None:
        option["argv"] = argv
    return option


def _host_route_options(
    tools: list[dict[str, object]], capability: str
) -> list[dict[str, object]]:
    return [
        _route_option(f"host:{tool['name']}", True, "host")
        for tool in tools
        if capability in tool["capabilities"]
    ]


def _normalize_host_tools(value: object) -> list[dict[str, object]]:
    assert isinstance(value, list)
    normalized: list[dict[str, object]] = []
    for tool in value:
        assert isinstance(tool, Mapping)
        item: dict[str, object] = {
            "name": str(tool["name"])[:128],
            "kind": str(tool["kind"])[:64],
            "capabilities": list(tool["capabilities"]),
        }
        if "server" in tool:
            item["server"] = str(tool["server"])[:128]
        normalized.append(item)
    return normalized


def _build_routes(
    tools: list[dict[str, object]],
    local_tools: Mapping[str, bool],
    project_commands: list[dict[str, object]],
    scheduled_available: bool,
    subagents_available: bool,
    background_terminal_available: bool,
    continuation_available: bool,
) -> dict[str, list[dict[str, object]]]:
    project = {str(command["name"]): command for command in project_commands}

    local_search = _host_route_options(tools, "local_search")
    local_search.append(
        _route_option("local:rg", local_tools["rg"], "local", argv=["rg"])
    )
    if "search" in project:
        local_search.append(
            _route_option(
                "project:search", True, "project", argv=list(project["search"]["argv"])
            )
        )
    local_search.append(
        _route_option(
            "fallback:file-inspection",
            True,
            "fallback",
            limitations=["slower than indexed search"],
        )
    )

    definitions = _host_route_options(tools, "lsp")
    for name in ("typecheck", "check", "build"):
        if name in project:
            definitions.append(
                _route_option(
                    f"project:{name}", True, "project", argv=list(project[name]["argv"])
                )
            )
    definitions.append(
        _route_option(
            "fallback:static-inspection",
            True,
            "fallback",
            limitations=["no live definitions or diagnostics"],
        )
    )

    structural_query = _host_route_options(tools, "ast")
    structural_rewrite = _host_route_options(tools, "ast")
    for executable in ("sg", "ast-grep"):
        option = _route_option(
            f"local:{executable}",
            local_tools[executable],
            "local",
            argv=[executable],
        )
        structural_query.append(option)
        structural_rewrite.append(copy.deepcopy(option))
    if "parse" in project:
        structural_query.append(
            _route_option(
                "project:parse", True, "project", argv=list(project["parse"]["argv"])
            )
        )
    if "codemod" in project:
        structural_rewrite.append(
            _route_option(
                "project:codemod",
                True,
                "project",
                argv=list(project["codemod"]["argv"]),
            )
        )
    structural_query.append(
        _route_option(
            "unavailable:structural-query",
            False,
            "fallback",
            limitations=["text search may locate candidates only"],
        )
    )
    structural_rewrite.append(
        _route_option(
            "unavailable:structural-rewrite",
            False,
            "fallback",
            limitations=["requires an AST tool, codemod, or standard parser"],
        )
    )

    external_search = _host_route_options(tools, "code_search")
    external_search.extend(_host_route_options(tools, "browser"))
    external_search.extend(_host_route_options(tools, "web"))
    external_search.append(
        _route_option("unavailable:external-search", False, "fallback")
    )

    official_docs = _host_route_options(tools, "official_docs")
    official_docs.extend(_host_route_options(tools, "browser"))
    official_docs.extend(_host_route_options(tools, "web"))
    official_docs.append(
        _route_option(
            "unavailable:official-docs",
            False,
            "fallback",
            limitations=["do not substitute unverified documentation"],
        )
    )

    return {
        "local_search": local_search,
        "definitions": definitions,
        "structural_query": structural_query,
        "structural_rewrite": structural_rewrite,
        "external_search": external_search,
        "official_docs": official_docs,
        "parallel_investigation": [
            _route_option("host:subagents", subagents_available, "host"),
            _route_option(
                "fallback:parent-sequence",
                True,
                "fallback",
                limitations=["no parallel execution"],
            ),
        ],
        "external_wait": [
            _route_option("host:scheduled", scheduled_available, "host"),
            _route_option(
                "host:background-terminal",
                background_terminal_available,
                "host",
                limitations=["short-lived processes only"],
            ),
            _route_option(
                "host:recoverable-goal",
                continuation_available,
                "host",
                limitations=["requires a later user or host wakeup"],
            ),
        ],
    }


def run_probe(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
    try:
        completed = subprocess.run(
            argv,
            cwd=cwd,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(returncode=124, stdout="", timed_out=True)
    except OSError:
        return ProbeResult(returncode=127, stdout="")
    return ProbeResult(
        returncode=completed.returncode,
        stdout=completed.stdout[:MAX_PROBE_CHARS],
        stderr=completed.stderr[:MAX_PROBE_CHARS],
    )


def resolve_capabilities(
    repository: Path,
    host_capabilities: Mapping[str, object],
    *,
    runner: ProbeRunner = run_probe,
    which: Callable[[str], str | None] = shutil.which,
    timeout_seconds: float = 5.0,
    local_probes: bool = True,
) -> CapabilitySnapshot:
    repository = repository.resolve()
    _validate_host_envelope(host_capabilities)
    if not isinstance(host_capabilities["surface"], str) or not host_capabilities[
        "surface"
    ].strip():
        raise ValueError("surface must be a non-empty string")
    _validate_controls(host_capabilities["controls"])
    _validate_access(host_capabilities["access"])
    _validate_tools(host_capabilities["tools"])
    access = host_capabilities["access"]
    assert isinstance(access, Mapping)
    controls = host_capabilities["controls"]
    assert isinstance(controls, Mapping)
    goal = controls["goal"]
    assert isinstance(goal, Mapping)
    operations = {
        operation: goal[operation]
        for operation in ("inspect", "create", "complete", "block")
    }
    continuation_available = all(value is True for value in operations.values())
    scheduled_controls = controls["scheduled"]
    assert isinstance(scheduled_controls, Mapping)
    scheduled_operations = {
        operation: scheduled_controls[operation] for operation in ("create", "delete")
    }
    scheduled_available = all(value is True for value in scheduled_operations.values())
    host_tools = _normalize_host_tools(host_capabilities["tools"])

    configured_locally = False
    configured_mcp: list[dict[str, object]] = []
    probe_warnings: list[str] = []
    git_state: dict[str, object] = {
        "available": False,
        "head": None,
        "dirty": None,
        "worktree_fingerprint": None,
        "evidence_strength": "files",
    }
    if local_probes and which("codex"):
        probe = runner(("codex", "features", "list"), repository, timeout_seconds)
        if probe.timed_out:
            probe_warnings.append("codex_features_timeout")
        elif probe.returncode == 0:
            configured_locally, feature_warning = _feature_state(probe.stdout, "goals")
            if feature_warning:
                probe_warnings.append(feature_warning)
        else:
            probe_warnings.append("codex_features_unavailable")
        mcp_probe = runner(("codex", "mcp", "list", "--json"), repository, timeout_seconds)
        configured_mcp, mcp_warnings = _reduce_mcp_probe(mcp_probe)
        probe_warnings.extend(mcp_warnings)
    if local_probes and which("git"):
        git_state, git_warnings = _probe_git(repository, runner, timeout_seconds)
        probe_warnings.extend(git_warnings)
    if local_probes:
        project_commands, project_warnings = _discover_project_commands(repository)
    else:
        project_commands, project_warnings = [], []
    probe_warnings.extend(project_warnings)
    local_tools = {
        executable: local_probes and which(executable) is not None
        for executable in ("rg", "sg", "ast-grep")
    }
    routes = _build_routes(
        host_tools,
        local_tools,
        project_commands,
        scheduled_available,
        controls["subagents"] is True,
        controls["background_terminal"] is True,
        continuation_available,
    )

    return CapabilitySnapshot(
        {
            "schema_version": 1,
            "surface": host_capabilities["surface"],
            "continuation": {
                "available": continuation_available,
                "operations": operations,
                "source": "host",
                "configured_locally": configured_locally,
            },
            "scheduled": {
                "available": scheduled_available,
                "operations": scheduled_operations,
                "source": "host",
            },
            "subagents": {
                "available": controls["subagents"],
                "source": "host",
            },
            "background_terminal": {
                "available": controls["background_terminal"],
                "source": "host",
            },
            "approval": {
                "policy": access["approval_policy"],
                "sandbox_mode": access["sandbox_mode"],
                "source": "host",
            },
            "workspace": {
                "repository": str(repository),
                "writable": _host_allows_repository(repository, access),
                "writable_source": "host",
                "git": git_state,
            },
            "exposed_tools": host_tools,
            "configured_mcp": configured_mcp,
            "local_tools": local_tools,
            "project_commands": project_commands,
            "routes": routes,
            "probe_warnings": probe_warnings,
        }
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--host-input", required=True)
    parser.add_argument("--no-local-probes", action="store_true")
    args = parser.parse_args(argv)

    try:
        if args.host_input == "-":
            host_text = sys.stdin.read(MAX_HOST_INPUT_CHARS + 1)
        else:
            host_path = Path(args.host_input)
            if host_path.stat().st_size > MAX_HOST_INPUT_CHARS:
                raise ValueError("host input is too large")
            host_text = host_path.read_text(encoding="utf-8")
        if len(host_text) > MAX_HOST_INPUT_CHARS:
            raise ValueError("host input is too large")
        host_capabilities = json.loads(host_text)
        if not isinstance(host_capabilities, Mapping):
            raise ValueError("host input must be a JSON object")
        snapshot = resolve_capabilities(
            args.repository,
            host_capabilities,
            local_probes=not args.no_local_probes,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as error:
        print(f"capability resolver error: {error}", file=sys.stderr)
        return 2

    print(json.dumps(snapshot.as_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
