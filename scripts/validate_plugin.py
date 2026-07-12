#!/usr/bin/env python3
"""Validate OhMyCodex without third-party dependencies."""

from __future__ import annotations

import json
import re
import sys
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "ohmycodex"
SKILLS = PLUGIN / "skills"
MANIFEST = PLUGIN / ".codex-plugin" / "plugin.json"
MARKETPLACE = ROOT / ".agents" / "plugins" / "marketplace.json"
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REQUIRED_SKILLS = {
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
TEAM_AGENTS = PLUGIN / "skills" / "omc-team" / "assets" / "agents"
TEAM_POLICY = {
    "omc-explorer.toml": ("omc-explorer", "gpt-5.6-luna", "low", "read-only"),
    "omc-librarian.toml": ("omc-librarian", "gpt-5.6-luna", "medium", "read-only"),
    "omc-qa.toml": ("omc-qa", "gpt-5.6-luna", "medium", "read-only"),
    "omc-architect.toml": ("omc-architect", "gpt-5.6", "xhigh", "read-only"),
    "omc-implementer.toml": ("omc-implementer", "gpt-5.6-terra", "high", "workspace-write"),
    "omc-debugger.toml": ("omc-debugger", "gpt-5.6-terra", "high", "read-only"),
    "omc-reviewer.toml": ("omc-reviewer", "gpt-5.6", "high", "read-only"),
    "omc-fallback.toml": ("omc-fallback", "gpt-5.5", "high", None),
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
    version, separator, metadata = manifest["version"].partition("+")
    if version != "0.3.0":
        fail("plugin manifest must use the planned 0.3.0 release version")
    if separator and (not metadata.startswith("codex.") or "+" in metadata):
        fail("plugin manifest may use only one +codex.* cachebuster suffix")
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
        metadata_path = directory / "agents" / "openai.yaml"
        if not metadata_path.is_file():
            fail(f"{skill_name} is missing agents/openai.yaml")
        metadata = read_json(metadata_path)
        interface = metadata.get("interface", {})
        if f"${skill_name}" not in interface.get("default_prompt", ""):
            fail(f"{skill_name} UI metadata must include an explicit default prompt")
        if metadata.get("policy", {}).get("allow_implicit_invocation") is not True:
            fail(f"{skill_name} must preserve implicit lifecycle invocation")


def validate_team_agents() -> None:
    discovered = {path.name for path in TEAM_AGENTS.glob("*.toml")}
    expected = set(TEAM_POLICY)
    if discovered != expected:
        fail(f"Team template mismatch; missing={sorted(expected - discovered)}, extra={sorted(discovered - expected)}")

    names: set[str] = set()
    for filename, (name, model, effort, sandbox) in TEAM_POLICY.items():
        path = TEAM_AGENTS / filename
        try:
            agent = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError) as error:
            fail(f"{path.relative_to(ROOT)} is not valid TOML: {error}")
        if agent.get("name") != name or agent.get("model") != model:
            fail(f"{filename} must use {name} with {model}")
        if agent.get("model_reasoning_effort") != effort:
            fail(f"{filename} must use {effort} reasoning")
        if sandbox is None:
            if "sandbox_mode" in agent:
                fail(f"{filename} must inherit the parent sandbox policy")
        elif agent.get("sandbox_mode") != sandbox:
            fail(f"{filename} must use {sandbox} sandbox mode")
        if not agent.get("description") or not agent.get("developer_instructions"):
            fail(f"{filename} must include description and developer instructions")
        if name in names:
            fail(f"Team agent name is duplicated: {name}")
        names.add(name)
        if "gpt-5.4" in model:
            fail(f"{filename} must not use a GPT-5.4 model")


def main() -> None:
    for path in (MANIFEST, MARKETPLACE, SKILLS, TEAM_AGENTS):
        if not path.exists():
            fail(f"required path is missing: {path.relative_to(ROOT)}")
    validate_manifest()
    validate_marketplace()
    validate_skills()
    validate_team_agents()
    print("OhMyCodex validation passed.")


if __name__ == "__main__":
    main()
