---
name: omc-qa
description: Verify an AI-assisted MVP with focused tests and acceptance evidence. Use when users ask to test, validate, check quality, run build or lint commands, assess edge cases, or confirm a feature is ready for review.
---

# Verify the Work

Read the MVP specification, architecture plan, and implementation record. Derive verification from acceptance criteria rather than only from changed lines.

For broad independent test-gap analysis, use `omc-team` to delegate read-only QA and Explorer work. Wait for both results before selecting checks; retain one parent-owned verification record.

Run available targeted tests first, then type checks, lint, build, or end-to-end checks recorded in `project.md` when relevant. Check happy path, empty input, invalid input, loading state, error or timeout, repeated action, and regression risk according to the feature.

If a command is unavailable, report the gap and perform a bounded static inspection; do not claim equivalent runtime coverage. Record exact commands, results, skipped checks, defects, and release impact in `.ohmycodex/plans/verification.md`. Route implementation failures to `omc-debug`.
