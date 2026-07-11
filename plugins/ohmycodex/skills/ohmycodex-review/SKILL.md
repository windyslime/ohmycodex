---
name: ohmycodex-review
description: Review AI-assisted changes against the active specification and engineering guardrails. Use when users request code review, PR review, diff review, implementation audit, release-readiness review, or maintainability feedback.
---

# Review Against the Contract

Read the active specification, architecture decisions, implementation evidence, and the requested diff or files. Review for correctness, scope compliance, contract consistency, module responsibility, resilience, observability, security-sensitive handling, tests, and rollback risk.

Report only actionable findings. For every finding, state severity, evidence, concrete consequence, and the smallest safe remediation. Distinguish required fixes from optional improvements. Do not edit code unless the user asks for fixes.

Write `.ohmycodex/plans/review.md` after review with reviewed scope, commands or evidence, findings, unresolved risks, and release recommendation. Do not claim approval when required checks or evidence are missing.
