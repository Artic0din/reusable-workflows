---
name: Engineering Skills Reviewer
description: Reviews the current pull-request head with pinned engineering skills and posts only verified, changed-line findings
"on":
  pull_request:
    types:
      - opened
      - reopened
      - synchronize
      - ready_for_review
permissions:
  contents: read
  pull-requests: read
  copilot-requests: write
engine:
  id: copilot
max-turns: 30
max-ai-credits: 2000
max-daily-ai-credits: 10000
network:
  allowed:
    - defaults
skills:
  - mattpocock/skills/diagnosing-bugs@801dca688564c529fa84f247f64472520d9ebe28
  - mattpocock/skills/tdd@801dca688564c529fa84f247f64472520d9ebe28
  - mattpocock/skills/improve-codebase-architecture@801dca688564c529fa84f247f64472520d9ebe28
  - mattpocock/skills/grill-with-docs@801dca688564c529fa84f247f64472520d9ebe28
  - mattpocock/skills/codebase-design@801dca688564c529fa84f247f64472520d9ebe28
tools:
  github:
    toolsets:
      - pull_requests
      - repos
safe-outputs:
  create-pull-request-review-comment:
    max: 10
  submit-pull-request-review:
    max: 1
  noop:
    report-as-issue: false
  report-failed-jobs: false
timeout-minutes: 15
strict: true
---

# Engineering Skills Reviewer

Review pull request #${{ github.event.pull_request.number }} in `${{ github.repository }}` at commit `${{ github.event.pull_request.head.sha }}`.

## Goal

Find high-impact defects in the changed lines and explain a concrete fix.
Use the installed engineering skills as review methods rather than as labels to add mechanically.
Stay concise and produce no generic praise.

## Review process

1. Fetch the pull request metadata, changed files, patch, existing review comments, and existing reviews with the GitHub tools.
2. Confirm that the live pull request head still equals `${{ github.event.pull_request.head.sha }}`.
   If it changed, call `noop` because the synchronize event for the newer head must own the review.
3. Classify the change and apply one or two relevant skills:
   - bug fix or performance regression: `/diagnosing-bugs` and `/tdd`
   - new behavior: `/tdd` and `/grill-with-docs`
   - refactor or architecture change: `/codebase-design` and `/improve-codebase-architecture`
   - tests only: `/tdd`
   - documentation, instructions, or workflow policy: `/grill-with-docs` and `/codebase-design`
4. Read repository instructions and only the changed code needed to verify each candidate issue.
5. Check existing review comments before posting so the workflow does not duplicate an earlier finding.
6. Re-fetch the pull request and verify the same head immediately before submitting output.
   If it changed, call `noop`.

## Finding rules

- Review changed lines only.
- Prioritize security, correctness, data loss, broken contracts, and missing regression coverage.
- Skip generated files, dependency lock files, and this workflow's compiled `.lock.yml` file.
- Verify every finding against the repository source or tests.
- Each inline comment must identify the concrete risk and the smallest sound fix.
- Post at most the ten most important findings.
- Do not treat a style preference or an unverified possibility as a finding.

## Output

For each verified issue, create one inline pull-request review comment.
Prefix the visible first sentence with the skill that supports the finding, such as `**[/tdd]**`.
Put lengthy evidence or examples in a `<details>` block.

After the inline comments, submit one overall review:

- `REQUEST_CHANGES` when a verified issue can break behavior, security, data integrity, or a required contract.
- `COMMENT` when findings are useful but non-blocking.
- When no actionable issue remains, call `noop` with a concise current-head completion message instead of posting praise.

Do not merge, push changes, approve your own work, or modify repository content.
