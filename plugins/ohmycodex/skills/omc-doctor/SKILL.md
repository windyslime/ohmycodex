---
name: omc-doctor
description: Inspect active Codex capabilities and safe degradation routes without changing them. Use when users ask what OhMyCodex can use, or when an OMC workflow needs a snapshot before continuation, delegation, or tool selection.
---

# Inspect Capabilities

Read [the capability contract](../omc-orchestrator/references/capability-contract.md) before collecting evidence.

1. Build Host Capability Input only from controls, tools, writable roots, and policy exposed in the current task. Assign a tool capability only when its exposed description or contract directly supports that capability; a generic MCP or REPL name is not evidence of browser, web, code-search, LSP, or AST support. Mark absent controls unavailable and never promote them from CLI configuration.
2. Locate the plugin's `scripts/capability_resolver.py`. Pass the Host Capability Input directly to its interface, or use its CLI with `--host-input -` and JSON on stdin. Use `--no-local-probes` when the surface cannot run local commands.
3. Return the normalized snapshot, the first available route for each need, and every degradation warning. Distinguish an exposed tool from a merely configured MCP server.

This workflow is read-only. Do not install an MCP, modify Codex or project configuration, write project artifacts, expose raw probe output, or include credentials. Completion requires an evidence-backed snapshot plus explicit limitations; never claim parity with another Codex surface.
