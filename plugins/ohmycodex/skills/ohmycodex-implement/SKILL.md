---
name: ohmycodex-implement
description: Implement an approved OhMyCodex plan incrementally and safely. Use when users ask to build an approved feature, execute a technical plan, change application code, or continue a verified implementation milestone.
---

# Implement Safely

Read the project profile, approved specification, architecture plan, and current Git status. If no approved plan exists, route to `ohmycodex-architecture` instead of inventing scope.

Before editing, state files to change, stable behavior to preserve, commands to verify, and any required dependency or permission change. Ask for confirmation before adding a production dependency, changing deployment configuration, or taking an external action.

For a complex approved plan, use `ohmycodex-team` only for read-only support such as Explorer, Librarian, or QA. Wait for their summaries before editing. The implementer remains the sole code-writing agent for the milestone.

Implement the smallest coherent milestone. Add or update focused tests at the relevant seam, run the narrowest useful verification, then run the repository's declared checks when proportionate. Inspect changed files for missing imports, null paths, duplicated logic, and unhandled error states.

Record completed milestones, commands run, results, residual risks, and next work in `.ohmycodex/plans/implementation.md`. Commit only when the user asks or existing repository policy requires it.
