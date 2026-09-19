---
name: github-actions
description: Build and validate this reusable-workflow library or adapt its workflows to a caller repository.
---

# Maintain reusable GitHub Actions

Read [workflow contracts](../../../docs/workflow-contracts.md), the target workflow, and the caller's current checks before editing.
Workflows are public APIs: preserve input types, default behavior, permissions, failure propagation, and required-check compatibility.

## Implement

Keep reusable entrypoints in .github/workflows with workflow_call.
Keep Copilot's copilot-setup-steps job and Dependabot's configuration in the consuming repository.
Use read-only permissions for checks and explicit caller opt-in for privileged automation.
Never execute pull-request code in the Dependabot target workflow, approve reviews automatically, or bypass protections.
Reference actions by their floating major tag and inspect action metadata before updating references.
linter.yml checks its validation bundle out of this library at `main`, so a tooling change reaches callers on their next run without a second commit.
Keep that reference library-owned; caller input must not select executable tooling.
Keep generated-output verification sensitive to changed, deleted, newly generated, and ignored files.
For gh-aw workflows, edit the Markdown source, compile the `.lock.yml` with the recorded compiler version and pinned action release, and commit the source, lock, `.github/aw/actions-lock.json`, and `.gitattributes` changes together.
Treat event-driven agentic workflows as repository-local assets; document copying and validation instead of presenting them as `workflow_call` entrypoints.
Use [the instruction refresh skill](../refresh-instructions/SKILL.md) when instruction facts change.

## Validate

Run Python regression tests, Ruff, strict yamllint, actionlint, and git diff --check.
Run `gh aw compile <workflow> --validate --no-check-update` and confirm it reports no warnings before validating the generated lock with the repository linters.
Execute the real workflow shell steps in temporary consumer repositories for failure-path tests.
Run the local and outgoing secret scans before publishing commits.
Use the self-test workflow and at least one real consumer PR to verify GitHub execution.
Record disabled CodeQL and unexercised dependency auto-merge explicitly; skipped jobs do not prove those capabilities worked.
