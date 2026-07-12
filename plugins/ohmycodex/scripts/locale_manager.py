#!/usr/bin/env python3
"""Validate and transactionally materialize OhMyCodex locale metadata."""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
import tempfile
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


SUPPORTED_LOCALES = ("en", "zh-CN")
CATALOG_FIELDS = {"schema_version", "locale", "manifest", "skills"}
MANIFEST_FIELDS = {
    "description",
    "displayName",
    "shortDescription",
    "longDescription",
    "defaultPrompt",
}
SKILL_FIELDS = {"display_name", "short_description", "default_prompt"}
PREFERENCE_FIELDS = {"schema_version", "language"}
JOURNAL_NAME = ".locale-transaction.json"
SKILL_REFERENCE_RE = re.compile(r"\$([a-z0-9]+(?:-[a-z0-9]+)*)")


@dataclass(frozen=True)
class LocaleResult:
    locale: str
    available: bool
    changed: bool
    recovered: bool
    restart_required: bool
    message: str

    def as_dict(self) -> dict[str, object]:
        return {
            "locale": self.locale,
            "available": self.available,
            "changed": self.changed,
            "recovered": self.recovered,
            "restart_required": self.restart_required,
            "message": self.message,
        }


def _object(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{label} must be an object")
    return value


def _exact_keys(value: Mapping[str, object], expected: set[str], label: str) -> None:
    missing = expected - set(value)
    unknown = set(value) - expected
    if missing:
        raise ValueError(f"{label} is missing fields: {', '.join(sorted(missing))}")
    if unknown:
        raise ValueError(f"{label} has unknown fields: {', '.join(sorted(unknown))}")


def _nonempty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _read_json(path: Path, label: str) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ValueError(f"invalid {label}: {path}: {error}") from error
    return dict(_object(value, label))


def _skill_names(plugin_root: Path) -> set[str]:
    skills_root = plugin_root / "skills"
    try:
        return {
            path.name
            for path in skills_root.iterdir()
            if path.is_dir() and (path / "SKILL.md").is_file()
        }
    except OSError as error:
        raise ValueError(f"cannot inspect Skill directories: {error}") from error


def _validate_catalog(
    catalog: Mapping[str, object], locale: str, skill_names: set[str]
) -> None:
    _exact_keys(catalog, CATALOG_FIELDS, f"{locale} catalog")
    if catalog["schema_version"] != 1 or isinstance(catalog["schema_version"], bool):
        raise ValueError(f"{locale} catalog schema_version must be 1")
    if catalog["locale"] != locale:
        raise ValueError(f"{locale} catalog locale must be {locale}")

    manifest = _object(catalog["manifest"], f"{locale} manifest catalog")
    _exact_keys(manifest, MANIFEST_FIELDS, f"{locale} manifest catalog")
    for field in MANIFEST_FIELDS - {"defaultPrompt"}:
        _nonempty_string(manifest[field], f"{locale} manifest.{field}")
    prompts = manifest["defaultPrompt"]
    if not isinstance(prompts, list) or len(prompts) != 3:
        raise ValueError(f"{locale} manifest.defaultPrompt must contain exactly 3 prompts")
    for index, prompt in enumerate(prompts):
        prompt_text = _nonempty_string(
            prompt, f"{locale} manifest.defaultPrompt[{index}]"
        )
        references = set(SKILL_REFERENCE_RE.findall(prompt_text))
        if not references or not references <= skill_names:
            raise ValueError(
                f"{locale} manifest.defaultPrompt[{index}] must reference a matching "
                "$omc-* Skill"
            )

    skills = _object(catalog["skills"], f"{locale} skills catalog")
    if set(skills) != skill_names:
        missing = skill_names - set(skills)
        unknown = set(skills) - skill_names
        detail = []
        if missing:
            detail.append(f"missing {', '.join(sorted(missing))}")
        if unknown:
            detail.append(f"unknown {', '.join(sorted(unknown))}")
        raise ValueError(f"{locale} skills catalog coverage mismatch: {'; '.join(detail)}")
    for name, raw_metadata in skills.items():
        metadata = _object(raw_metadata, f"{locale} skills.{name}")
        _exact_keys(metadata, SKILL_FIELDS, f"{locale} skills.{name}")
        for field in SKILL_FIELDS:
            _nonempty_string(metadata[field], f"{locale} skills.{name}.{field}")
        references = set(SKILL_REFERENCE_RE.findall(str(metadata["default_prompt"])))
        if name not in references or not references <= skill_names:
            raise ValueError(
                f"{locale} skills.{name}.default_prompt must reference ${name}"
            )


def validate_catalogs(plugin_root: str | Path) -> dict[str, dict[str, object]]:
    """Return validated catalogs, rejecting any coverage or schema drift."""

    root = Path(plugin_root).resolve()
    skill_names = _skill_names(root)
    locales_root = root / "assets" / "locales"
    try:
        actual_catalog_files = {
            path.name for path in locales_root.iterdir() if path.suffix == ".json"
        }
    except OSError as error:
        raise ValueError(f"cannot inspect locale catalogs: {error}") from error
    expected_catalog_files = {f"{locale}.json" for locale in SUPPORTED_LOCALES}
    unsupported = actual_catalog_files - expected_catalog_files
    if unsupported:
        raise ValueError(
            f"unsupported locale catalog: {', '.join(sorted(unsupported))}"
        )
    catalogs: dict[str, dict[str, object]] = {}
    for locale in SUPPORTED_LOCALES:
        catalog = _read_json(
            locales_root / f"{locale}.json", f"{locale} catalog"
        )
        _validate_catalog(catalog, locale, skill_names)
        catalogs[locale] = catalog

    if set(catalogs["en"]["skills"]) != set(catalogs["zh-CN"]["skills"]):
        raise ValueError("locale catalogs must contain identical Skill keys")
    return copy.deepcopy(catalogs)


def _metadata_targets(root: Path, skill_names: set[str]) -> tuple[Path, dict[str, Path]]:
    manifest_path = root / ".codex-plugin" / "plugin.json"
    skill_paths = {
        name: root / "skills" / name / "agents" / "openai.yaml"
        for name in sorted(skill_names)
    }
    return manifest_path, skill_paths


def _validate_materialized(
    root: Path, skill_names: set[str]
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    manifest_path, skill_paths = _metadata_targets(root, skill_names)
    manifest = _read_json(manifest_path, "plugin manifest")
    _nonempty_string(manifest.get("description"), "plugin manifest.description")
    interface = _object(manifest.get("interface"), "plugin manifest.interface")
    for field in MANIFEST_FIELDS - {"description"}:
        if field == "defaultPrompt":
            prompts = interface.get(field)
            if not isinstance(prompts, list) or len(prompts) != 3:
                raise ValueError(
                    "plugin manifest.interface.defaultPrompt must contain exactly 3 prompts"
                )
            for index, prompt in enumerate(prompts):
                prompt_text = _nonempty_string(
                    prompt, f"plugin manifest.interface.defaultPrompt[{index}]"
                )
                references = set(SKILL_REFERENCE_RE.findall(prompt_text))
                if not references or not references <= skill_names:
                    raise ValueError(
                        "plugin manifest.interface.defaultPrompt must reference only "
                        "matching $omc-* Skills"
                    )
        else:
            _nonempty_string(
                interface.get(field), f"plugin manifest.interface.{field}"
            )

    metadata_by_skill: dict[str, dict[str, object]] = {}
    for name, path in skill_paths.items():
        metadata = _read_json(path, f"{name} metadata")
        skill_interface = _object(metadata.get("interface"), f"{name} metadata.interface")
        for field in SKILL_FIELDS:
            _nonempty_string(
                skill_interface.get(field), f"{name} metadata.interface.{field}"
            )
        prompt = str(skill_interface["default_prompt"])
        references = set(SKILL_REFERENCE_RE.findall(prompt))
        if name not in references or not references <= skill_names:
            raise ValueError(f"{name} metadata default_prompt must reference ${name}")
        metadata_by_skill[name] = metadata
    return manifest, metadata_by_skill


def _translatable_snapshot(
    manifest: Mapping[str, object], skills: Mapping[str, Mapping[str, object]]
) -> dict[str, object]:
    interface = _object(manifest["interface"], "plugin manifest.interface")
    manifest_snapshot = {"description": manifest["description"]}
    manifest_snapshot.update(
        {field: copy.deepcopy(interface[field]) for field in MANIFEST_FIELDS - {"description"}}
    )
    skill_snapshot: dict[str, object] = {}
    for name, metadata in skills.items():
        skill_interface = _object(metadata["interface"], f"{name} metadata.interface")
        skill_snapshot[name] = {
            field: copy.deepcopy(skill_interface[field]) for field in SKILL_FIELDS
        }
    return {"manifest": manifest_snapshot, "skills": skill_snapshot}


def _catalog_snapshot(catalog: Mapping[str, object]) -> dict[str, object]:
    return {
        "manifest": copy.deepcopy(catalog["manifest"]),
        "skills": copy.deepcopy(catalog["skills"]),
    }


def _read_preference(codex_home: Path) -> str | None:
    path = codex_home / "ohmycodex" / "preferences.json"
    if not path.exists():
        return None
    preference = _read_json(path, "OhMyCodex preference")
    _exact_keys(preference, PREFERENCE_FIELDS, "OhMyCodex preference")
    if preference["schema_version"] != 1 or isinstance(
        preference["schema_version"], bool
    ):
        raise ValueError("OhMyCodex preference schema_version must be 1")
    language = preference["language"]
    if language not in SUPPORTED_LOCALES:
        raise ValueError("OhMyCodex preference language is unsupported")
    assert isinstance(language, str)
    return language


def inspect_locale(plugin_root: str | Path, codex_home: str | Path) -> dict[str, object]:
    """Inspect saved and materialized locale state without modifying either root."""

    root = Path(plugin_root).resolve()
    home = Path(codex_home).resolve()
    catalogs = validate_catalogs(root)
    skill_names = set(catalogs["en"]["skills"])
    manifest, skills = _validate_materialized(root, skill_names)
    actual = _translatable_snapshot(manifest, skills)
    matches = [
        locale
        for locale in SUPPORTED_LOCALES
        if actual == _catalog_snapshot(catalogs[locale])
    ]
    materialized = matches[0] if len(matches) == 1 else "unknown"
    saved = _read_preference(home)
    effective = saved or "en"
    consistent = materialized == effective
    if consistent and saved is None:
        recommendation = "none"
        restart_recommended = False
    elif consistent:
        recommendation = "restart_codex_or_start_new_task"
        restart_recommended = True
    else:
        command = "$omc-cn" if effective == "zh-CN" else "$omc-en"
        recommendation = f"rerun_{command}_then_restart_codex_or_start_new_task"
        restart_recommended = False
    return {
        "schema_version": 1,
        "saved_preference": saved,
        "effective_preference": effective,
        "materialized_locale": materialized,
        "consistent": consistent,
        "restart_or_new_task_recommended": restart_recommended,
        "recommendation": recommendation,
    }


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def _materialize(
    root: Path,
    home: Path,
    catalog: Mapping[str, object],
    manifest: dict[str, object],
    metadata_by_skill: Mapping[str, dict[str, object]],
) -> dict[Path, bytes]:
    new_manifest = copy.deepcopy(manifest)
    manifest_catalog = _object(catalog["manifest"], "manifest catalog")
    new_manifest["description"] = manifest_catalog["description"]
    manifest_interface = _object(new_manifest["interface"], "plugin manifest.interface")
    for field in MANIFEST_FIELDS - {"description"}:
        manifest_interface[field] = copy.deepcopy(manifest_catalog[field])

    manifest_path, skill_paths = _metadata_targets(root, set(metadata_by_skill))
    payloads: dict[Path, bytes] = {manifest_path: _canonical_json(new_manifest)}
    skill_catalog = _object(catalog["skills"], "skills catalog")
    for name, metadata in metadata_by_skill.items():
        new_metadata = copy.deepcopy(metadata)
        interface = _object(new_metadata["interface"], f"{name} metadata.interface")
        translated = _object(skill_catalog[name], f"skills catalog.{name}")
        for field in SKILL_FIELDS:
            interface[field] = copy.deepcopy(translated[field])
        payloads[skill_paths[name]] = _canonical_json(new_metadata)

    preference_path = home / "ohmycodex" / "preferences.json"
    payloads[preference_path] = _canonical_json(
        {"schema_version": 1, "language": catalog["locale"]}
    )
    return payloads


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_new_file(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(_canonical_json(value))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _journal_path(home: Path) -> Path:
    return home / "ohmycodex" / JOURNAL_NAME


def _safe_transaction_path(path: Path, root: Path, label: str) -> None:
    resolved = path.resolve(strict=False)
    if not resolved.is_relative_to(root):
        raise ValueError(f"transaction {label} escapes its owned root")


def _validate_journal(
    value: Mapping[str, object], root: Path, home: Path
) -> list[dict[str, object]]:
    _exact_keys(
        value,
        {"schema_version", "transaction_id", "plugin_root", "codex_home", "entries"},
        "locale transaction journal",
    )
    if value["schema_version"] != 1 or isinstance(value["schema_version"], bool):
        raise ValueError("locale transaction journal schema_version must be 1")
    _nonempty_string(value["transaction_id"], "transaction_id")
    if value["plugin_root"] != str(root) or value["codex_home"] != str(home):
        raise ValueError("locale transaction journal belongs to different roots")
    entries = value["entries"]
    if not isinstance(entries, list) or not entries:
        raise ValueError("locale transaction journal entries must be a non-empty list")
    validated: list[dict[str, object]] = []
    seen_targets: set[Path] = set()
    for index, raw_entry in enumerate(entries):
        entry = _object(raw_entry, f"journal entry {index}")
        _exact_keys(entry, {"target", "staged", "backup", "existed"}, f"journal entry {index}")
        target = Path(_nonempty_string(entry["target"], f"journal entry {index}.target"))
        staged = Path(_nonempty_string(entry["staged"], f"journal entry {index}.staged"))
        backup_value = entry["backup"]
        if backup_value is not None:
            backup = Path(
                _nonempty_string(backup_value, f"journal entry {index}.backup")
            )
        else:
            backup = None
        if type(entry["existed"]) is not bool:
            raise ValueError(f"journal entry {index}.existed must be a boolean")
        existed = bool(entry["existed"])
        owned_root = root if target.is_relative_to(root) else home
        _safe_transaction_path(target, owned_root, "target")
        _safe_transaction_path(staged, target.parent.resolve(), "staged path")
        if backup is not None:
            _safe_transaction_path(backup, target.parent.resolve(), "backup path")
        if target in seen_targets:
            raise ValueError("locale transaction journal contains duplicate targets")
        if existed != (backup is not None):
            raise ValueError("journal backup must match whether target existed")
        seen_targets.add(target)
        validated.append(
            {
                "target": target,
                "staged": staged,
                "backup": backup,
                "existed": existed,
            }
        )
    return validated


def _cleanup_entry_files(
    entries: list[dict[str, object]], *, ignore_errors: bool = False
) -> None:
    for entry in entries:
        staged = entry["staged"]
        backup = entry["backup"]
        assert isinstance(staged, Path)
        for path in (staged, backup):
            if not isinstance(path, Path):
                continue
            try:
                path.unlink(missing_ok=True)
            except OSError:
                if not ignore_errors:
                    raise


def _restore_backup(backup: Path, target: Path) -> None:
    temporary = target.parent / f".{target.name}.{uuid.uuid4().hex}.recover"
    _write_new_file(temporary, backup.read_bytes())
    try:
        os.replace(temporary, target)
        _fsync_directory(target.parent)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _recover_transaction(root: Path, home: Path) -> bool:
    journal_path = _journal_path(home)
    if not journal_path.exists():
        return False
    journal = _read_json(journal_path, "locale transaction journal")
    entries = _validate_journal(journal, root, home)
    for entry in reversed(entries):
        target = entry["target"]
        backup = entry["backup"]
        existed = entry["existed"]
        assert isinstance(target, Path)
        if existed:
            if not isinstance(backup, Path) or not backup.is_file():
                raise OSError(f"cannot recover missing locale backup for {target}")
            _restore_backup(backup, target)
        else:
            target.unlink(missing_ok=True)
            _fsync_directory(target.parent)
    journal_path.unlink()
    _fsync_directory(journal_path.parent)
    _cleanup_entry_files(entries, ignore_errors=True)
    return True


def _stage_transaction(
    root: Path, home: Path, payloads: Mapping[Path, bytes]
) -> tuple[Path, list[dict[str, object]]]:
    transaction_id = uuid.uuid4().hex
    entries: list[dict[str, object]] = []
    journal_path = _journal_path(home)
    journal_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        for index, (target, payload) in enumerate(payloads.items()):
            target.parent.mkdir(parents=True, exist_ok=True)
            owned_root = root if target.is_relative_to(root) else home
            _safe_transaction_path(target, owned_root, "target")
            if target.is_symlink():
                raise ValueError(f"locale target must not be a symlink: {target}")
            staged = target.parent / f".{target.name}.{transaction_id}.{index}.stage"
            backup = (
                target.parent / f".{target.name}.{transaction_id}.{index}.backup"
                if target.exists()
                else None
            )
            _write_new_file(staged, payload)
            entries.append(
                {
                    "target": target,
                    "staged": staged,
                    "backup": backup,
                    "existed": target.exists(),
                }
            )
            if backup is not None:
                _write_new_file(backup, target.read_bytes())
        serialized_entries = [
            {
                "target": str(entry["target"]),
                "staged": str(entry["staged"]),
                "backup": str(entry["backup"]) if entry["backup"] is not None else None,
                "existed": entry["existed"],
            }
            for entry in entries
        ]
        _atomic_json(
            journal_path,
            {
                "schema_version": 1,
                "transaction_id": transaction_id,
                "plugin_root": str(root),
                "codex_home": str(home),
                "entries": serialized_entries,
            },
        )
        return journal_path, entries
    except BaseException:
        _cleanup_entry_files(entries)
        raise


def _commit_transaction(root: Path, home: Path, payloads: Mapping[Path, bytes]) -> None:
    journal_path, entries = _stage_transaction(root, home, payloads)
    try:
        for entry in entries:
            staged = entry["staged"]
            target = entry["target"]
            assert isinstance(staged, Path) and isinstance(target, Path)
            os.replace(staged, target)
            _fsync_directory(target.parent)
    except BaseException:
        _recover_transaction(root, home)
        raise
    journal_path.unlink()
    _fsync_directory(journal_path.parent)
    _cleanup_entry_files(entries, ignore_errors=True)


def apply_locale(
    plugin_root: str | Path, codex_home: str | Path, locale: str
) -> LocaleResult:
    """Atomically apply a supported locale to all plugin-owned metadata."""

    if locale not in SUPPORTED_LOCALES:
        raise ValueError(f"unsupported locale: {locale}")
    root = Path(plugin_root).resolve()
    home = Path(codex_home).resolve()
    try:
        recovered = _recover_transaction(root, home)
        catalogs = validate_catalogs(root)
        skill_names = set(catalogs["en"]["skills"])
        manifest, skills = _validate_materialized(root, skill_names)
        _read_preference(home)
        payloads = _materialize(root, home, catalogs[locale], manifest, skills)
        changed = any(
            not target.is_file() or target.read_bytes() != payload
            for target, payload in payloads.items()
        )
        if changed:
            _commit_transaction(root, home, payloads)
    except (OSError, PermissionError) as error:
        message = (
            "Global OhMyCodex language switching is unavailable: "
            f"{type(error).__name__}: {error}"
        )
        return LocaleResult(
            locale=locale,
            available=False,
            changed=False,
            recovered=False,
            restart_required=False,
            message=message,
        )

    if locale == "zh-CN":
        message = "OhMyCodex 已切换为简体中文。请重启 Codex 或开始一个新任务。"
    else:
        message = (
            "OhMyCodex is now using English. Restart Codex or start a new task."
        )
    return LocaleResult(
        locale=locale,
        available=True,
        changed=changed,
        recovered=recovered,
        restart_required=True,
        message=message,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("locale", choices=SUPPORTED_LOCALES)
    parser.add_argument("--plugin-root", required=True, type=Path)
    parser.add_argument("--codex-home", required=True, type=Path)
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    result = apply_locale(args.plugin_root, args.codex_home, args.locale)
    if args.json_output:
        print(json.dumps(result.as_dict(), sort_keys=True, ensure_ascii=False))
    else:
        print(result.message)
    return 0 if result.available else 1


if __name__ == "__main__":
    sys.exit(main())
