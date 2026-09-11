---
name: Engineering Skills Reviewer
description: Reviews current same-repository maintainer pull-request heads with pinned engineering skills and bounded findings
"on":
  pull_request:
    types:
      - opened
      - reopened
      - synchronize
      - ready_for_review
      - edited
      - closed
permissions:
  contents: read
  pull-requests: read
  copilot-requests: write
concurrency:
  group: "gh-aw-${{ github.workflow }}-${{ github.event.action != 'edited' && github.event.pull_request.number || github.event.action == 'edited' && github.event.changes.base.ref.from && github.event.pull_request.number || github.run_id }}"
  cancel-in-progress: true
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
steps:
  - name: Prefetch pull-request review context
    env:
      GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
      PR_NUMBER: ${{ github.event.pull_request.number }}
      PR_REPOSITORY: ${{ github.repository }}
      TRIGGER_HEAD_SHA: ${{ github.event.pull_request.head.sha }}
      EVENT_ACTION: ${{ github.event.action }}
      BASE_CHANGED_FROM: ${{ github.event.changes.base.ref.from || '' }}
      GH_AW_SAFE_OUTPUTS: ${{ steps.set-runtime-paths.outputs.GH_AW_SAFE_OUTPUTS }}
    run: |
      set -euo pipefail
      context_dir=/tmp/gh-aw/agent
      mkdir -p "$context_dir"
      mkdir -p "$(dirname "$GH_AW_SAFE_OUTPUTS")"

      gh pr view "$PR_NUMBER" \
        --repo "$PR_REPOSITORY" \
        --json number,title,body,state,baseRefOid,headRefName,headRefOid,additions,deletions,changedFiles,files \
        > "$context_dir/pr-meta.json"

      current_state=$(jq -r '.state' "$context_dir/pr-meta.json")
      if [ "$EVENT_ACTION" = "closed" ] || [ "$current_state" != "OPEN" ]; then
        jq -cn \
          --arg message "Skipped pull request in $current_state state." \
          '{type: "noop", message: $message}' >> "$GH_AW_SAFE_OUTPUTS"
        exit 0
      fi

      if [ "$EVENT_ACTION" = "edited" ] && [ -z "$BASE_CHANGED_FROM" ]; then
        jq -cn \
          --arg message "Skipped pull-request edit because its base branch did not change." \
          '{type: "noop", message: $message}' >> "$GH_AW_SAFE_OUTPUTS"
        exit 0
      fi

      current_head_sha=$(jq -r '.headRefOid' "$context_dir/pr-meta.json")
      if [ "$current_head_sha" != "$TRIGGER_HEAD_SHA" ]; then
        jq -cn \
          --arg message "Skipped stale pull-request head $TRIGGER_HEAD_SHA; current head is $current_head_sha." \
          '{type: "noop", message: $message}' >> "$GH_AW_SAFE_OUTPUTS"
        exit 0
      fi

      current_base_sha=$(jq -r '.baseRefOid' "$context_dir/pr-meta.json")
      gh api \
        -H "Accept: application/vnd.github.v3.diff" \
        "repos/$PR_REPOSITORY/compare/$current_base_sha...$current_head_sha" \
        | awk '
            /^diff --git / {
              skip = ($0 ~ / b\/\.github\/workflows\/.*\.lock\.yml$/ ||
                      $0 ~ / b\/\.github\/aw\/actions-lock\.json$/ ||
                      $0 ~ / b\/([^\/]+\/)*(package-lock\.json|pnpm-lock\.yaml|yarn\.lock|uv\.lock|poetry\.lock|Cargo\.lock|Podfile\.lock|Gemfile\.lock|composer\.lock|Package\.resolved)$/)
            }
            !skip { print }
          ' \
        | sed -n '1,3000p' > "$context_dir/pr-diff.patch"

      gh api \
        --paginate \
        "repos/$PR_REPOSITORY/pulls/$PR_NUMBER/comments?per_page=100" \
        --jq '.[] | {id, path, line: (.line // .original_line), body: .body[:500], user: .user.login}' \
        | jq -s '.' > "$context_dir/pr-review-comments.json"

      gh api \
        --paginate \
        "repos/$PR_REPOSITORY/issues/$PR_NUMBER/comments?per_page=100" \
        --jq '.[] | {id, body: .body[:500], user: .user.login}' \
        | jq -s '.' > "$context_dir/pr-issue-comments.json"

      gh api \
        --paginate \
        "repos/$PR_REPOSITORY/pulls/$PR_NUMBER/reviews?per_page=100" \
        --jq '.[] | {id, state, body: .body[:500], commit_id, user: .user.login}' \
        | jq -s '.' > "$context_dir/pr-reviews.json"
safe-outputs:
  create-pull-request-review-comment:
    max: 10
  add-comment:
    max: 1
  noop:
    report-as-issue: false
  report-failed-jobs: false
  report-failure-as-issue: false
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

1. Read the pre-fetched review context from `/tmp/gh-aw/agent/pr-meta.json`,
   `/tmp/gh-aw/agent/pr-diff.patch`, `/tmp/gh-aw/agent/pr-review-comments.json`,
   `/tmp/gh-aw/agent/pr-issue-comments.json`, and `/tmp/gh-aw/agent/pr-reviews.json`.
   Do not fetch this data again with GitHub tools.
2. Treat a 3000-line patch as intentionally truncated and focus on the highest-impact changed files represented in it.
3. Classify the change and apply one or two relevant skills:
   - bug fix or performance regression: `/diagnosing-bugs` and `/tdd`
   - new behavior: `/tdd` and `/grill-with-docs`
   - refactor or architecture change: `/codebase-design` and `/improve-codebase-architecture`
   - tests only: `/tdd`
   - documentation, instructions, or workflow policy: `/grill-with-docs` and `/codebase-design`
4. Read repository instructions and only the changed code needed to verify each candidate issue.
   Do not install packages, run tests, search the whole filesystem, or inspect generated and dependency lock files.
   Use existing source and tests as evidence; CI owns command execution.
5. Check existing review comments before posting so the workflow does not duplicate an earlier finding.
6. Use the GitHub pull-request tool once to verify the live state, base, and head immediately before submitting output.
   Compare the state with `OPEN` and the commits with `baseRefOid` and `headRefOid` in `/tmp/gh-aw/agent/pr-meta.json`.
   If the pull request closed or either commit changed, call `noop`.

## Finding rules

- Review changed lines only.
- Prioritize security, correctness, data loss, broken contracts, and missing regression coverage.
- Skip generated files, dependency lock files, and this workflow's compiled `.lock.yml` file.
- Verify every finding against the repository source or tests.
- Each inline comment must identify the concrete risk and the smallest sound fix.
- Put deletion-only findings in the pull-request summary comment with the file and deleted context because inline safe outputs target the right side of the diff.
- Post at most the ten most important findings.
- Do not treat a style preference or an unverified possibility as a finding.

## Output

For each verified issue, create one inline pull-request review comment.
Prefix the visible first sentence with the skill that supports the finding, such as `**[/tdd]**`.
Put lengthy evidence or examples in a `<details>` block.
The workflow submits buffered inline comments as a `COMMENT` review automatically.
When findings exist, call `add_comment` once with a concise severity summary and any deletion-only findings.
When no actionable issue remains, call `noop` with a concise current-head completion message instead of posting praise.

Do not merge, push changes, request changes, approve, or modify repository content.
