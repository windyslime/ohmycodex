---
name: omc-spec
description: Define a scoped MVP specification with acceptance criteria and non-goals. Use when a product idea needs a buildable feature brief, user flows, data entities, error states, or a clear implementation boundary.
---

# Specify the MVP

Read the discovery brief and project profile. Convert approved goals into one primary user flow, explicit in-scope behavior, non-goals, acceptance criteria, domain entities, state transitions, loading/error/empty states, and compatibility constraints.

Resolve ambiguities that would change user-visible behavior. Keep the first version small: defer user systems, analytics, integrations, and abstractions unless they are essential to the primary flow.

After user approval, write `.ohmycodex/specs/mvp.md`. Mark unknown integrations or policy decisions as blockers instead of inventing data or APIs. Hand off technical choices to `omc-architecture`.
