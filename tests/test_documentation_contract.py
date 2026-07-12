from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ohmycodex"
SKILLS = PLUGIN / "skills"
PUBLIC_DOC_PAIRS = (
    (Path("README.md"), Path("README.zh-CN.md")),
    (Path("CONTRIBUTING.md"), Path("CONTRIBUTING.zh-CN.md")),
    (Path("SECURITY.md"), Path("SECURITY.zh-CN.md")),
    (Path("CODE_OF_CONDUCT.md"), Path("CODE_OF_CONDUCT.zh-CN.md")),
    (Path("docs/compatibility.md"), Path("docs/compatibility.zh-CN.md")),
    (Path("docs/evaluation-matrix.md"), Path("docs/evaluation-matrix.zh-CN.md")),
    (Path("docs/skill-catalog.md"), Path("docs/skill-catalog.zh-CN.md")),
    (Path("docs/team-mode.md"), Path("docs/team-mode.zh-CN.md")),
    (Path("docs/releases/v0.3.0.md"), Path("docs/releases/v0.3.0.zh-CN.md")),
)
RUNTIME_DOCS = tuple(
    ROOT / relative_path
    for pair in PUBLIC_DOC_PAIRS
    for relative_path in pair
)


class DocumentationContractTests(unittest.TestCase):
    def test_public_docs_have_chinese_pairs_and_bidirectional_switches(self) -> None:
        for english_relative, chinese_relative in PUBLIC_DOC_PAIRS:
            english = ROOT / english_relative
            chinese = ROOT / chinese_relative
            with self.subTest(english=english_relative):
                self.assertTrue(english.is_file())
                self.assertTrue(chinese.is_file())
                english_target = chinese.relative_to(english.parent).as_posix()
                chinese_target = english.relative_to(chinese.parent).as_posix()
                self.assertIn(
                    f"English | [简体中文]({english_target})",
                    english.read_text(encoding="utf-8").splitlines()[:3],
                )
                self.assertIn(
                    f"[English]({chinese_target}) | 简体中文",
                    chinese.read_text(encoding="utf-8").splitlines()[:3],
                )

    def test_public_doc_relative_links_resolve(self) -> None:
        for pair in PUBLIC_DOC_PAIRS:
            for relative_path in pair:
                document = ROOT / relative_path
                text = document.read_text(encoding="utf-8")
                for target in re.findall(r"(?<!!)\[[^]]+\]\(([^)]+)\)", text):
                    if target.startswith(("https://", "http://", "mailto:", "#")):
                        continue
                    path = document.parent / target.partition("#")[0]
                    with self.subTest(document=relative_path, target=target):
                        self.assertTrue(path.is_file())

    def test_runtime_docs_use_only_the_canonical_omc_namespace(self) -> None:
        for path in RUNTIME_DOCS:
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertTrue(path.is_file())
                if path.parent.name != "releases":
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
