# Changelog

All notable changes are documented here using Keep a Changelog conventions.

## [Unreleased]

### Added

- Added configurable repository checks, Python/npm CI, generated-output verification, CodeQL, guarded dependency automation, and local setup examples.
- Added README documentation, heading-preserving instruction refresh, workflow maintenance, and test-gap review skills.

### Fixed

- Cancelled previously enabled dependency auto-merge when a later run failed or skipped eligibility, metadata verification or queueing.
- Rejected nested generated-output symlinks before and after builds and prevented npm script inputs from being interpreted as command options.
- Corrected instruction-link validation for filenames with balanced parentheses and escaped punctuation.
