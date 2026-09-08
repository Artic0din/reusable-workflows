# Consumer setup

## Choose and pin a revision

Review the library pull request or release and select its full commit SHA.
Use that exact SHA in the external job-level uses reference.
For linter.yml, also set tooling-ref to the same value; both references must change together.
GitHub Actions does not follow repository redirects, so references use the permanent Artic0din/reusable-workflows namespace.

The executable local calls in [validate-self.yml](../.github/workflows/validate-self.yml) demonstrate each input.
The external pilot is maintained as a separate consumer pull request.
A public library can be called from public or private projects when their Actions policy permits it.

## Keep the caller's contract

Keep existing events, concurrency controls, permissions, and language-specific checks.
Wrap shared jobs with caller-owned aggregate jobs when existing branch rules require stable names.
An aggregate must run with always() and explicitly require success from every required dependency; skipped jobs must not become a green result.
Inspect actual GitHub check contexts before changing rulesets or merging a migration.

Keep generated-asset runtime checks local even when sharing the rebuild comparison.
Keep Copilot setup local and preserve its exact job identifier.
Copy this library's setup only for a Python workflow-library project; Node applications need their own lockfile installation and browser tools where applicable.

## Install skills

Copy only selected .github/skills folders and adapt references to the caller.
README work uses readme-docs and optionally the linked readme-specialist agent.
Instruction accuracy uses refresh-instructions and preserves existing heading structure.
The GitHub Actions skill contains library-specific references; rebuild its commands from the caller's actual workflows rather than copying it unchanged.
Existing strong project instructions should be retained.

## Dependency maintenance

Keep a local Dependabot github-actions entry so external reusable-workflow references receive updates.
Use release-associated SHAs with same-line version comments once releases exist.
Review both workflow and tooling-ref updates together.
Configure only the package ecosystems that exist in the caller.
Keep major updates separate from minor/patch groups.

Dependency auto-merge is a separate opt-in.
The caller must configure effective strict rules, thread resolution, squash merge, and auto-merge.
Keep the caller's target-event entrypoint and pin the shared workflow to reviewed code.
Do not automatically approve dependency reviews.

## Updates and rollback

Validate a library release against its self-tests and a representative consumer before broad adoption.
Open consumer PRs for revision changes and preserve required-check contexts.
Rollback by reverting the consumer's workflow and tooling-ref pins together to a previously verified commit.
Changes to inputs, permissions, output checks, or result semantics require a documented migration.
Never publish a release or enable privileged behavior solely because YAML parsing passed.
