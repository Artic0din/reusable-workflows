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
Resolve action release tags to full SHAs and inspect action metadata before updating references.
When changing validation scripts, pass the same library commit as tooling-ref and the caller's workflow reference.
Keep generated-output verification sensitive to changed, deleted, newly generated, and ignored files.
Use [the instruction refresh skill](../refresh-instructions/SKILL.md) when instruction facts change.

## Validate

Run Python regression tests, Ruff, strict yamllint, offline pedantic zizmor, actionlint, and git diff --check.
Execute the real workflow shell steps in temporary consumer repositories for failure-path tests.
Run the local and outgoing secret scans before publishing commits.
Use the self-test workflow and at least one real consumer PR to verify GitHub execution.
Record disabled CodeQL and unexercised dependency auto-merge explicitly; skipped jobs do not prove those capabilities worked.
