---
name: ohmycodex-refactor
description: Refactor AI-generated code without changing intended behavior. Use when users ask to simplify code, reduce duplication, split large files, clarify module boundaries, improve maintainability, or make a codebase safer to change.
---

# Refactor in Small Steps

Inspect existing behavior, tests, public contracts, and Git status. State the behavior invariant and the concrete design problem before proposing a refactor. Reject cosmetic churn and premature abstractions.

Choose the smallest independently verifiable step: extract a focused unit, centralize real duplication, clarify a boundary, or remove an obsolete path. Preserve public APIs unless the user explicitly approves a compatibility change.

Run relevant tests before and after each step. Record the invariant, files changed, validation evidence, deferred cleanup, and rollback point in `.ohmycodex/plans/refactor.md`. Add a debt record when a larger structural issue remains intentionally deferred.
