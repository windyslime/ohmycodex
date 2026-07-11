from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "plugins" / "ohmycodex" / "skills" / "ohmycodex-team" / "scripts" / "install_team_agents.py"
SPEC = importlib.util.spec_from_file_location("install_team_agents", INSTALLER)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)
AGENT_FILENAMES = MODULE.AGENT_FILENAMES
install_templates = MODULE.install_templates


class InstallTeamAgentsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.target = Path(self.tempdir.name) / "project"
        self.target.mkdir()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def test_installs_all_templates_and_safe_defaults_in_fresh_project(self) -> None:
        result = install_templates(self.target)

        self.assertEqual(result.created, list(AGENT_FILENAMES))
        self.assertEqual(result.skipped, [])
        self.assertFalse(result.dry_run)
        config = (self.target / ".codex" / "config.toml").read_text(encoding="utf-8")
        self.assertIn("[agents]", config)
        self.assertIn("max_threads = 4", config)
        self.assertIn("max_depth = 1", config)
        for filename in AGENT_FILENAMES:
            self.assertTrue((self.target / ".codex" / "agents" / filename).is_file())

    def test_preserves_project_owned_agent_and_agents_section(self) -> None:
        agents = self.target / ".codex" / "agents"
        agents.mkdir(parents=True)
        owned = agents / "omc-explorer.toml"
        owned.write_text('name = "omc-explorer"\nmodel = "custom"\n', encoding="utf-8")
        config = self.target / ".codex" / "config.toml"
        config.write_text("[agents]\nmax_threads = 2\n", encoding="utf-8")

        result = install_templates(self.target)

        self.assertIn("omc-explorer.toml", result.skipped)
        self.assertEqual(owned.read_text(encoding="utf-8"), 'name = "omc-explorer"\nmodel = "custom"\n')
        self.assertEqual(config.read_text(encoding="utf-8"), "[agents]\nmax_threads = 2\n")

    def test_dry_run_reports_files_without_writing(self) -> None:
        result = install_templates(self.target, dry_run=True)

        self.assertTrue(result.dry_run)
        self.assertEqual(result.created, list(AGENT_FILENAMES))
        self.assertFalse((self.target / ".codex").exists())


if __name__ == "__main__":
    unittest.main()
