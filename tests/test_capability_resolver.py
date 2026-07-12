from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
RESOLVER = ROOT / "plugins" / "ohmycodex" / "scripts" / "capability_resolver.py"
SPEC = importlib.util.spec_from_file_location("capability_resolver", RESOLVER)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

CapabilitySnapshot = MODULE.CapabilitySnapshot
ProbeResult = MODULE.ProbeResult
resolve_capabilities = MODULE.resolve_capabilities
run_probe = MODULE.run_probe


def host_input(repository: Path, *, goal: bool = False) -> dict[str, object]:
    return {
        "schema_version": 1,
        "surface": "desktop",
        "controls": {
            "goal": {
                "inspect": goal,
                "create": goal,
                "complete": goal,
                "block": goal,
            },
            "scheduled": {"create": False, "delete": False},
            "subagents": False,
            "background_terminal": False,
        },
        "access": {
            "writable_roots": [str(repository)],
            "approval_policy": "never",
            "sandbox_mode": "danger-full-access",
        },
        "tools": [],
    }


class CapabilityResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repository = Path(self.tempdir.name).resolve()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_local_goal_feature_cannot_upgrade_missing_host_controls(self) -> None:
        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "features", "list"):
                return ProbeResult(returncode=0, stdout="goals stable true\n")
            return ProbeResult(returncode=1, stdout="")

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository, goal=False),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertFalse(snapshot["continuation"]["available"])
        self.assertEqual(snapshot["continuation"]["source"], "host")
        self.assertTrue(snapshot["continuation"]["configured_locally"])

    def test_rejects_unknown_host_fields_and_unsupported_schema_version(self) -> None:
        unknown = host_input(self.repository)
        unknown["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            resolve_capabilities(self.repository, unknown, which=lambda _name: None)

        unsupported = host_input(self.repository)
        unsupported["schema_version"] = 2
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            resolve_capabilities(self.repository, unsupported, which=lambda _name: None)

    def test_rejects_relative_writable_roots_and_bool_as_integer(self) -> None:
        relative_root = host_input(self.repository)
        access = relative_root["access"]
        assert isinstance(access, dict)
        access["writable_roots"] = ["relative/path"]
        with self.assertRaisesRegex(ValueError, "writable_roots must be absolute"):
            resolve_capabilities(self.repository, relative_root, which=lambda _name: None)

        boolean_version = host_input(self.repository)
        boolean_version["schema_version"] = True
        with self.assertRaisesRegex(ValueError, "schema_version must be 1"):
            resolve_capabilities(self.repository, boolean_version, which=lambda _name: None)

    def test_filesystem_permissions_cannot_upgrade_missing_host_writable_root(self) -> None:
        host = host_input(self.repository)
        access = host["access"]
        assert isinstance(access, dict)
        access["writable_roots"] = [str(self.repository.parent / "different-root")]

        snapshot = resolve_capabilities(
            self.repository,
            host,
            which=lambda _name: None,
        ).as_dict()

        self.assertFalse(snapshot["workspace"]["writable"])
        self.assertEqual(snapshot["workspace"]["writable_source"], "host")

    def test_mcp_probe_output_is_reduced_to_allowlisted_fields(self) -> None:
        payload = [
            {
                "name": "github",
                "enabled": True,
                "transport": {
                    "type": "streamable_http",
                    "url": "https://example.invalid/mcp?token=secret-token",
                    "http_headers": {"Authorization": "Bearer secret-token"},
                    "env": {"API_KEY": "secret-token"},
                    "args": ["--token", "secret-token"],
                },
                "auth_status": "authenticated",
                "disabled_reason": None,
            }
        ]

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "mcp", "list", "--json"):
                return ProbeResult(returncode=0, stdout=json.dumps(payload))
            return ProbeResult(returncode=0, stdout="")

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertEqual(
            snapshot["configured_mcp"],
            [
                {
                    "name": "github",
                    "enabled": True,
                    "transport": "streamable_http",
                    "auth_status": "authenticated",
                }
            ],
        )
        self.assertNotIn("secret-token", json.dumps(snapshot))

    def test_probe_timeout_records_bounded_warning_without_failing_resolution(self) -> None:
        secret = "credential-that-must-not-be-reported"

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            return ProbeResult(
                returncode=124,
                stdout=secret,
                stderr=secret,
                timed_out=True,
            )

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertEqual(
            snapshot["probe_warnings"],
            ["codex_features_timeout", "codex_mcp_timeout"],
        )
        self.assertNotIn(secret, json.dumps(snapshot))

    def test_invalid_probe_json_records_warning_without_raw_output(self) -> None:
        secret = "truncated-secret-payload"

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "features", "list"):
                return ProbeResult(returncode=0, stdout="goals stable false\n")
            return ProbeResult(returncode=0, stdout=f'{{"token":"{secret}"')

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertEqual(snapshot["probe_warnings"], ["codex_mcp_invalid_json"])
        self.assertNotIn(secret, json.dumps(snapshot))

    def test_rejects_invalid_nested_controls_and_tool_capabilities(self) -> None:
        invalid_control = host_input(self.repository)
        controls = invalid_control["controls"]
        assert isinstance(controls, dict)
        controls["subagents"] = 1
        with self.assertRaisesRegex(ValueError, "subagents must be a boolean"):
            resolve_capabilities(self.repository, invalid_control, which=lambda _name: None)

        invalid_tool = host_input(self.repository)
        invalid_tool["tools"] = [
            {
                "name": "mystery",
                "kind": "mcp",
                "server": "mystery",
                "capabilities": ["execute_arbitrary_policy"],
            }
        ]
        with self.assertRaisesRegex(ValueError, "unsupported tool capability"):
            resolve_capabilities(self.repository, invalid_tool, which=lambda _name: None)

    def test_git_probe_reports_head_dirty_state_and_worktree_fingerprint(self) -> None:
        calls: list[tuple[tuple[str, ...], Path, float]] = []

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            calls.append((argv, cwd, timeout))
            outputs = {
                ("codex", "features", "list"): "goals stable false\n",
                ("codex", "mcp", "list", "--json"): "[]",
                ("git", "rev-parse", "HEAD"): "abc123\n",
                (
                    "git",
                    "status",
                    "--porcelain=v1",
                    "-z",
                    "--untracked-files=all",
                ): " M source.py\0",
                ("git", "diff", "--cached", "--raw", "-z", "HEAD"): "",
            }
            return ProbeResult(returncode=0, stdout=outputs[argv])

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: f"/usr/local/bin/{name}" if name in {"codex", "git"} else None,
            timeout_seconds=2.5,
        ).as_dict()

        git = snapshot["workspace"]["git"]
        self.assertEqual(git["head"], "abc123")
        self.assertTrue(git["available"])
        self.assertTrue(git["dirty"])
        self.assertRegex(git["worktree_fingerprint"], r"^sha256:[0-9a-f]{64}$")
        self.assertTrue(all(isinstance(argv, tuple) for argv, _cwd, _timeout in calls))
        self.assertTrue(all(cwd == self.repository for _argv, cwd, _timeout in calls))
        self.assertTrue(all(timeout == 2.5 for _argv, _cwd, timeout in calls))

    def test_discovers_package_scripts_using_the_existing_lockfile_manager(self) -> None:
        (self.repository / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\n")
        (self.repository / "package.json").write_text(
            json.dumps(
                {
                    "scripts": {
                        "test": "vitest run --token secret-script-value",
                        "lint": "eslint .",
                        "deploy": "publish-to-production",
                    }
                }
            ),
            encoding="utf-8",
        )

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            which=lambda _name: None,
        ).as_dict()

        self.assertEqual(
            snapshot["project_commands"],
            [
                {"name": "test", "argv": ["pnpm", "run", "test"], "source": "package.json"},
                {"name": "lint", "argv": ["pnpm", "run", "lint"], "source": "package.json"},
            ],
        )
        self.assertNotIn("secret-script-value", json.dumps(snapshot))
        self.assertNotIn("publish-to-production", json.dumps(snapshot))

    def test_route_order_prefers_host_then_local_then_project_fallback(self) -> None:
        (self.repository / "package.json").write_text(
            json.dumps({"scripts": {"typecheck": "tsc --noEmit", "codemod": "node codemod.js"}}),
            encoding="utf-8",
        )
        host = host_input(self.repository)
        host["tools"] = [
            {"name": "search", "kind": "native", "capabilities": ["local_search"]},
            {"name": "typescript-lsp", "kind": "mcp", "server": "ts", "capabilities": ["lsp"]},
            {"name": "syntax-tree", "kind": "mcp", "server": "ast", "capabilities": ["ast"]},
            {"name": "browser", "kind": "host", "capabilities": ["browser"]},
        ]

        snapshot = resolve_capabilities(
            self.repository,
            host,
            which=lambda name: f"/usr/local/bin/{name}" if name in {"rg", "sg"} else None,
        ).as_dict()

        self.assertEqual(
            [option["id"] for option in snapshot["routes"]["local_search"][:2]],
            ["host:search", "local:rg"],
        )
        self.assertEqual(snapshot["routes"]["definitions"][0]["id"], "host:typescript-lsp")
        self.assertEqual(snapshot["routes"]["structural_rewrite"][0]["id"], "host:syntax-tree")
        self.assertIn("local:sg", [option["id"] for option in snapshot["routes"]["structural_rewrite"]])
        self.assertIn(
            "project:codemod",
            [option["id"] for option in snapshot["routes"]["structural_rewrite"]],
        )
        self.assertNotIn(
            "local:rg",
            [option["id"] for option in snapshot["routes"]["structural_rewrite"]],
        )

    def test_run_probe_uses_argument_array_timeout_and_bounded_output(self) -> None:
        completed = SimpleNamespace(
            returncode=0,
            stdout="x" * (MODULE.MAX_PROBE_CHARS + 100),
            stderr="y" * (MODULE.MAX_PROBE_CHARS + 100),
        )
        with patch.object(MODULE.subprocess, "run", return_value=completed) as mocked:
            result = run_probe(("tool", "--flag"), self.repository, 1.25)

        mocked.assert_called_once_with(
            ("tool", "--flag"),
            cwd=self.repository,
            capture_output=True,
            check=False,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=1.25,
        )
        self.assertEqual(len(result.stdout), MODULE.MAX_PROBE_CHARS)
        self.assertEqual(len(result.stderr), MODULE.MAX_PROBE_CHARS)

    def test_cli_emits_valid_snapshot_json_without_local_probes(self) -> None:
        host_path = self.repository / "host.json"
        host_path.write_text(
            json.dumps(host_input(self.repository, goal=True)),
            encoding="utf-8",
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(RESOLVER),
                "--repository",
                str(self.repository),
                "--host-input",
                str(host_path),
                "--no-local-probes",
            ],
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        snapshot = json.loads(completed.stdout)
        self.assertTrue(snapshot["continuation"]["available"])
        self.assertEqual(snapshot["configured_mcp"], [])
        self.assertFalse(any(snapshot["local_tools"].values()))

    def test_run_probe_converts_oserror_without_copying_error_text(self) -> None:
        secret = "secret-path-from-oserror"
        with patch.object(
            MODULE.subprocess,
            "run",
            side_effect=FileNotFoundError(secret),
        ):
            result = run_probe(("missing-tool",), self.repository, 1.0)

        self.assertEqual(result.returncode, 127)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertNotIn(secret, repr(result))

    def test_conflicting_goal_feature_rows_fail_closed(self) -> None:
        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "features", "list"):
                return ProbeResult(
                    returncode=0,
                    stdout="goals stable true\ngoals under development false\n",
                )
            return ProbeResult(returncode=0, stdout="[]")

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertFalse(snapshot["continuation"]["configured_locally"])
        self.assertEqual(snapshot["probe_warnings"], ["codex_features_conflict"])

    def test_unknown_mcp_tokens_are_normalized_without_copying_values(self) -> None:
        secret_transport = "secret-transport-token"
        secret_auth = "secret-auth-token"
        payload = [
            {
                "name": "safe-name",
                "enabled": True,
                "transport": {"type": secret_transport},
                "auth_status": secret_auth,
            }
        ]

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "features", "list"):
                return ProbeResult(returncode=0, stdout="goals stable false\n")
            return ProbeResult(returncode=0, stdout=json.dumps(payload))

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertEqual(snapshot["configured_mcp"][0]["transport"], "unknown")
        self.assertEqual(snapshot["configured_mcp"][0]["auth_status"], "unknown")
        self.assertEqual(
            snapshot["probe_warnings"],
            ["codex_mcp_transport_unknown", "codex_mcp_auth_unknown"],
        )
        serialized = json.dumps(snapshot)
        self.assertNotIn(secret_transport, serialized)
        self.assertNotIn(secret_auth, serialized)

    def test_cli_accepts_host_input_from_stdin(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(RESOLVER),
                "--repository",
                str(self.repository),
                "--host-input",
                "-",
                "--no-local-probes",
            ],
            input=json.dumps(host_input(self.repository)),
            capture_output=True,
            check=False,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["schema_version"], 1)

    def test_configured_mcp_does_not_become_an_exposed_tool(self) -> None:
        payload = [
            {
                "name": "code-search",
                "enabled": True,
                "transport": {"type": "stdio"},
                "auth_status": "authenticated",
            }
        ]

        def runner(argv: tuple[str, ...], cwd: Path, timeout: float) -> ProbeResult:
            if argv == ("codex", "features", "list"):
                return ProbeResult(returncode=0, stdout="goals stable false\n")
            return ProbeResult(returncode=0, stdout=json.dumps(payload))

        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            runner=runner,
            which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
        ).as_dict()

        self.assertEqual(snapshot["configured_mcp"][0]["name"], "code-search")
        self.assertEqual(snapshot["exposed_tools"], [])
        self.assertNotIn(
            "host:code-search",
            [option["id"] for option in snapshot["routes"]["external_search"]],
        )

    def test_structural_rewrite_never_falls_back_to_text_search(self) -> None:
        snapshot = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            which=lambda name: "/usr/local/bin/rg" if name == "rg" else None,
        ).as_dict()

        options = snapshot["routes"]["structural_rewrite"]
        self.assertNotIn("local:rg", [option["id"] for option in options])
        self.assertFalse(any(option["available"] for option in options))

    @unittest.skipUnless(shutil.which("git"), "git is required for fingerprint coverage")
    def test_same_dirty_path_with_different_contents_changes_fingerprint(self) -> None:
        subprocess.run(
            ["git", "init", "-q"],
            cwd=self.repository,
            check=True,
        )
        tracked = self.repository / "tracked.txt"
        tracked.write_text("baseline\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.repository, check=True)
        subprocess.run(
            [
                "git",
                "-c",
                "user.name=OMC Test",
                "-c",
                "user.email=omc@example.invalid",
                "commit",
                "-qm",
                "baseline",
            ],
            cwd=self.repository,
            check=True,
        )

        tracked.write_text("first dirty value\n", encoding="utf-8")
        first = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            which=lambda name: shutil.which("git") if name == "git" else None,
        ).as_dict()["workspace"]["git"]["worktree_fingerprint"]

        tracked.write_text("second dirty value\n", encoding="utf-8")
        second = resolve_capabilities(
            self.repository,
            host_input(self.repository),
            which=lambda name: shutil.which("git") if name == "git" else None,
        ).as_dict()["workspace"]["git"]["worktree_fingerprint"]

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
