---
name: test-gap-audit
description: Review a requested workflow or change for missing behavioral tests and unproven failure handling without editing files.
---

# Review workflow test gaps

Stay within the requested workflow, PR, or feature and its direct dependencies.
Read current implementation and existing assertions before reporting a gap.
Distinguish confirmed missing tests from cases not inspected.

For this library, prioritize rejected inputs, empty success paths, permission boundaries, skipped jobs, generated-file changes, upstream API failures, and caller compatibility.
A YAML parse is not a GitHub execution test, a stubbed API is not proof of live authorization, and a passing happy path does not establish failure propagation.
Prefer executing the actual script with isolated fixtures over assertions that merely search its text.

For each verified gap, report the behavior, exact source location, existing coverage, and the smallest test that would prove it.
Report an explicit no-findings result when appropriate and state coverage limitations.
Do not add tests, open issues, post reviews, or change settings unless that action is included in the user's request.
