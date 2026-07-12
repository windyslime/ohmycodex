---
name: omc-init
description: Initialize `.ohmycodex` project state for an AI-assisted MVP. Use when starting OhMyCodex in a repository or when the user wants reusable project context, commands, constraints, decisions, and engineering records.
---

# Initialize OhMyCodex

Inspect the repository, existing guidance, package manifests, CI configuration, and Git status before writing. Create the workspace layout defined in `../omc-orchestrator/references/workspace-contract.md` without overwriting existing artifacts.

Populate `project.md` from repository evidence. Include only commands that exist in configuration or have been verified. Mark unknowns as questions; do not guess the stack, deployment system, or test command.

Create draft `decisions.md`, `technical-debt.md`, and release/plan/spec directories. Explain the created files and request confirmation before recording product or architectural decisions. If writes are unavailable, present the same structure inline and label it conversation-only.

Never modify application code, dependency manifests, permissions, or Git configuration during initialization.
