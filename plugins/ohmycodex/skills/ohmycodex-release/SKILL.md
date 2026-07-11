---
name: ohmycodex-release
description: Prepare a safe release for an AI-assisted project. Use when users ask to ship, publish, tag, deploy, create release notes, determine go or no-go, define rollback, or verify release readiness.
---

# Prepare the Release

Read the project profile, approved specification, verification evidence, review record, open debt, and current Git status. Confirm the intended version, release scope, target environment, owner, and rollback authority.

Build a checklist covering acceptance evidence, automated checks, migration or configuration changes, compatibility, monitoring or logs, known risks, rollback steps, and user-visible release notes. Give a clear `go`, `no-go`, or `go with recorded risk` result with evidence.

Write `.ohmycodex/releases/checklist.md` before any tag, deploy, push, or public publication. Treat all external release actions as user-controlled: request confirmation immediately before performing them and never fabricate successful deployment or publication.
