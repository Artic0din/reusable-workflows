# Repository instructions

## Project overview

- This repository provides versioned GitHub Actions workflows and scoped documentation skills.
- Python tooling uses .python-version and hash-locked requirements-dev.txt.
- The npm package under tests/fixtures/npm is a consumer test fixture, not an application.
- No credentials are required for local regression tests.

## Repository layout

- .github/workflows contains reusable entrypoints and this repository's own CI and Copilot setup.
- scripts/validate_agent_config.py validates instruction metadata, scopes, and local links.
- tests exercises real workflow steps against temporary consumer repositories and fake GitHub API responses.
- .github/skills and .github/agents contain the documentation, instruction-refresh, and workflow-maintenance capabilities.
- docs/workflow-contracts.md defines inputs, permissions, limitations, and consumer setup.

## Development workflow

- Create a feature branch and a normal pull request; reference the actual issue.
- Create .venv with Python from .python-version and install requirements-dev.txt with pip --require-hashes.
- Run python -m unittest discover -s tests -v, ruff check scripts tests, yamllint --strict .github .yamllint.yml, zizmor --offline --pedantic .github, and actionlint.
- Use the actionlint version and digest in .github/actions/actionlint/Dockerfile.
- Regenerate requirements-dev.txt with uv pip compile requirements-dev.in --generate-hashes --output-file requirements-dev.txt --python-version 3.14.
- Scan staged and outgoing commits with gitleaks before committing and pushing.

## Validation practices

- Run the workflow's actual shell fragment against isolated fixtures rather than copying its logic into a test.
- Cover failures, missing inputs, empty test discovery, generated files, API errors, and concurrent PR-head changes.
- Validate custom instruction metadata and links with python scripts/validate_agent_config.py .
- The metadata validator does not evaluate model behavior or fetch external links.
- Verify actual GitHub caller runs; local parsing and fake API responses are narrower evidence.
- Preserve caller-required check names through explicit local aggregate jobs.

## Implementation conventions

- Pin external actions and consumer references to full commit SHAs, with verified version comments for released actions.
- Keep checks read-only and disable privileged features until the caller explicitly opts in.
- Recheck current Dependabot identity, signed commits, strict rules, and expected head; never approve reviews or bypass protections.
- Pass event values through environment variables, not shell interpolation.
- Keep project build commands and credentials in the caller; only supported structured inputs belong in shared APIs.
- Preserve heading structure when refreshing existing custom instructions.

## Documentation

- Document every changed workflow input, permission, limitation, and migration in the same PR.
- Add a CHANGELOG.md entry under Unreleased.
- Preserve README documentation-only scope and never invent licenses, commands, or successful validation.
