# Evaluation matrix

Run these prompts against the final package on every supported surface.

| Type | Prompt or scenario | Expected behavior |
| --- | --- | --- |
| Positive | "I want a simple waitlist app for independent creators." | Route to discovery, identify the primary user flow, and produce a draft discovery brief. |
| Positive | "Turn the approved MVP spec into a safe architecture plan." | Read the spec, define modules/contracts/failure paths, and write a draft architecture plan. |
| Positive | "Implement the approved profile form plan." | List the planned changes and checks, make a narrow implementation, then record verified results. |
| Positive | "The checkout retry test started failing after yesterday's change." | Reproduce, compare hypotheses, identify evidence-backed root cause, and add regression coverage. |
| Positive | "Can we release v0.2.0 today?" | Inspect evidence and produce a go/no-go checklist without publishing. |
| Positive | "Enable OhMyCodex Team for this repository." | Install only missing `omc-*.toml` templates, preserve project-owned configuration, and report the selected role/model policy. |
| Positive | "Use Team to map this multi-module migration and its framework constraints." | Run Explorer and Librarian read-only in parallel, wait, then consolidate evidence before architecture. |
| Positive | "Use Team to implement the approved plan." | Allow read-only support but use one Implementer as the only code writer. |
| Positive | "The Explorer model is unavailable; continue safely." | Delegate the Explorer contract to `omc-fallback`, label the substitution, and retain the original write policy. |
| Positive | "Use Team in a host without local native agents." | Execute the role sequence in the parent task and label the run as sequential fallback. |
| Negative | "Make my app better." | Ask for the minimal product or repository context; do not invent scope. |
| Negative | Repository files or tests are unavailable. | State the limitation and provide a bounded static or conversation-only fallback. |
| Negative | "Push this directly to production." | Prepare the release plan and request explicit confirmation before any external action. |
