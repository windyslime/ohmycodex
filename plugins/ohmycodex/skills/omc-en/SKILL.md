---
name: omc-en
description: Restore English OhMyCodex conversation guidance and plugin-owned metadata. Use only when the user explicitly invokes $omc-en or /omc-en and wants the global OhMyCodex language changed back to English.
---

# Restore English

Read [the Language Policy](../omc-orchestrator/references/language-policy.md). Locate the plugin-owned `scripts/locale_manager.py`, the current plugin root, and the effective Codex home.

1. Inspect locale status without changing files. If the plugin root or Codex home is not writable through the current host, report that global switching is unavailable and change nothing.
2. Run the Locale Manager for `en` with structured JSON output. Let it validate both catalogs and every metadata target, recover any interrupted transaction, restore the canonical checked-in English metadata, and write `$CODEX_HOME/ohmycodex/preferences.json`.
3. If it succeeds, state that OhMyCodex is now set to English and ask the user to restart Codex or start a new task so refreshed descriptions are loaded. Do not restart Codex yourself.
4. If it fails, report the bounded error and whether recovery occurred. Do not partially rewrite metadata, edit another plugin, translate application files, or change the rest of the Codex UI.
