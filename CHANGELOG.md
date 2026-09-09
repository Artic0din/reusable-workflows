# Changelog

All notable changes are documented here using Keep a Changelog conventions.

## [Unreleased]

### Added

- Added a repository-local engineering review workflow with five commit-pinned skills, pre-fetched current-head context, bounded inline findings, and a generated gh-aw lock.
- Added a Codex completion status that waits for authenticated code-review evidence on the current pull-request commit.
- Added an explicit repository rollout skill and a tested three-way update helper for tailored consumer skills.
- Added configurable repository checks, Python/npm CI, generated-output verification, CodeQL, guarded dependency automation, and local setup examples.
- Added README documentation, heading-preserving instruction refresh, workflow maintenance, and test-gap review skills.

### Fixed

- Rechecked dependency pull-request targets after metadata verification before enabling automatic merges.
- Serialized dependency auto-merge attempts within the shared workflow and retained pending validations when delayed events arrive.
- Cleared earlier automatic merge requests before verifying dependency updates.
- Preserved current automatic merge requests when older events were rerun.

- Rejected merge-queue callers before enabling dependency automatic merges, whose cancellation contract applies only to native auto-merge requests.
- Revoked existing automatic merge requests when complete dependency eligibility no longer succeeds, including missing metadata, major updates and failures.

- Rejected hidden managed index entries before applying skill updates and ignored Git replacement objects when reading reviewed revisions.
- Clarified workflow-pin documentation updates, copied-skill ancestry, consumer agent tools, and manual review of shared workflow dependency updates.
- Limited skill updates to tracked, selected files without external hard links or implicit source fetches.
- Rejected nested generated-output symlinks before and after builds and prevented npm script inputs from being interpreted as command options.
- Corrected instruction-link validation for filenames with balanced parentheses and escaped punctuation.
