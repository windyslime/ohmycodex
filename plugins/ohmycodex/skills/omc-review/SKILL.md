---
name: omc-review
description: Review AI-assisted changes against the active specification and engineering guardrails. Use when users request code review, PR review, diff review, implementation audit, release-readiness review, or maintainability feedback.
---

# Review Against the Contract

Read [the Language Policy](../omc-orchestrator/references/language-policy.md) before responding or writing OhMyCodex artifacts.

Read the active specification, architecture decisions, implementation evidence, and the requested diff or files. Review for correctness, scope compliance, contract consistency, module responsibility, resilience, observability, security-sensitive handling, tests, and rollback risk.

For a broad diff with independent code-path mapping and risk review, use `omc-team` to run Explorer and Reviewer read-only in parallel. The parent consolidates findings and never asks review workers to edit code.

Report only actionable findings. For every finding, state severity, evidence, concrete consequence, and the smallest safe remediation. Distinguish required fixes from optional improvements. Do not edit code unless the user asks for fixes.

Write `.ohmycodex/plans/review.md` after review with reviewed scope, commands or evidence, findings, unresolved risks, and release recommendation. Do not claim approval when required checks or evidence are missing.
