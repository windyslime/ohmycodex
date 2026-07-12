---
name: omc-cn
description: Switch OhMyCodex conversation guidance and plugin-owned metadata to Simplified Chinese. Use only when the user explicitly invokes $omc-cn or /omc-cn and wants the global OhMyCodex language changed.
---

# Switch to Simplified Chinese

Read [the Language Policy](../omc-orchestrator/references/language-policy.md). Locate the plugin-owned `scripts/locale_manager.py`, the current plugin root, and the effective Codex home.

1. Inspect locale status without changing files. If the plugin root or Codex home is not writable through the current host, report that global switching is unavailable and change nothing.
2. Run the Locale Manager for `zh-CN` with structured JSON output. Let it validate both catalogs and every metadata target, recover any interrupted transaction, update only plugin-owned translatable fields, and write `$CODEX_HOME/ohmycodex/preferences.json`.
3. If it succeeds, reply in Chinese that OhMyCodex is now set to Simplified Chinese and ask the user to restart Codex or start a new task so refreshed descriptions are loaded. Do not restart Codex yourself.
4. If it fails, report the bounded error and whether recovery occurred. Do not partially rewrite metadata, edit another plugin, translate application files, or change the rest of the Codex UI.
