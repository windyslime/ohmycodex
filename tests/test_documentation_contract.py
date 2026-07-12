from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ohmycodex"
SKILLS = PLUGIN / "skills"
RUNTIME_DOCS = (
    ROOT / "README.md",
    ROOT / "README.zh-CN.md",
    ROOT / "docs" / "compatibility.md",
    ROOT / "docs" / "evaluation-matrix.md",
    ROOT / "docs" / "skill-catalog.md",
    ROOT / "docs" / "team-mode.md",
    ROOT / "docs" / "releases" / "v0.3.0.md",
    ROOT / "CONTRIBUTING.md",
)


class DocumentationContractTests(unittest.TestCase):
    def test_runtime_docs_use_only_the_canonical_omc_namespace(self) -> None:
        for path in RUNTIME_DOCS:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())
                if path.name != "v0.3.0.md":
                    self.assertNotIn("ohmycodex-", path.read_text(encoding="utf-8"))

    def test_catalog_lists_all_nineteen_skills(self) -> None:
        catalog = (ROOT / "docs" / "skill-catalog.md").read_text(encoding="utf-8")
        names = {
            path.name
            for path in SKILLS.iterdir()
            if (path / "SKILL.md").is_file()
        }
        self.assertEqual(len(names), 19)
        for name in names:
            self.assertIn(f"`{name}`", catalog)

    def test_v03_breaking_migration_and_native_fallbacks_are_documented(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
        release = (ROOT / "docs" / "releases" / "v0.3.0.md").read_text(
            encoding="utf-8"
        ).lower()
        compatibility = (ROOT / "docs" / "compatibility.md").read_text(
            encoding="utf-8"
        ).lower()

        self.assertIn("breaking", readme)
        self.assertIn("breaking", release)
        self.assertIn("no compatibility aliases", release)
        self.assertIn("goal", compatibility)
        self.assertIn("scheduled", compatibility)
        self.assertIn("recoverable goal", compatibility)
        self.assertIn("restart", readme)

    def test_workspace_contract_declares_loop_state_paths(self) -> None:
        contract = (
            SKILLS / "omc-orchestrator" / "references" / "workspace-contract.md"
        ).read_text(encoding="utf-8")
        self.assertIn("runtime/loops/", contract)
        self.assertIn("plans/loop-runs/", contract)
        self.assertIn("JSON", contract)
        self.assertIn("exempt", contract)

    def test_ci_and_pr_template_run_the_full_validation_set(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "validate.yml").read_text(
            encoding="utf-8"
        )
        template = (ROOT / ".github" / "pull_request_template.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("python3 -m unittest discover -s tests -v", workflow)
        self.assertIn("python3 scripts/validate_plugin.py", workflow)
        for phrase in ("unit tests", "custom validation", "official plugin validation", "new-task smoke test"):
            self.assertIn(phrase, template.lower())

    def test_manifest_and_plugin_bundle_no_runtime_extensions(self) -> None:
        manifest = json.loads(
            (PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
        )
        self.assertFalse({"apps", "mcpServers", "hooks"} & set(manifest))
        forbidden_names = {"hooks", "apps", "mcp", "mcp-servers", "telemetry", "daemon"}
        bundled = {path.name.lower() for path in PLUGIN.rglob("*")}
        self.assertFalse(forbidden_names & bundled)


if __name__ == "__main__":
    unittest.main()
