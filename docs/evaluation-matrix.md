# Evaluation matrix

Run these scenarios on supported surfaces without simulating unavailable host controls.

| Type | Scenario | Expected behavior |
| --- | --- | --- |
| Positive | `$omc-intentgate` with no acceptance contract | Route to discovery/specification and create no Goal |
| Positive | New direct continuation | Ask once for `X`, default/minimum `3`, then pass it to Loop |
| Positive | Matching Goal and ledger | Reconcile and resume without asking for `X` again |
| Negative | Foreign unfinished Goal | Do not replace or adopt it |
| Recovery | Goal created, activation interrupted | Match run ID and activate without a duplicate Goal |
| Recovery | Repository fingerprint changed | Mark bound verification stale before continuing |
| Positive | `$omc-letgo` on bounded work | Complete one turn without Goal or ledger |
| Positive | `$omc-letgo` on continuing work | Record assumptions, choose `X`, and delegate to Loop |
| Negative | Untrusted MCP endpoint | Reject without an install attempt |
| Degradation | MCP installation fails | Record the error and choose the next capability route |
| Degradation | AST route missing | Never use text replacement as structural rewrite |
| Waiting | External state unchanged | Keep waiting and use a bounded same-task heartbeat |
| Recovery | External state changes | Clean the heartbeat before resuming |
| Negative | Unrelated external state changes | Keep the run blocked |
| Degradation | Scheduled unavailable, short process | Use only a bounded terminal wait |
| Degradation | Scheduled unavailable, long wait | Keep a recoverable Goal |
| Degradation | Workspace is read-only | Report reduced audit and threshold recovery |
| Degradation | Git unavailable | Use labeled file and acceptance fingerprints |
| Recovery | Locale transaction is interrupted | Restore every target before a new switch |
| Positive | English → Chinese → English | Restore canonical English bytes and preserve stable metadata |
| Negative | Push, deploy, tag, or publish under Letgo | Require the existing user/native gate immediately before action |
