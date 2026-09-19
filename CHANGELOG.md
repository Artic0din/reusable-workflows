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

- Documented `@main` as the consumer reference for this library's reusable workflows, replacing the full-commit-SHA pin.
  `@main` resolves to the tip of the default branch at each caller run, so nothing is rewritten in the caller and Dependabot has nothing to bump for this library; rollback is a revert here rather than a pull request in every caller.
  A caller that needs a change frozen can still use a full commit SHA. The library-owned validation-tools checkout, third-party actions, the actionlint image, the gitleaks binary, and the pinned review skills are unaffected.

### Fixed

- Restored the Engineering Skills Reviewer lock. A dependency pull request edited the generated
  `skills-reviewer.lock.yml` directly, bumping an action the compiler derives from its own version and reverting
  `GH_AW_MAX_TURNS` from 45 to 30, which silently undid the invocation-cap fix and left the frontmatter hash
  mismatched so every `activation` run failed. Regenerated with the pinned compiler.
  The contract test no longer reimplements gh-aw's frontmatter hash, which disagreed with the compiler and made
  the unit test and the determinism gate mutually unsatisfiable. It now derives `max-turns` from the source and
  requires the generated lock to agree, which is the value that regressed.
- Added the compiler-backed determinism gate to `validate-self.yml`. Nothing in this repository ran `gh aw compile`,
  so a stale lock could merge and only surfaced later as a failed `activation` run. The gate installs the compiler
  version recorded in the lock and fails on any diff, and a contract test asserts the gate itself still exists.
- Advanced the library-owned validation-tools checkout in `linter.yml` to the revision that drops zizmor, so callers stop installing the unused dependency on every linter run.

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
