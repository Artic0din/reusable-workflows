# Changelog

All notable changes are documented here using Keep a Changelog conventions.

## [Unreleased]

### Added

- Added a Codex completion status that waits for authenticated code-review evidence on the current pull-request commit.
- Added an explicit repository rollout skill and a tested three-way update helper for tailored consumer skills.
- Added configurable repository checks, Python/npm CI, generated-output verification, CodeQL, guarded dependency automation, and local setup examples.
- Added README documentation, heading-preserving instruction refresh, workflow maintenance, and test-gap review skills.

### Fixed

- Rejected hidden managed index entries before applying skill updates and ignored Git replacement objects when reading reviewed revisions.
- Clarified workflow-pin documentation updates, copied-skill ancestry, consumer agent tools, and manual review of shared workflow dependency updates.
- Limited skill updates to tracked, selected files without external hard links or implicit source fetches.
- Rejected nested generated-output symlinks before and after builds and prevented npm script inputs from being interpreted as command options.
- Corrected instruction-link validation for filenames with balanced parentheses and escaped punctuation.
