# Capability Contract

Use this contract whenever an OhMyCodex workflow chooses a tool, native control, subagent, or external-wait strategy.

## Authority

The current task is authoritative for exposed tools and controls. Local probes describe installation or configuration only.

| Capability | Authoritative evidence | Supplementary evidence |
| --- | --- | --- |
| Goal inspect/create/complete/block | Current host controls | `codex features list` may report local configuration only |
| Scheduled create/delete | Current host controls | None |
| Native subagents and background terminal | Current host controls | None |
| Writable roots, approval, sandbox | Current host policy | Never use `os.access` to upgrade the host result |
| Usable tools | Tools exposed in the current task | Executables and configured MCP entries may supply later routes |
| Git and project commands | Bounded local probes | File/acceptance fingerprints when Git is unavailable |

Never infer Goal or Scheduled support from a CLI help command. Never treat an enabled or authenticated MCP configuration as proof that its tools are exposed in the current task. Assign a tool capability only when the exposed tool description or contract directly supports it; do not reclassify a generic MCP or REPL from its name.

## Host Capability Input

Construct one strict JSON object. Omit secrets and reject unknown fields.

```json
{
  "schema_version": 1,
  "surface": "desktop",
  "controls": {
    "goal": {
      "inspect": true,
      "create": true,
      "complete": true,
      "block": true
    },
    "scheduled": {
      "create": true,
      "delete": true
    },
    "subagents": true,
    "background_terminal": true
  },
  "access": {
    "writable_roots": ["/absolute/repository/path"],
    "approval_policy": "never",
    "sandbox_mode": "danger-full-access"
  },
  "tools": [
    {
      "name": "openaiDeveloperDocs",
      "kind": "mcp",
      "server": "openaiDeveloperDocs",
      "capabilities": ["official_docs"]
    }
  ]
}
```

Allowed tool capabilities are `local_search`, `lsp`, `ast`, `code_search`, `official_docs`, `browser`, and `web`.

## Snapshot

Call:

```text
resolve_capabilities(repository, host_capabilities) -> CapabilitySnapshot
```

The snapshot reports:

- Host-authoritative continuation, Scheduled, subagent, background-terminal, approval, and writable-workspace state.
- Exposed tools separately from reduced configured-MCP entries.
- Git HEAD, dirty state, a worktree fingerprint, and evidence strength.
- Bounded local executable and project-script discovery.
- Ordered routes for local search, definitions, structural query, structural rewrite, external search, official documentation, parallel investigation, and external wait.
- Stable warning codes without raw stdout, stderr, headers, environment values, commands, URLs, tokens, or credentials.

`configured_locally` on continuation is informational. It never changes `continuation.available`.

## Route Order

| Need | Order |
| --- | --- |
| Local discovery | Exposed host search, `rg`, project search, bounded file inspection |
| Definitions and diagnostics | Exposed LSP, project compiler/typecheck/build, bounded static inspection |
| Structural query | Exposed AST, `sg` or `ast-grep`, project parser |
| Structural rewrite | Exposed AST, `sg` or `ast-grep`, project codemod |
| External source search | Exposed code-search, browser, then web tool |
| Official documentation | Exposed official-docs tool, browser, then web tool |
| Parallel investigation | Native subagents, then the same role sequence in the parent task |
| External wait | Same-task Scheduled heartbeat, bounded terminal for a short process, then recoverable Goal |

Text search may locate structural candidates but must never perform or claim a structural rewrite. An unavailable route stays explicit instead of being replaced with fabricated success.

## Probe Safety

Use argument arrays with `shell=False`, bounded timeouts, and bounded returned output. Reduce `codex mcp list --json` entries to `name`, `enabled`, `transport.type`, and `auth_status`; normalize unknown transport or auth tokens instead of copying them. A probe failure selects the next route and records a stable warning code.

MCP installation is outside Doctor. A workflow that later proposes installation must use an existing registry, a Skill dependency, user-supplied documented configuration, or an authoritative project source, then preserve the Codex-native trust and approval flow.
