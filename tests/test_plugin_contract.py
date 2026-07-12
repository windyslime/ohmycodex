from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "plugins" / "ohmycodex" / "skills"
MANIFEST = ROOT / "plugins" / "ohmycodex" / ".codex-plugin" / "plugin.json"


class PluginContractTests(unittest.TestCase):
    def test_existing_skills_use_only_the_omc_namespace(self) -> None:
        expected = {
            "omc-orchestrator",
            "omc-init",
            "omc-discover",
            "omc-spec",
            "omc-architecture",
            "omc-implement",
            "omc-qa",
            "omc-debug",
            "omc-refactor",
            "omc-review",
            "omc-release",
            "omc-debt",
            "omc-team",
        }

        discovered = {
            path.name
            for path in SKILLS.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }

        self.assertEqual(discovered, expected)
        self.assertFalse(any(name.startswith("ohmycodex-") for name in discovered))

    def test_skill_frontmatter_name_matches_its_directory(self) -> None:
        for directory in SKILLS.iterdir():
            skill = directory / "SKILL.md"
            if not directory.is_dir() or not skill.is_file():
                continue
            match = re.match(r"^---\nname: ([^\n]+)\n", skill.read_text(encoding="utf-8"))
            self.assertIsNotNone(match, directory.name)
            assert match is not None
            self.assertEqual(match.group(1), directory.name)

    def test_lifecycle_metadata_is_structured_and_implicitly_invocable(self) -> None:
        for directory in SKILLS.iterdir():
            skill = directory / "SKILL.md"
            if not directory.is_dir() or not skill.is_file():
                continue
            metadata = json.loads(
                (directory / "agents" / "openai.yaml").read_text(encoding="utf-8")
            )
            self.assertIn(f"${directory.name}", metadata["interface"]["default_prompt"])
            self.assertTrue(metadata["policy"]["allow_implicit_invocation"])

    def test_manifest_uses_v03_base_and_canonical_starter_prompts(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        version, separator, metadata = manifest["version"].partition("+")

        self.assertEqual(manifest["name"], "ohmycodex")
        self.assertEqual(version, "0.3.0")
        if separator:
            self.assertTrue(metadata.startswith("codex."))
            self.assertNotIn("+", metadata)
        for prompt in manifest["interface"]["defaultPrompt"]:
            self.assertIn("$omc-", prompt)
            self.assertNotIn("$ohmycodex-", prompt)


if __name__ == "__main__":
    unittest.main()
