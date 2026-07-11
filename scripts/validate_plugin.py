#!/usr/bin/env python3
"""Validate OhMyCodex without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ohmycodex"
SKILLS = PLUGIN / "skills"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_SKILLS = {
    "ohmycodex-orchestrator",
    "ohmycodex-init",
    "ohmycodex-discover",
    "ohmycodex-spec",
    "ohmycodex-architecture",
    "ohmycodex-implement",
    "ohmycodex-qa",
    "ohmycodex-debug",
    "ohmycodex-refactor",
    "ohmycodex-review",
    "ohmycodex-release",
    "ohmycodex-debt",
}


def fail(message: str) -> None:
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"{path.relative_to(ROOT)} is not valid JSON: {error}")


def validate_manifest() -> None:
    manifest = read_json(MANIFEST)
    required = {"name", "version", "description", "author", "license", "skills", "interface"}
    missing = required - manifest.keys()
    if missing:
        fail(f"plugin manifest is missing: {', '.join(sorted(missing))}")
    if manifest["name"] != "ohmycodex" or manifest["skills"] != "./skills/":
        fail("plugin manifest must identify ohmycodex and ./skills/")
    if manifest["version"] != "0.1.0":
        fail("plugin manifest must use the planned 0.1.0 release version")
    if manifest["license"] != "MIT":
        fail("plugin manifest must declare MIT")
    interface = manifest["interface"]
    for key in ("displayName", "shortDescription", "longDescription", "developerName", "category", "defaultPrompt"):
        if not interface.get(key):
            fail(f"plugin interface is missing {key}")
    if len(interface["defaultPrompt"]) != 3:
        fail("plugin interface must provide exactly three starter prompts")
    forbidden = {"apps", "mcpServers", "hooks"} & manifest.keys()
    if forbidden:
        fail(f"skills-only plugin must not declare: {', '.join(sorted(forbidden))}")


def validate_marketplace() -> None:
    marketplace = read_json(MARKETPLACE)
    if marketplace.get("name") != "ohmycodex":
        fail("marketplace name must be ohmycodex")
    entries = marketplace.get("plugins", [])
    if len(entries) != 1:
        fail("marketplace must contain exactly one plugin entry")
    entry = entries[0]
    if entry.get("name") != "ohmycodex" or entry.get("source", {}).get("path") != "./plugins/ohmycodex":
        fail("marketplace must point at ./plugins/ohmycodex")
    policy = entry.get("policy", {})
    if policy.get("installation") != "AVAILABLE" or policy.get("authentication") != "ON_INSTALL":
        fail("marketplace policy must be AVAILABLE and ON_INSTALL")


def frontmatter(path: Path) -> tuple[str, str]:
    text = path.read_text(encoding="utf-8")
    if "TODO" in text or "[TODO:" in text:
        fail(f"{path.relative_to(ROOT)} contains a placeholder")
    match = re.match(r"^---\nname: ([^\n]+)\ndescription: ([^\n]+)\n---\n", text)
    if not match:
        fail(f"{path.relative_to(ROOT)} must start with name and description frontmatter")
    return match.group(1).strip(), match.group(2).strip()


def validate_skills() -> None:
    discovered = {path.name for path in SKILLS.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()}
    if discovered != REQUIRED_SKILLS:
        missing = REQUIRED_SKILLS - discovered
        extra = discovered - REQUIRED_SKILLS
        fail(f"skill set mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    for skill_name in sorted(REQUIRED_SKILLS):
        directory = SKILLS / skill_name
        name, description = frontmatter(directory / "SKILL.md")
        if name != skill_name or not NAME_RE.fullmatch(name):
            fail(f"{skill_name} must match its valid folder name")
        if len(description) > 240:
            fail(f"{skill_name} description must stay concise for skill discovery")
        metadata = directory / "agents" / "openai.yaml"
        if not metadata.is_file():
            fail(f"{skill_name} is missing agents/openai.yaml")
        if f"${skill_name}" not in metadata.read_text(encoding="utf-8"):
            fail(f"{skill_name} UI metadata must include an explicit default prompt")


def main() -> None:
    for path in (MANIFEST, MARKETPLACE, SKILLS):
        if not path.exists():
            fail(f"required path is missing: {path.relative_to(ROOT)}")
    validate_manifest()
    validate_marketplace()
    validate_skills()
    print("OhMyCodex validation passed.")


if __name__ == "__main__":
    main()
