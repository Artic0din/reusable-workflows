# Reusable workflows

Shared GitHub Actions checks and scoped agent skills for repositories maintained under Artic0din and plaintextlab.
Each caller selects the checks it needs and retains its own application behavior, events, required checks, and secrets.

## Installation

Read [workflow contracts](docs/workflow-contracts.md) before adding a caller.
Reusable workflows live directly in .github/workflows and use workflow_call.
Reference this public repository with a full reviewed commit SHA.
The workflow library owns the immutable revision of its executable validation tools.
The validator checks the caller checkout and loads its own code from a separately pinned library checkout.

Public and private repositories can consume this public library when their Actions policy permits it.
Consuming the library does not change the visibility of the caller.
No local API key or paid service is needed for offline validation.
CodeQL eligibility and dependency auto-merge activation remain caller-owned.

## Usage

| Capability | Entrypoint |
| --- | --- |
| Configurable required files | [.github/workflows/baseline.yml](.github/workflows/baseline.yml) |
| Python unittest and npm scripts | [.github/workflows/ci.yml](.github/workflows/ci.yml) |
| Checked-in generated output | [.github/workflows/check-dist.yml](.github/workflows/check-dist.yml) |
| Workflow syntax/security and agent configuration | [.github/workflows/linter.yml](.github/workflows/linter.yml) |
| Explicitly enabled CodeQL | [.github/workflows/codeql-analysis.yml](.github/workflows/codeql-analysis.yml) |
| Verified, opt-in Dependabot auto-merge | [.github/workflows/dependabot-automerge.yml](.github/workflows/dependabot-automerge.yml) |
| Redacted history secret scanning | [.github/workflows/secret-scan.yml](.github/workflows/secret-scan.yml) |

[validate-self.yml](.github/workflows/validate-self.yml) contains executable caller examples, including Python/npm and generated-output fixtures.
[Consumer setup](docs/consumer-setup.md) covers external wiring, Copilot, Dependabot, updates, and rollback.

## Agent skills

The [README specialist](.github/agents/readme-specialist.agent.md) edits requested documentation only.
The [instruction-refresh skill](.github/skills/refresh-instructions/SKILL.md) corrects repository instructions without changing heading text, levels, or order.
[Workflow maintenance](.github/skills/github-actions/SKILL.md) covers caller contracts and validation.
[Test-gap review](.github/skills/test-gap-audit/SKILL.md) reports scoped, evidence-backed coverage gaps without editing files.

Skills are not installed merely by calling a workflow.
Copy the selected skill folders into the caller's .github/skills, adapt repository-specific references, and review the diff.
The README agent also needs its linked readme-docs skill.
For agents that do not discover .github/skills, add explicit links in the caller's existing instruction file.
Do not copy this repository's entire agent policy over a project's instructions.

## Development

Use the Python version declared in .python-version:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --require-hashes -r requirements-dev.txt
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/validate_agent_config.py .
.venv/bin/ruff check scripts tests
.venv/bin/yamllint --strict .github .yamllint.yml
.venv/bin/zizmor --offline --pedantic .github
```

Run actionlint at the version pinned in [.github/actions/actionlint/Dockerfile](.github/actions/actionlint/Dockerfile), then git diff --check.
Tests require Git, Bash, and jq on PATH.
Node from .node-version is needed for the npm consumer fixture.
Local tests do not prove GitHub permissions, successful CodeQL uploads, or live dependency merges.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).
Workflow inputs and check behavior are public contracts; test failure paths and document migrations.
Record changes in [CHANGELOG.md](CHANGELOG.md).

## License

[MIT](LICENSE).
Workflow patterns were adapted from Chris Reddington's [validate-file-exists](https://github.com/chrisreddington/validate-file-exists) and [reusable-workflows](https://github.com/chrisreddington/reusable-workflows) repositories.
His copyright notice is retained for adapted portions.
