from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ohmycodex"
SKILLS = PLUGIN / "skills"
REFERENCES = SKILLS / "omc-orchestrator" / "references"
CONTINUATION_SKILLS = ("omc-loop", "omc-intentgate", "omc-letgo")
SHARED_CONTRACTS = (
    "workspace-contract.md",
    "capability-contract.md",
    "loop-contract.md",
)


def skill_text(name: str) -> str:
    path = SKILLS / name / "SKILL.md"
    if not path.is_file():
        raise AssertionError(f"missing continuation Skill: {path}")
    return path.read_text(encoding="utf-8")


def normalized(text: str) -> str:
    return " ".join(text.replace("`", "").split()).lower()


class ContinuationContractTests(unittest.TestCase):
    def test_continuation_entries_are_explicit_only(self) -> None:
        for name in CONTINUATION_SKILLS:
            with self.subTest(skill=name):
                metadata_path = SKILLS / name / "agents" / "openai.yaml"
                self.assertTrue(metadata_path.is_file(), metadata_path)
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

                self.assertFalse(metadata["policy"]["allow_implicit_invocation"])
                self.assertIn(
                    f"${name}",
                    metadata["interface"]["default_prompt"],
                )

    def test_continuation_entries_load_the_shared_contracts(self) -> None:
        for name in CONTINUATION_SKILLS:
            text = skill_text(name)
            with self.subTest(skill=name):
                for contract in SHARED_CONTRACTS:
                    self.assertIn(contract, text)

        intentgate = skill_text("omc-intentgate")
        letgo = skill_text("omc-letgo")
        for name, text in (("omc-intentgate", intentgate), ("omc-letgo", letgo)):
            with self.subTest(skill=name, delegation="doctor"):
                self.assertIn("omc-doctor", text)
            with self.subTest(skill=name, delegation="orchestrator"):
                self.assertIn("omc-orchestrator", text)

    def test_acceptance_is_established_before_any_goal_creation(self) -> None:
        intentgate = skill_text("omc-intentgate")
        intentgate_flat = normalized(intentgate)

        self.assertIn("do not create a goal", intentgate_flat)
        self.assertIn("acceptance contract", intentgate_flat)
        self.assertRegex(intentgate_flat, r"route.+\$?omc-(?:discover|spec)")
        acceptance = intentgate_flat.index("acceptance contract")
        delegation = intentgate_flat.index("delegate", acceptance)
        self.assertLess(acceptance, delegation)

        loop = normalized(skill_text("omc-loop"))
        self.assertRegex(
            loop,
            r"new run.+(?:write|create).+preparing ledger.+before.+goal-create",
        )

    def test_threshold_prompting_is_once_per_new_direct_run(self) -> None:
        for name in ("omc-loop", "omc-intentgate"):
            text = normalized(skill_text(name))
            with self.subTest(skill=name):
                self.assertIn("ask once", text)
                self.assertRegex(text, r"new (?:direct |continuation )?run")
                self.assertRegex(text, r"x\s*>=\s*3|reject (?:x\s*<\s*3|values below 3)")
                self.assertIn("default", text)
                self.assertRegex(text, r"(?:resume|matching existing run)")
                self.assertRegex(text, r"(?:without asking|do not ask|must not ask|never ask)")

        letgo = normalized(skill_text("omc-letgo"))
        self.assertRegex(letgo, r"choos(?:e|es).{0,80}x\s*>=\s*3")
        self.assertRegex(letgo, r"(?:threshold reason|record why that threshold)")
        self.assertRegex(
            letgo,
            r"(?:no|without|does not add).{0,80}(?:ohmycodex )?confirmation",
        )

    def test_native_goal_and_scheduled_own_continuation_and_wakeups(self) -> None:
        loop_contract_path = REFERENCES / "loop-contract.md"
        self.assertTrue(loop_contract_path.is_file(), loop_contract_path)
        contract = normalized(loop_contract_path.read_text(encoding="utf-8"))

        self.assertIn("codex owns automatic continuation", contract)
        self.assertIn("persisted native goal", contract)
        self.assertIn("scheduled owns delayed wakeups only", contract)
        self.assertIn("external state", contract)
        self.assertIn("one ledger iteration is exactly one native goal continuation turn", contract)
        self.assertIn("there is no total", contract)

    def test_mcp_trust_and_external_release_gates_remain_native(self) -> None:
        intentgate = normalized(skill_text("omc-intentgate"))
        letgo = normalized(skill_text("omc-letgo"))

        self.assertRegex(
            intentgate,
            r"(?:one (?:ohmycodex|omc) (?:mcp )?(?:installation )?proposal|propose mcp installation at most once)",
        )
        self.assertIn("codex-native", intentgate)
        self.assertRegex(
            intentgate,
            r"(?:trust|authorization|approval).{0,100}(?:remain|preserve|native)|preserve.{0,100}(?:trust|authorization|approval)",
        )

        self.assertRegex(
            letgo,
            r"(?:without|does not require|no).{0,100}(?:(?:extra|additional|separate).{0,40})?(?:ohmycodex|omc).{0,40}proposal",
        )
        self.assertRegex(
            letgo,
            r"native.{0,80}(?:trust|authorization|permission|approval)|(?:trust|authorization|permission|approval).{0,80}(?:native|mandatory)",
        )
        for action in ("push", "deploy", "tag", "public publication"):
            with self.subTest(release_action=action):
                self.assertIn(action, letgo)
        self.assertRegex(
            letgo,
            r"explicit user (?:control|confirmation).{0,100}immediately before|immediately before.{0,300}(?:user.s required confirmation|explicit user)",
        )

    def test_continuation_entries_forbid_a_replacement_runtime(self) -> None:
        loop = normalized(skill_text("omc-loop"))
        for forbidden in ("shell loop", "stop hook", "daemon"):
            with self.subTest(forbidden=forbidden):
                self.assertIn(forbidden, loop)
        self.assertRegex(loop, r"(?:custom|independent) scheduler")
        self.assertRegex(
            loop,
            r"(?:do not|must not|never).{0,120}(?:shell loop|stop hook|daemon|custom scheduler)",
        )

        for name in CONTINUATION_SKILLS:
            directory = SKILLS / name
            with self.subTest(skill=name, artifact="runtime"):
                self.assertFalse((directory / "hooks").exists())
                self.assertFalse((directory / "scripts").exists())
                self.assertEqual(list(directory.rglob("*.sh")), [])


if __name__ == "__main__":
    unittest.main()
