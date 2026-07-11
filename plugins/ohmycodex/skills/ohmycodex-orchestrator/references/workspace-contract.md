# OhMyCodex workspace contract

Create the following files only when the host grants write access. Never overwrite confirmed content without showing the intended change.

```text
.ohmycodex/
  project.md
  decisions.md
  technical-debt.md
  specs/
    discovery.md
    mvp.md
  plans/
    architecture.md
    implementation.md
    verification.md
    diagnosis.md
    refactor.md
    review.md
  releases/
    checklist.md
```

Every artifact starts with `Status: draft | approved | superseded`, `Owner:`, and `Updated:`. Use concise Markdown. Record a source link or file path for every repository-specific claim.

## Project profile

Record product purpose, runtime/tooling, test/build/type-check commands, deployment path, data sensitivity, known constraints, and source-of-truth documents.

## Decision record

For each material decision record context, options considered, selected option, consequence, and revisit trigger.

## Evidence record

For tests, reviews, diagnostics, and releases record the exact command or inspection, result, unresolved risk, and next owner. Never claim a command passed unless it ran successfully in the current environment.
