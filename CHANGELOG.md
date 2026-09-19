# Changelog

All notable changes are documented here using Keep a Changelog conventions.

## [Unreleased]

### Added

- Added a repository-local engineering review workflow with five commit-pinned skills, pre-fetched current-head context, bounded inline findings, and a generated gh-aw lock.
- Added a Codex completion status that waits for authenticated code-review evidence on the current pull-request commit.
- Added an explicit repository rollout skill and a tested three-way update helper for tailored consumer skills.
- Added configurable repository checks, Python/npm CI, generated-output verification, CodeQL, guarded dependency automation, and local setup examples.
- Added README documentation, heading-preserving instruction refresh, workflow maintenance, and test-gap review skills.
- Added an `.agents/skills` symlink to `.github/skills` so agents that scan the `.agents` convention discover this repository's skills without duplicating them.

### Removed

- Removed the zizmor workflow-security scan from the shared validation workflow, its configuration file, and the locked development requirements.
  Callers referencing this library at `@main` no longer need a `.github/zizmor.yml` policy exception; actionlint continues to validate workflow syntax and the secret scan continues to check history.

### Changed

- Changed CodeQL results for consumers that enable it. `codeql-analysis.yml` now references `github/codeql-action@v4`
  rather than the v4.37.9 commit it was pinned to. That tag currently resolves to v4.38.1, which ships CodeQL bundle
  2.27.0 in place of 2.26.4, so query packs and alert results move on the next run with no pull request in the caller.
- Replaced every SHA-pinned action reference in this library's workflows with its floating major tag, and pointed
  `linter.yml`'s library-owned validation bundle at `main` instead of a fixed commit.
  Consumers already receive these workflows from `main`, so a fixed bundle revision only held the tools behind the
  workflow running them, and every release needed a pin-bump commit. The bundle reference stays a literal the
  library controls and is still not a caller input; the contract test now asserts that property rather than a SHA shape.
- Documented `@main` as the consumer reference for this library's reusable workflows, replacing the full-commit-SHA pin.
  `@main` resolves to the tip of the default branch at each caller run, so nothing is rewritten in the caller and Dependabot has nothing to bump for this library; rollback is a revert here rather than a pull request in every caller.
  A caller that needs a change frozen can still use a full commit SHA. The actionlint image, the gitleaks binary, and the compiled review-skill locks are unaffected.

### Fixed

- Stopped callers installing the removed zizmor dependency on every linter run. The library-owned validation-tools
  checkout had been left on a revision predating the removal, and now tracks `main`.

- Removed the baseline check's deprecated Node 20 action dependency by validating required paths with the runner's Python standard library in isolated mode.
  Preserved empty-list and missing-path failures and added regression coverage for literal filenames, whitespace, directories and symlinks.
- Increased the Engineering Skills Reviewer runtime invocation cap from 30 to 45 to reduce false-failure `HTTP 429` runs on larger pull requests.
- Stopped stale, closed, and unrelated pull-request edit runs before agent execution, initialized their safe-output path, deduplicated against issue comments, and excluded nested dependency locks before truncating review context.
- Rechecked dependency pull-request targets after metadata verification before enabling automatic merges.
- Serialized dependency auto-merge attempts within the shared workflow and retained pending validations when delayed events arrive.
- Cleared earlier automatic merge requests before verifying dependency updates.
- Preserved current automatic merge requests when older events were rerun.
- Separated unrelated pull-request title/body edited events into a non-blocking concurrency lane so maintainers can still review active, in-progress pull requests.

- Rejected merge-queue callers before enabling dependency automatic merges, whose cancellation contract applies only to native auto-merge requests.
- Revoked existing automatic merge requests when complete dependency eligibility no longer succeeds, including missing metadata, major updates and failures.

- Rejected hidden managed index entries before applying skill updates and ignored Git replacement objects when reading reviewed revisions.
- Clarified workflow-pin documentation updates, copied-skill ancestry, consumer agent tools, and manual review of shared workflow dependency updates.
- Limited skill updates to tracked, selected files without external hard links or implicit source fetches.
- Rejected nested generated-output symlinks before and after builds and prevented npm script inputs from being interpreted as command options.
- Corrected instruction-link validation for filenames with balanced parentheses and escaped punctuation.
