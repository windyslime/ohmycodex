# Language Policy

Use this policy for every OhMyCodex conversation and generated OhMyCodex artifact.

English is the checked-in default. When the host permits reading it, inspect `$CODEX_HOME/ohmycodex/preferences.json`; schema version `1` with `language` equal to `en` or `zh-CN` selects the global OhMyCodex language. If the preference is absent or unavailable, use English. An explicit language instruction in the current task overrides the saved preference for that task without changing the global setting.

Apply the selected language to OhMyCodex explanations, questions, summaries, and `.ohmycodex` prose artifacts. Do not translate source code, identifiers, commands, file paths, configuration keys, protocol values, evidence IDs, or raw logs. Do not change application files, the rest of the Codex UI, or metadata owned by another plugin.

`omc-cn` and `omc-en` use the transactional Locale Manager to materialize plugin-owned descriptions and save the preference. A successful switch requires restarting Codex or starting a new task before already-loaded Skill descriptions refresh. The commands never restart Codex themselves.

If saved `zh-CN` preference and materialized English metadata disagree after an upgrade, keep the mismatch explicit. `omc-doctor` should recommend rerunning `$omc-cn`; it must not repair the mismatch automatically or install a SessionStart Hook.
