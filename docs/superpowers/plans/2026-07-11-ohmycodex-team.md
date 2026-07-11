# OhMyCodex Team Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use inline execution with checkpoints. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add native Codex subagent configuration and orchestration to the existing single OhMyCodex plugin.

**Architecture:** `ohmycodex-team` bundles custom-agent TOML templates and an idempotent installer. The installer writes only missing project-owned files and merges safe global agent defaults. Existing lifecycle skills delegate to Team for eligible read-heavy work and keep application writes single-threaded.

**Tech Stack:** Codex skills and custom-agent TOML, Python standard library, GitHub Actions.

## Global Constraints

- Keep one skills-only `ohmycodex` plugin; add no MCP, hook, telemetry, or external runtime.
- Use `gpt-5.6-luna`, `gpt-5.6-terra`, `gpt-5.6`, and `gpt-5.5`; do not use GPT-5.4 models.
- Never overwrite project-owned `.codex` files without explicit user instruction.
- Default to at most four direct threads and one nesting level; use only one code-writing agent at once.

---

### Task 1: Add custom-agent templates and installer

**Files:**
- Create: `plugins/ohmycodex/skills/ohmycodex-team/assets/agents/omc-*.toml`
- Create: `plugins/ohmycodex/skills/ohmycodex-team/scripts/install_team_agents.py`
- Test: `tests/test_install_team_agents.py`

**Interfaces:**
- Consumes: target repository path and bundled TOML templates.
- Produces: `target/.codex/agents/omc-*.toml`, plus missing `[agents]` defaults in `target/.codex/config.toml`.

- [ ] **Step 1: Write installer tests for a fresh project, existing files, and dry run.**

```python
result = install_templates(target, source, dry_run=False)
assert result.created == ["omc-explorer.toml", "omc-fallback.toml"]
assert "max_threads = 4" in (target / ".codex/config.toml").read_text()
```

- [ ] **Step 2: Run the tests and confirm they fail because the installer is absent.**

Run: `python3 -m unittest tests.test_install_team_agents -v`

- [ ] **Step 3: Implement template installation and conservative config merge.**

```python
if destination.exists():
    skipped.append(destination.name)
else:
    shutil.copyfile(source, destination)
    created.append(destination.name)
```

Only append `[agents]`, `max_threads = 4`, and `max_depth = 1` when no `[agents]` section exists. Never edit an existing section.

- [ ] **Step 4: Add eight role templates with required `name`, `description`, `developer_instructions`, exact model policy, reasoning effort, and sandbox mode.**

- [ ] **Step 5: Re-run the tests and commit.**

Run: `python3 -m unittest tests.test_install_team_agents -v`

Commit: `feat(team): add native agent templates and installer`

### Task 2: Add the Team skill and team-run artifact contract

**Files:**
- Create: `plugins/ohmycodex/skills/ohmycodex-team/SKILL.md`
- Create: `plugins/ohmycodex/skills/ohmycodex-team/agents/openai.yaml`
- Modify: `plugins/ohmycodex/skills/ohmycodex-orchestrator/references/workspace-contract.md`
- Test: `scripts/validate_plugin.py`

**Interfaces:**
- Consumes: installed `omc-*` agents when local native subagents are available.
- Produces: `.ohmycodex/plans/team-runs/<timestamp>.md` with roster, model, evidence, risk, and consolidation.

- [ ] **Step 1: Extend the workspace contract with the exact Team run record.**

```text
Stage, role, model, task, conclusion, evidence, risk, recommendation, fallback
```

- [ ] **Step 2: Write `ohmycodex-team` with explicit phases: install, read-only parallel delegation, parent consolidation, serial architecture/implementation, independent review, and sequential fallback.**

- [ ] **Step 3: Generate `agents/openai.yaml` with an explicit `$ohmycodex-team` prompt.**

- [ ] **Step 4: Validate the new skill and commit.**

Run: `python3 scripts/validate_plugin.py`

Commit: `feat(team): add orchestration workflow`

### Task 3: Integrate lifecycle skills without concurrent writers

**Files:**
- Modify: `plugins/ohmycodex/skills/ohmycodex-orchestrator/SKILL.md`
- Modify: `plugins/ohmycodex/skills/ohmycodex-architecture/SKILL.md`
- Modify: `plugins/ohmycodex/skills/ohmycodex-qa/SKILL.md`
- Modify: `plugins/ohmycodex/skills/ohmycodex-debug/SKILL.md`
- Modify: `plugins/ohmycodex/skills/ohmycodex-review/SKILL.md`
- Modify: `plugins/ohmycodex/skills/ohmycodex-implement/SKILL.md`
- Test: `scripts/validate_plugin.py`

**Interfaces:**
- Consumes: Team selection thresholds and result contract.
- Produces: a Team delegation request only for independent, multi-file, uncertain, or cross-disciplinary work.

- [ ] **Step 1: Add a common delegation threshold to the orchestrator.**

```text
Delegate only when two or more independent investigations can improve the decision.
```

- [ ] **Step 2: Add role-specific delegation instructions to architecture, QA, debug, and review.**

- [ ] **Step 3: Explicitly prohibit the implementation skill from parallel code writers.**

- [ ] **Step 4: Run validation and commit.**

Run: `python3 scripts/validate_plugin.py`

Commit: `feat(team): route complex workflows through roles`

### Task 4: Document and release the feature

**Files:**
- Modify: `README.md`
- Modify: `README.zh-CN.md`
- Modify: `docs/skill-catalog.md`
- Modify: `docs/compatibility.md`
- Modify: `docs/evaluation-matrix.md`
- Modify: `scripts/validate_plugin.py`
- Test: `python3 scripts/validate_plugin.py`, plugin validator, all skill validators, fixture test, installer tests.

- [ ] **Step 1: Document local native-agent setup, Web sequential fallback, role/model matrix, and the no-GPT-5.4 policy.**

- [ ] **Step 2: Add five evaluation rows: native install, parallel read-only delegation, single writer, fallback agent, and host without subagent support.**

- [ ] **Step 3: Extend static validation to require `ohmycodex-team`, all eight TOML files, role uniqueness, exact models, and valid agent metadata.**

- [ ] **Step 4: Run the complete verification suite and commit.**

Run:

```bash
python3 -m unittest tests.test_install_team_agents -v
python3 scripts/validate_plugin.py
python3 /Users/jerrywu/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py plugins/ohmycodex
for skill in plugins/ohmycodex/skills/*; do python3 /Users/jerrywu/.codex/skills/.system/skill-creator/scripts/quick_validate.py "$skill"; done
node fixtures/vibe-todo-app/test/todos.test.mjs
```

Commit: `feat(team): document and validate subagent workflow`
