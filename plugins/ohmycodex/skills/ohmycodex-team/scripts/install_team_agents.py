#!/usr/bin/env python3
"""Install OhMyCodex Team agent templates without overwriting project files."""

from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path


AGENT_FILENAMES = (
    "omc-explorer.toml",
    "omc-librarian.toml",
    "omc-qa.toml",
    "omc-architect.toml",
    "omc-implementer.toml",
    "omc-debugger.toml",
    "omc-reviewer.toml",
    "omc-fallback.toml",
)


@dataclass
class InstallResult:
    created: list[str]
    skipped: list[str]
    dry_run: bool
    config_updated: bool


def template_directory() -> Path:
    return Path(__file__).resolve().parents[1] / "assets" / "agents"


def install_templates(target: Path, dry_run: bool = False) -> InstallResult:
    target = target.resolve()
    source = template_directory()
    missing = [name for name in AGENT_FILENAMES if not (source / name).is_file()]
    if missing:
        raise FileNotFoundError(f"Missing bundled agent templates: {', '.join(missing)}")

    agents_directory = target / ".codex" / "agents"
    config_path = target / ".codex" / "config.toml"
    created: list[str] = []
    skipped: list[str] = []
    config_updated = False

    for filename in AGENT_FILENAMES:
        destination = agents_directory / filename
        if destination.exists():
            skipped.append(filename)
            continue
        created.append(filename)
        if not dry_run:
            agents_directory.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / filename, destination)

    if config_path.exists():
        existing = config_path.read_text(encoding="utf-8")
        if "[agents]" in existing:
            skipped.append("config.toml [agents]")
        else:
            config_updated = True
            if not dry_run:
                config_path.parent.mkdir(parents=True, exist_ok=True)
                separator = "" if not existing or existing.endswith("\n") else "\n"
                config_path.write_text(
                    f"{existing}{separator}[agents]\nmax_threads = 4\nmax_depth = 1\n",
                    encoding="utf-8",
                )
    else:
        config_updated = True
        if not dry_run:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text("[agents]\nmax_threads = 4\nmax_depth = 1\n", encoding="utf-8")

    return InstallResult(
        created=created,
        skipped=skipped,
        dry_run=dry_run,
        config_updated=config_updated,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", nargs="?", default=".", type=Path, help="Target repository directory")
    parser.add_argument("--dry-run", action="store_true", help="Report changes without writing files")
    args = parser.parse_args()
    result = install_templates(args.target, dry_run=args.dry_run)
    mode = "Would install" if result.dry_run else "Installed"
    print(f"{mode}: {', '.join(result.created) or 'nothing'}")
    if result.skipped:
        print(f"Preserved: {', '.join(result.skipped)}")
    if result.config_updated:
        print("Added missing [agents] defaults.")


if __name__ == "__main__":
    main()
