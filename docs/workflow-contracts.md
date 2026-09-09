# Workflow contracts

Call these workflows at job level with workflow_call.
All jobs use GitHub-hosted Ubuntu 24.04; application-specific or macOS builds remain caller-owned.
Timeouts are bounded.
Callers own triggers and general concurrency policy.
The Dependabot job additionally owns the dedicated per-PR lock described below.

## Baseline

baseline.yml accepts required-files, a comma-separated list.
It defaults to README.md, LICENSE, .gitignore, and AGENTS.md.
Empty lists and missing files fail.
The required-files action is pinned to a verified release.
Dev Containers are optional project choices and are not a baseline requirement.

## CI

ci.yml accepts python (default true) and npm (default false); disabling both fails.
Python uses python-version-file (default .python-version), optional hash-locked python-requirements, python-test-directory (tests), and python-test-pattern (test*.py).
Zero discovered tests, import errors, and failed assertions fail the job.
The Python suite must use unittest discovery; other runners remain caller-owned.
When npm is also enabled, its Node version is available before Python tests run, supporting mixed-language test fixtures.

npm uses node-version-file (.node-version), npm-directory (.), npm-test-script (test), and optional npm-build-script.
It runs npm ci, the optional build, then the required test script.
A missing script or failed command fails.
Script names are passed after npm's option delimiter, so option-like names must resolve to actual package scripts.
Playwright installation and browser coverage remain explicit caller jobs.
No arbitrary shell-command input is accepted.

## Generated output

check-dist.yml accepts required output-path, optional build-script (build), node-version-file (.node-version), and working-directory (.).
output-path is relative to the caller repository root; working-directory selects the npm project.
The output directory must already contain tracked files and cannot escape the repository or contain symlinks or parent traversal.
The same directory validation runs before and after the build, rejecting nested directory, file and dangling symlinks.
After npm ci and the build, changed, deleted, new, and ignored generated files fail verification.
This checks reproducibility, not the application-specific runtime import graph.

## Workflow validation

linter.yml pins its executable validation bundle to a literal, reviewed library commit SHA.
It checks out the caller under source and this library under automation.
Callers cannot override that checkout revision through workflow inputs.
When scripts or tool locks change, publish that source commit on the feature branch and update the library's embedded pin in a subsequent commit before release.
The self-validation source job tests the current implementation as well as exercising the pinned reusable caller.
The actionlint Dockerfile and validation dependencies are library-owned.

yaml-paths is a newline-separated list, default .github.
Blank lines are ignored, including the trailing newline from YAML block scalars; an empty list fails.
yaml-config defaults to the caller's .yamllint.yml.
YAML checks, actionlint, and offline pedantic zizmor fail the workflow when they find problems.
Callers retain their own language-specific lint and automation tests.

validate-agent-config defaults to true.
The validator checks AGENTS.md, copilot-instructions.md, and .github skill, agent, and scoped-instruction Markdown.
It checks nonempty descriptions, skill-folder names, matching instruction scopes, and local inline Markdown file links outside fenced examples.
Inline link destinations support balanced parentheses, escaped punctuation, optional titles and angle-bracket paths.
Scopes support recursive glob stars, character classes, brace alternatives, and comma-separated patterns.
It excludes .git, .venv, node_modules, and __pycache__ from the file inventory.
It does not fetch web links, validate heading anchors or reference-style Markdown links, detect conflicting prose, or prove model behavior.

## CodeQL

codeql-analysis.yml requires explicit enabled: true to analyze.
languages is a JSON array, default actions.
Select languages supported by CodeQL build-mode none; compiled builds needing another mode stay caller-owned.
The caller must grant contents: read, actions: read, and security-events: write.
Private callers must already have the necessary GitHub Code Security entitlement and configuration.
Disabled analysis reports that no scan ran.
Never use the availability job alone as a required security guarantee.
Failed enabled scans fail normally.

## Dependabot

dependabot-automerge.yml defaults to disabled.
required-checks is a nonempty JSON array of exact check contexts.
Use only from a caller-owned pull_request_target workflow with contents: write and pull-requests: write permissions.
The shared workflow accepts only same-repository Dependabot PRs to the default branch.

Before queueing, it checks current repository auto-merge/squash settings, strict required checks, required thread resolution, live PR identity and head, and every commit's Dependabot author, GitHub web-flow committer and verified signature.
Other committers fail closed, including signed human commits attributed to Dependabot.
The complete paginated commit count must match the live PR.
Only minor/patch updates with no maintainer changes qualify.
Branches requiring GitHub's merge queue are unsupported and rejected during preflight before queueing.
Preflight requires the live pull request's isMergeQueueEnabled field to be exactly false, covering effective branch protection as well as rulesets.
This workflow manages native automatic merge requests; it does not dequeue merge-queue entries.
Shared-workflow updates and missing metadata require manual review.
The queue step records eligibility only after all guards and the merge request succeed.
The first step clears an earlier automatic merge request for the matching live Dependabot head before potentially slow API and metadata checks; a new request can be enabled only after successful verification.
Both cancellation paths recheck the live head and identity, so stale events leave newer requests intact.
A separate cleanup step revokes an existing request unless the job, metadata and queue step all succeeded with that positive result.
Cleanup runs after failures or cancellation and cannot enable a merge.
With enabled set to false, verification and queueing are skipped while cancellation still runs on matching Dependabot events.
The merge command pins the expected head and respects GitHub protections.
After metadata succeeds, the queue step rechecks the live default branch, PR target repository/ref, author, open/non-draft state and head immediately before requesting automatic merge.
Changed identity, retargeting or failed API reads prevent a new request and run cleanup for any matching earlier request.
GitHub does not provide an atomic expected-base condition for this command; a base change after the final read can still race the request.
The cleanup reads current state independently of the guard's temporary files, avoids writes when auto-merge is already disabled or the PR is closed, and reports API failures instead of suppressing them.
The job serializes all attempts for each repository/PR with a library-owned `reusable-dependabot-automerge-` concurrency group and does not cancel an active attempt.
It uses `queue: max` so delayed older events cannot replace a waiting current-head validation.
Caller workflows that also configure serialization must use a different concurrency group with `queue: max` and `cancel-in-progress: false`, or omit their redundant concurrency setting.
Cleanup checks that the current PR head still matches its triggering head before cancelling auto-merge.
This protects newer requests even when an older workflow starts late; [GitHub does not guarantee dispatch ordering](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency).
Cleanup needs a running job and working GitHub API access; it cannot revoke a completed merge or run after the runner is forcibly terminated.
GitHub limits each queue to 100 pending attempts and cancels additional arrivals when full; an attempt cancelled at that limit must be rerun before relying on its validation or cleanup.
The pinned actionlint 1.7.12 does not yet recognize GitHub's documented `queue` property.
A temporary path-specific exception suppresses only that unknown-key diagnostic; regression tests require `queue: max` and `cancel-in-progress: false`.
Remove this exception when the pinned actionlint supports `queue`; other syntax checks remain enabled.
There is no checkout, execution of PR code, automatic approval, or protection bypass.
GitHub may merge immediately if all configured requirements already pass.
Do not enable this capability until the caller's effective rules and its intended review requirements are verified.
Fixture tests execute both queueing and cancellation; an actual eligible dependency PR is needed to prove live operation.

## Secret scan

secret-scan.yml scans all fetched refs and complete history, including merge-resolution changes, with Gitleaks and redacted output.
The Linux binary is release-pinned and checked against its verified SHA-256 digest before execution.
Caller Gitleaks configuration is honored, so review any allowlists as part of normal code review.
Existing findings also fail; this workflow does not silently create a baseline or suppress results.
Changing the release requires updating and verifying its digest together.

## Codex review completion

codex-review-gate.yml requires a positive integer pull-request-number and caller permissions contents: read, issues: read, pull-requests: read, and statuses: write.
It does not check out code, execute pull-request content, approve reviews, merge changes, or receive publishing credentials.
The public workflow source must be pinned to a reviewed full commit SHA in the caller.

The workflow publishes the commit-status context `Codex review complete`.
Require this exact context from GitHub Actions after verifying a real consumer run; the workflow job's own success is not the completion signal.
Missing, running or stale code-review evidence stays pending.
Failed, cancelled, unknown or malformed evidence cannot pass.
Status writes retry transient failures; verification errors attempt to publish an error status, including when the initial pending write fails.
Completed review passes only after its abbreviated commit resolves through GitHub to the full current head and the head is rechecked before publication.
Only the authenticated `chatgpt-codex-connector[bot]` account, including its numeric account ID and bot type, can supply evidence.
The separate Security Review row cannot satisfy Code Review completion.
The latest summary and all pages of comments are considered.
An owner, member or collaborator's newer `@codex review` request invalidates older completion evidence.
Completion must be in a later second than a request because comment timestamps cannot establish ordering within one second.
Edited requests use their edit time, and the triggering event preserves a request even if its comment is removed.
The latest request timestamp is retained in authenticated GitHub Actions status descriptions for that PR and commit, so later refreshes cannot forget a deleted request.
Triggering requests are persisted before draft handling and fallible list or comment reads.
A PR base-branch change also invalidates earlier completion, even when its head SHA is unchanged; title and body edits do not.
Untrusted commenters cannot hold the gate by posting review requests that Codex would not honor.

Keep required review-conversation resolution enabled independently: completed code review can contain findings and does not mean approval.
Enable Codex Review all PRs and On every push before requiring this status.
Do not silently pass when Codex is unavailable or its summary format changes.

Callers serialize gate jobs repository-wide, after the trusted-event job condition, with cancel-in-progress: false and queue: max.
The default single pending run can discard a base-change or deleted-request event before its invalidation is persisted.
GitHub queues up to 100 pending runs with queue: max; monitor cancelled runs and retry dropped invalidations if this platform limit is reached.
Use pull_request_target for opened, reopened, synchronize, edited, ready_for_review, converted_to_draft and closed events; the gate reads GitHub metadata only.
Also handle created, edited and deleted issue_comment events on pull requests when the author is Codex, or a trusted contributor is requesting a review.
Include workflow_dispatch with a required pull-request-number input to initialize existing PRs and recover missed events.
Comment events load the caller from its default branch, so merge the caller before relying on them.
GitHub event delivery, runner startup, and status publication are asynchronous: a same-commit manual re-review has a short propagation window before its pending status appears.
If GitHub's API remains unavailable, no workflow can replace an already-published status; the failed run must be retried after service recovers.
A new commit has no successful status until its own completion is verified.
Status contexts are commit-scoped, so all open PRs sharing a head must have completed code review before that commit succeeds.
The gate rechecks the entire matching PR set, base identities, heads and draft states before publication.
Closing or pushing one PR also refreshes any remaining PRs on its previous head.

## Engineering skills reviewer

`skills-reviewer.md` is the maintained gh-aw source and `skills-reviewer.lock.yml` is its generated executable workflow.
Keep the pair in the consuming repository because pull-request event workflows must be present on the caller's default branch and cannot be delivered through a job-level `workflow_call`.
Edit the Markdown source and regenerate the lock with the gh-aw version recorded in its metadata; never edit the lock directly.
The repository excludes generated locks from formatting-only yamllint rules and generator-owned zizmor findings while actionlint and gh-aw continue to validate executable syntax and policy.
The pinned actionlint predates `copilot-requests` and gh-aw's generated `queue` extension, so path-specific ignores suppress only those two unknown-key diagnostics for this lock.

The workflow runs for opened, reopened, synchronized, and ready-for-review pull requests.
Its concurrency policy cancels an older run when the same pull request receives a newer commit.
It verifies the live head before review output and instructs stale runs to finish without comments.
gh-aw's strict activation guard runs this configuration only for same-repository pull requests initiated by an actor with write, maintain, or admin access.
Fork pull requests and untrusted actors are intentionally outside this workflow's contract.

The workflow grants read access to contents and pull requests plus `copilot-requests: write` for the agent engine.
The generated safe-output jobs receive `pull-requests: write` for at most ten inline comments and one pull-request summary comment.
They also receive `issues: write` because gh-aw can report missing tools or data and incomplete runs as issues.
Provider and agent failures remain visible in the workflow run but do not create repository issues.
It cannot push code, merge, approve, or change repository settings.

Before the agent starts, a deterministic step fetches the current base and head metadata, an exact-SHA diff capped at 3000 lines, existing review comments, and existing reviews.
It removes generated workflow output and common dependency lock files from the review diff before applying the cap.
The agent reads that local context and uses the GitHub pull-request tool only for its final base-and-head check, keeping model invocations bounded.

The five Matt Pocock skills are pinned to one reviewed full commit SHA.
The reviewer selects one or two methods for each change, checks existing comments, skips generated and lock files, and reports only verified issues on changed lines.
Buffered inline comments are submitted as a non-blocking `COMMENT` review, and the workflow does not expose a review-decision tool that could approve or request changes.
Deletion-only findings go in the pull-request summary comment because the generated inline-comment handler targets right-side diff lines.
No-finding runs use a silent `noop` rather than creating an issue or praise comment.
Stale-head runs queue the same `noop` and then fail the prefetch step so the agent cannot run against mixed context.

The workflow is advisory until a real consumer run proves the installed Copilot entitlement, generated check context, current-head behavior, and review output.
If its workflow check becomes required, keep required review-thread resolution enabled because a successful run can still create unresolved findings.

## Local entrypoints

copilot-setup-steps.yml remains a local workflow with a job named copilot-setup-steps so its environment exists in the session Copilot will use.
This repository's setup installs Python validation tools and Node before running regression tests.
Consumer repositories keep their own setup commands; a separately hosted reusable job cannot prepare another job's filesystem.

Dependabot configuration also remains local at .github/dependabot.yml.
This library updates Actions, Python validation dependencies, and the actionlint container.
Consumer configurations should list their actual ecosystems, including npm only when they use it.
