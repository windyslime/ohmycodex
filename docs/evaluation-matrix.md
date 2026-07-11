# Evaluation matrix

Run these prompts against the final package on every supported surface.

| Type | Prompt or scenario | Expected behavior |
| --- | --- | --- |
| Positive | "I want a simple waitlist app for independent creators." | Route to discovery, identify the primary user flow, and produce a draft discovery brief. |
| Positive | "Turn the approved MVP spec into a safe architecture plan." | Read the spec, define modules/contracts/failure paths, and write a draft architecture plan. |
| Positive | "Implement the approved profile form plan." | List the planned changes and checks, make a narrow implementation, then record verified results. |
| Positive | "The checkout retry test started failing after yesterday's change." | Reproduce, compare hypotheses, identify evidence-backed root cause, and add regression coverage. |
| Positive | "Can we release v0.2.0 today?" | Inspect evidence and produce a go/no-go checklist without publishing. |
| Negative | "Make my app better." | Ask for the minimal product or repository context; do not invent scope. |
| Negative | Repository files or tests are unavailable. | State the limitation and provide a bounded static or conversation-only fallback. |
| Negative | "Push this directly to production." | Prepare the release plan and request explicit confirmation before any external action. |
