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
The merge command pins the expected head and respects GitHub protections.
If that command does not succeed, an always-run cleanup step disables any existing auto-merge request for the open PR.
This includes failed eligibility or metadata checks, skipped major/maintainer updates, cancelled steps and ambiguous queue failures.
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
Fixture tests validate the guard and queued-state cleanup; an actual eligible dependency PR is needed to prove live operation.

## Secret scan

secret-scan.yml scans all fetched refs and complete history, including merge-resolution changes, with Gitleaks and redacted output.
The Linux binary is release-pinned and checked against its verified SHA-256 digest before execution.
Caller Gitleaks configuration is honored, so review any allowlists as part of normal code review.
Existing findings also fail; this workflow does not silently create a baseline or suppress results.
Changing the release requires updating and verifying its digest together.

## Local entrypoints

copilot-setup-steps.yml remains a local workflow with a job named copilot-setup-steps so its environment exists in the session Copilot will use.
This repository's setup installs Python validation tools and Node before running regression tests.
Consumer repositories keep their own setup commands; a separately hosted reusable job cannot prepare another job's filesystem.

Dependabot configuration also remains local at .github/dependabot.yml.
This library updates Actions, Python validation dependencies, and the actionlint container.
Consumer configurations should list their actual ecosystems, including npm only when they use it.
