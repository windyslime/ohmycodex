---
name: omc-debt
description: Record and prioritize intentional technical debt in an AI-assisted project. Use when users accept a shortcut, defer cleanup, need a debt register, want to assess maintainability risk, or ask what to revisit before the next milestone.
---

# Record Technical Debt

Read the project profile and existing debt register. Record only deliberate trade-offs, not vague dissatisfaction. For each item capture location, current shortcut, reason accepted, consequence, risk level, owner, revisit trigger, and suggested next action.

Prioritize debt by likelihood and cost of failure, not by aesthetic preference. Link debt to relevant specification, decision, incident, review, or release artifact. Do not convert debt tracking into an unbounded backlog.

Update `.ohmycodex/technical-debt.md` after confirmation. Report the highest-leverage revisit item and state when leaving the debt in place is reasonable.
