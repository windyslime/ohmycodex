---
name: omc-architecture
description: Design a change-safe architecture for an approved MVP specification. Use when users need module boundaries, API or data contracts, storage decisions, implementation sequencing, resilience design, or a technical plan before coding.
---

# Design the Architecture

Read [the Language Policy](../omc-orchestrator/references/language-policy.md) before responding or writing OhMyCodex artifacts.

Inspect the existing repository before proposing changes. Read the approved MVP specification and preserve stable patterns unless they conflict with a concrete requirement.

For a cross-module architecture question with independent repository and documentation unknowns, use `omc-team` to run Explorer and Librarian in parallel. Consolidate their evidence before making architectural decisions; do not delegate writing.

Define focused modules with one responsibility each. Specify public contracts: inputs, outputs, nullability, events, loading/error states, persistence boundaries, and ownership. List files to create or modify, identify risky existing paths, and prefer extension over rewrites.

Address invalid input, empty data, partial responses, retry behavior, repeated actions, offline or slow requests, and observability without logging secrets. Include test seams and rollback-safe milestones.

After approval, write `.ohmycodex/plans/architecture.md` and any material decision to `decisions.md`. Do not implement code in this workflow.
