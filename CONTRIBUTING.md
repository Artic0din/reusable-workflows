# Contributing

Use an issue for planned work and a feature branch for changes.
Keep pull requests focused and use Conventional Commit titles.

## Development

Use Python from .python-version and create an isolated virtual environment.
Install the hash-locked development requirements.
Run the commands in [.github/copilot-instructions.md](.github/copilot-instructions.md) and the applicable consumer tests.

## Validation

Test successful and failing callers when a workflow's public behavior changes.
Retain source locations and actual command output for any reported defect.
Before a commit run `gitleaks git --staged --redact`.
Before a push run `gitleaks git --redact --log-opts='origin/main..HEAD'`.
Never include credentials or caller-private data.

## Pull requests

Explain the affected workflow, caller impact, validation evidence, and any untested live integration.
Update workflow contracts and CHANGELOG.md under Unreleased.
Use a normal pull request and leave acceptance claims unchecked until verified.
