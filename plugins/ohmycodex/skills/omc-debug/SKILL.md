---
name: omc-debug
description: Diagnose bugs and regressions with evidence before changing code. Use when a feature is broken, a command fails, behavior is unexpected, performance regresses, or users ask to debug or find root cause.
---

# Diagnose Before Fixing

Read [the Language Policy](../omc-orchestrator/references/language-policy.md) before responding or writing OhMyCodex artifacts.

Read the project profile, relevant specification, recent changes, logs, error output, and reproducible steps. Establish the observed behavior, expected behavior, affected scope, and smallest reliable reproduction.

For intermittent or multi-module failures, use `omc-team` to parallelize Explorer and QA evidence gathering. Consolidate competing hypotheses before assigning a debugger or implementer; never run parallel repair agents.

Form competing hypotheses and gather discriminating evidence with narrow tests, traces, or static inspection. Do not edit application code until the most likely root cause is supported by evidence. Separate root cause from correlated symptoms.

After user-approved remediation, add a regression test or explicit reason one is infeasible. Record reproduction, evidence, root cause, fix boundary, test result, and residual risk in `.ohmycodex/plans/diagnosis.md`.
