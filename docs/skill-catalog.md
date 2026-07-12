# Skill catalog

English | [简体中文](skill-catalog.zh-CN.md)

Portable invocation uses `$omc-*` or `/skills`. Every Skill follows the shared language policy; tool-using workflows also follow the capability contract.

| Skill | Primary responsibility |
| --- | --- |
| `omc-orchestrator` | Route lifecycle work and name the next decision |
| `omc-doctor` | Inspect active capabilities and degradation routes without writes |
| `omc-intentgate` | Require acceptance, inspect capabilities, and select continuation |
| `omc-letgo` | Autonomously choose a bounded turn or native continuation |
| `omc-loop` | Adapt a validated contract to native Goal continuation |
| `omc-init` | Initialize durable project context |
| `omc-discover` | Produce an MVP discovery brief |
| `omc-spec` | Define scope, non-goals, and acceptance |
| `omc-architecture` | Define modules, contracts, risks, and sequence |
| `omc-implement` | Execute an approved plan with evidence |
| `omc-qa` | Verify acceptance paths and regressions |
| `omc-debug` | Diagnose root cause before repair |
| `omc-refactor` | Improve structure while preserving behavior |
| `omc-review` | Review changes against specification and standards |
| `omc-release` | Prepare a release decision and rollback plan |
| `omc-debt` | Record intentional engineering trade-offs |
| `omc-team` | Configure and run native subagent roles |
| `omc-cn` | Switch plugin-owned metadata and guidance to Simplified Chinese |
| `omc-en` | Restore canonical English metadata and guidance |

The continuation and language entries are explicit-only. Lifecycle Skills remain implicitly discoverable when their descriptions match the request.
