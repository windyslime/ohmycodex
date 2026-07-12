from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "plugins" / "ohmycodex" / "scripts" / "locale_manager.py"
SPEC = importlib.util.spec_from_file_location("locale_manager", MANAGER)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

apply_locale = MODULE.apply_locale
inspect_locale = MODULE.inspect_locale
validate_catalogs = MODULE.validate_catalogs
ACTUAL_PLUGIN = ROOT / "plugins" / "ohmycodex"


def canonical(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


class LocaleManagerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.plugin = self.root / "plugin"
        self.codex_home = self.root / "codex"
        self.locales = self.plugin / "assets" / "locales"
        self.skills = self.plugin / "skills"
        self.manifest = self.plugin / ".codex-plugin" / "plugin.json"
        self.skill_names = ("omc-alpha", "omc-beta")
        self._create_fixture()

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def _catalog(self, locale: str) -> dict[str, object]:
        chinese = locale == "zh-CN"
        return {
            "schema_version": 1,
            "locale": locale,
            "manifest": {
                "description": "插件描述" if chinese else "Plugin description",
                "displayName": "插件名称" if chinese else "Plugin Name",
                "shortDescription": "简短描述" if chinese else "Short description",
                "longDescription": "详细描述" if chinese else "Long description",
                "defaultPrompt": [
                    f"Use ${name} for {'这个任务' if chinese else 'this task'}."
                    for name in ("omc-alpha", "omc-beta", "omc-alpha")
                ],
            },
            "skills": {
                name: {
                    "display_name": f"{'ZH' if chinese else 'EN'} {name}",
                    "short_description": f"{'ZH' if chinese else 'EN'} description {name}",
                    "default_prompt": f"Use ${name} for {'这个任务' if chinese else 'this task'}.",
                }
                for name in self.skill_names
            },
        }

    def _create_fixture(self) -> None:
        self.locales.mkdir(parents=True)
        self.manifest.parent.mkdir(parents=True)
        catalogs = {locale: self._catalog(locale) for locale in ("en", "zh-CN")}
        for locale, catalog in catalogs.items():
            (self.locales / f"{locale}.json").write_bytes(canonical(catalog))

        english = catalogs["en"]
        manifest_fields = english["manifest"]
        assert isinstance(manifest_fields, dict)
        self.manifest.write_bytes(
            canonical(
                {
                    "name": "fixture-plugin",
                    "version": "1.2.3",
                    "description": manifest_fields["description"],
                    "author": {"name": "Fixture"},
                    "interface": {
                        "displayName": manifest_fields["displayName"],
                        "shortDescription": manifest_fields["shortDescription"],
                        "longDescription": manifest_fields["longDescription"],
                        "defaultPrompt": manifest_fields["defaultPrompt"],
                        "category": "Productivity",
                        "capabilities": ["Write"],
                    },
                }
            )
        )
        skill_catalog = english["skills"]
        assert isinstance(skill_catalog, dict)
        for name in self.skill_names:
            metadata = self.skills / name / "agents" / "openai.yaml"
            metadata.parent.mkdir(parents=True)
            metadata.write_bytes(
                canonical(
                    {
                        "interface": skill_catalog[name],
                        "policy": {"allow_implicit_invocation": name == "omc-alpha"},
                        "dependencies": {"tools": ["read"]},
                    }
                )
            )
            (self.skills / name / "SKILL.md").write_text(f"# {name}\n")

    def test_catalogs_validate_exact_coverage_and_prompt_references(self) -> None:
        catalogs = validate_catalogs(self.plugin)

        self.assertEqual(set(catalogs), {"en", "zh-CN"})
        self.assertEqual(set(catalogs["en"]["skills"]), set(self.skill_names))

    def test_catalog_validation_rejects_unknown_fields_and_foreign_prompts(self) -> None:
        chinese_path = self.locales / "zh-CN.json"
        catalog = json.loads(chinese_path.read_text())
        catalog["unexpected"] = True
        chinese_path.write_bytes(canonical(catalog))
        with self.assertRaisesRegex(ValueError, "unknown fields"):
            validate_catalogs(self.plugin)

        catalog.pop("unexpected")
        catalog["manifest"]["defaultPrompt"][0] = "Use $foreign-skill now."
        chinese_path.write_bytes(canonical(catalog))
        with self.assertRaisesRegex(ValueError, "manifest.defaultPrompt"):
            validate_catalogs(self.plugin)

        catalog = self._catalog("zh-CN")
        catalog["skills"]["omc-alpha"]["default_prompt"] = (
            "Use $omc-alpha-extra instead."
        )
        chinese_path.write_bytes(canonical(catalog))
        with self.assertRaisesRegex(ValueError, "must reference \\$omc-alpha"):
            validate_catalogs(self.plugin)

    def test_catalog_validation_rejects_unsupported_catalog_files(self) -> None:
        (self.locales / "fr.json").write_bytes(canonical(self._catalog("en")))

        with self.assertRaisesRegex(ValueError, "unsupported locale catalog"):
            validate_catalogs(self.plugin)

    def test_inspect_locale_reports_default_english_without_writing(self) -> None:
        before = {
            path: path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }

        status = inspect_locale(self.plugin, self.codex_home)

        self.assertIsNone(status["saved_preference"])
        self.assertEqual(status["effective_preference"], "en")
        self.assertEqual(status["materialized_locale"], "en")
        self.assertTrue(status["consistent"])
        self.assertFalse(status["restart_or_new_task_recommended"])
        after = {
            path: path.read_bytes()
            for path in self.root.rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)

    def test_inspect_locale_detects_saved_chinese_with_english_metadata(self) -> None:
        preference = self.codex_home / "ohmycodex" / "preferences.json"
        preference.parent.mkdir(parents=True)
        preference.write_bytes(canonical({"schema_version": 1, "language": "zh-CN"}))

        status = inspect_locale(self.plugin, self.codex_home)

        self.assertEqual(status["saved_preference"], "zh-CN")
        self.assertEqual(status["materialized_locale"], "en")
        self.assertFalse(status["consistent"])
        self.assertIn("$omc-cn", status["recommendation"])
        self.assertFalse(status["restart_or_new_task_recommended"])

    def test_switch_to_chinese_updates_only_translatable_fields_and_preference(self) -> None:
        original_manifest = json.loads(self.manifest.read_text())
        original_metadata = {
            name: json.loads(
                (self.skills / name / "agents" / "openai.yaml").read_text()
            )
            for name in self.skill_names
        }

        result = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertTrue(result.available)
        self.assertTrue(result.changed)
        self.assertTrue(result.restart_required)
        chinese = json.loads((self.locales / "zh-CN.json").read_text())
        switched_manifest = json.loads(self.manifest.read_text())
        self.assertEqual(switched_manifest["description"], chinese["manifest"]["description"])
        for field in ("displayName", "shortDescription", "longDescription", "defaultPrompt"):
            self.assertEqual(
                switched_manifest["interface"][field], chinese["manifest"][field]
            )
        self.assertEqual(switched_manifest["name"], original_manifest["name"])
        self.assertEqual(switched_manifest["version"], original_manifest["version"])
        self.assertEqual(
            switched_manifest["interface"]["category"],
            original_manifest["interface"]["category"],
        )
        for name in self.skill_names:
            switched = json.loads(
                (self.skills / name / "agents" / "openai.yaml").read_text()
            )
            self.assertEqual(switched["interface"], chinese["skills"][name])
            self.assertEqual(switched["policy"], original_metadata[name]["policy"])
            self.assertEqual(
                switched["dependencies"], original_metadata[name]["dependencies"]
            )
        preference = json.loads(
            (self.codex_home / "ohmycodex" / "preferences.json").read_text()
        )
        self.assertEqual(preference, {"schema_version": 1, "language": "zh-CN"})

    def test_english_chinese_english_round_trip_is_exact_and_idempotent(self) -> None:
        metadata_paths = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        original = {path: path.read_bytes() for path in metadata_paths}

        apply_locale(self.plugin, self.codex_home, "zh-CN")
        restored = apply_locale(self.plugin, self.codex_home, "en")
        repeated = apply_locale(self.plugin, self.codex_home, "en")

        self.assertTrue(restored.changed)
        self.assertFalse(repeated.changed)
        self.assertEqual({path: path.read_bytes() for path in metadata_paths}, original)
        self.assertEqual(inspect_locale(self.plugin, self.codex_home)["materialized_locale"], "en")

    def test_invalid_catalog_fails_before_any_target_changes(self) -> None:
        targets = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        before = {path: path.read_bytes() for path in targets}
        chinese_path = self.locales / "zh-CN.json"
        catalog = json.loads(chinese_path.read_text())
        del catalog["skills"]["omc-beta"]
        chinese_path.write_bytes(canonical(catalog))

        with self.assertRaisesRegex(ValueError, "coverage mismatch"):
            apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertEqual({path: path.read_bytes() for path in targets}, before)
        self.assertFalse((self.codex_home / "ohmycodex" / "preferences.json").exists())

    def test_invalid_metadata_fails_before_any_target_changes(self) -> None:
        invalid = self.skills / "omc-beta" / "agents" / "openai.yaml"
        invalid.write_text("not: [valid JSON")
        targets = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        before = {path: path.read_bytes() for path in targets}

        with self.assertRaisesRegex(ValueError, "invalid omc-beta metadata"):
            apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertEqual({path: path.read_bytes() for path in targets}, before)
        self.assertFalse((self.codex_home / "ohmycodex" / "preferences.json").exists())

    def test_invalid_existing_preference_fails_before_any_target_changes(self) -> None:
        preference = self.codex_home / "ohmycodex" / "preferences.json"
        preference.parent.mkdir(parents=True)
        preference.write_bytes(canonical({"schema_version": 1, "language": "fr"}))
        targets = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        before = {path: path.read_bytes() for path in targets}

        with self.assertRaisesRegex(ValueError, "language is unsupported"):
            apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertEqual({path: path.read_bytes() for path in targets}, before)
        self.assertEqual(
            json.loads(preference.read_text()),
            {"schema_version": 1, "language": "fr"},
        )

    def test_metadata_prompt_references_are_validated_before_writing(self) -> None:
        metadata_path = self.skills / "omc-alpha" / "agents" / "openai.yaml"
        metadata = json.loads(metadata_path.read_text())
        metadata["interface"]["default_prompt"] = "Use $omc-alpha-extra now."
        metadata_path.write_bytes(canonical(metadata))
        before = self.manifest.read_bytes()

        with self.assertRaisesRegex(ValueError, "must reference \\$omc-alpha"):
            apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertEqual(self.manifest.read_bytes(), before)
        self.assertFalse(
            (self.codex_home / "ohmycodex" / "preferences.json").exists()
        )

    def test_failure_on_nth_replace_rolls_back_every_target(self) -> None:
        targets = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        before = {path: path.read_bytes() for path in targets}
        real_replace = MODULE.os.replace
        committed_replacements = 0

        def fail_second_commit(source: object, destination: object) -> None:
            nonlocal committed_replacements
            source_path = Path(source)  # type: ignore[arg-type]
            if source_path.name.endswith(".stage"):
                committed_replacements += 1
                if committed_replacements == 2:
                    raise OSError("injected replacement failure")
            real_replace(source, destination)

        with patch.object(MODULE.os, "replace", side_effect=fail_second_commit):
            result = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertFalse(result.available)
        self.assertFalse(result.changed)
        self.assertEqual({path: path.read_bytes() for path in targets}, before)
        state_root = self.codex_home / "ohmycodex"
        self.assertFalse((state_root / "preferences.json").exists())
        self.assertFalse((state_root / ".locale-transaction.json").exists())
        leftovers = [
            path
            for path in self.root.rglob("*")
            if path.name.endswith((".stage", ".backup"))
        ]
        self.assertEqual(leftovers, [])

    def test_permission_failure_reports_unavailable_without_partial_changes(self) -> None:
        targets = [self.manifest] + [
            self.skills / name / "agents" / "openai.yaml" for name in self.skill_names
        ]
        before = {path: path.read_bytes() for path in targets}

        with patch.object(
            MODULE, "_write_new_file", side_effect=PermissionError("read-only fixture")
        ):
            result = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertFalse(result.available)
        self.assertIn("unavailable", result.message)
        self.assertEqual({path: path.read_bytes() for path in targets}, before)
        self.assertFalse(
            (self.codex_home / "ohmycodex" / "preferences.json").exists()
        )

    def test_interrupted_transaction_journal_is_recovered_before_new_switch(self) -> None:
        original = self.manifest.read_bytes()
        backup = self.manifest.parent / ".plugin.json.crash.backup"
        staged = self.manifest.parent / ".plugin.json.crash.stage"
        backup.write_bytes(original)
        staged.write_bytes(b"staged-but-not-committed\n")
        self.manifest.write_bytes(b"interrupted-invalid-target\n")
        state_root = self.codex_home / "ohmycodex"
        state_root.mkdir(parents=True)
        journal = state_root / ".locale-transaction.json"
        journal.write_bytes(
            canonical(
                {
                    "schema_version": 1,
                    "transaction_id": "crash-fixture",
                    "plugin_root": str(self.plugin.resolve()),
                    "codex_home": str(self.codex_home.resolve()),
                    "entries": [
                        {
                            "target": str(self.manifest.resolve()),
                            "staged": str(staged.resolve()),
                            "backup": str(backup.resolve()),
                            "existed": True,
                        }
                    ],
                }
            )
        )

        result = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertTrue(result.available)
        self.assertTrue(result.recovered)
        self.assertEqual(inspect_locale(self.plugin, self.codex_home)["materialized_locale"], "zh-CN")
        self.assertFalse(journal.exists())
        self.assertFalse(backup.exists())
        self.assertFalse(staged.exists())

    def test_failed_recovery_remains_retryable_on_next_invocation(self) -> None:
        targets = [
            self.manifest,
            self.skills / "omc-alpha" / "agents" / "openai.yaml",
        ]
        entries = []
        for index, target in enumerate(targets):
            backup = target.parent / f".{target.name}.retry-{index}.backup"
            staged = target.parent / f".{target.name}.retry-{index}.stage"
            backup.write_bytes(target.read_bytes())
            staged.write_bytes(b"orphaned stage\n")
            target.write_bytes(b"interrupted-invalid-target\n")
            entries.append(
                {
                    "target": str(target.resolve()),
                    "staged": str(staged.resolve()),
                    "backup": str(backup.resolve()),
                    "existed": True,
                }
            )
        state_root = self.codex_home / "ohmycodex"
        state_root.mkdir(parents=True)
        journal = state_root / ".locale-transaction.json"
        journal.write_bytes(
            canonical(
                {
                    "schema_version": 1,
                    "transaction_id": "retry-fixture",
                    "plugin_root": str(self.plugin.resolve()),
                    "codex_home": str(self.codex_home.resolve()),
                    "entries": entries,
                }
            )
        )
        real_restore = MODULE._restore_backup
        restore_calls = 0

        def fail_second_restore(backup: Path, target: Path) -> None:
            nonlocal restore_calls
            restore_calls += 1
            if restore_calls == 2:
                raise OSError("interrupted recovery")
            real_restore(backup, target)

        with patch.object(MODULE, "_restore_backup", side_effect=fail_second_restore):
            failed = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertFalse(failed.available)
        self.assertTrue(journal.exists())
        self.assertTrue(all(Path(entry["backup"]).exists() for entry in entries))

        recovered = apply_locale(self.plugin, self.codex_home, "zh-CN")

        self.assertTrue(recovered.available)
        self.assertTrue(recovered.recovered)
        self.assertFalse(journal.exists())
        self.assertEqual(inspect_locale(self.plugin, self.codex_home)["materialized_locale"], "zh-CN")

    def test_cli_json_success_requests_restart_or_new_task(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(MANAGER),
                "zh-CN",
                "--plugin-root",
                str(self.plugin),
                "--codex-home",
                str(self.codex_home),
                "--json",
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        payload = json.loads(completed.stdout)
        self.assertTrue(payload["available"])
        self.assertTrue(payload["restart_required"])
        self.assertIn("重启", payload["message"])
        self.assertIn("新任务", payload["message"])


class ActualPluginLocaleContractTests(unittest.TestCase):
    def test_catalogs_cover_exactly_all_nineteen_skills(self) -> None:
        catalogs = validate_catalogs(ACTUAL_PLUGIN)
        skill_names = {
            path.name
            for path in (ACTUAL_PLUGIN / "skills").iterdir()
            if (path / "SKILL.md").is_file()
        }

        self.assertEqual(len(skill_names), 19)
        for locale in ("en", "zh-CN"):
            self.assertEqual(set(catalogs[locale]["skills"]), skill_names)

    def test_checked_in_metadata_matches_english_catalog(self) -> None:
        status = inspect_locale(ACTUAL_PLUGIN, ROOT / ".nonexistent-codex-home")

        self.assertEqual(status["materialized_locale"], "en")
        self.assertTrue(status["consistent"])

    def test_all_nineteen_skills_load_the_language_policy(self) -> None:
        for skill in sorted((ACTUAL_PLUGIN / "skills").glob("omc-*/SKILL.md")):
            with self.subTest(skill=skill.parent.name):
                self.assertIn("language-policy.md", skill.read_text(encoding="utf-8"))

    def test_actual_plugin_round_trip_restores_canonical_english_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plugin = root / "ohmycodex"
            codex_home = root / "codex-home"
            shutil.copytree(ACTUAL_PLUGIN, plugin)
            targets = [plugin / ".codex-plugin" / "plugin.json"] + sorted(
                (plugin / "skills").glob("*/agents/openai.yaml")
            )
            before = {path.relative_to(plugin): path.read_bytes() for path in targets}

            chinese = apply_locale(plugin, codex_home, "zh-CN")
            restored = apply_locale(plugin, codex_home, "en")

            self.assertTrue(chinese.available)
            self.assertTrue(restored.available)
            self.assertEqual(
                {path.relative_to(plugin): path.read_bytes() for path in targets},
                before,
            )


if __name__ == "__main__":
    unittest.main()
