# Consumer setup

## Choose and pin a revision

Review the library pull request or release and select its full commit SHA.
Use that exact SHA in the external job-level uses reference.
The library pins its own executable tools; no second caller input is required.
GitHub Actions does not follow repository redirects, so references use the permanent Artic0din/reusable-workflows namespace.

The executable local calls in [validate-self.yml](../.github/workflows/validate-self.yml) demonstrate each input.
The external pilot is maintained as a separate consumer pull request.
A public library can be called from public or private projects when their Actions policy permits it.

This complete caller uses the v1.0.0 release revision and a minimal file baseline.
Change the required file list to match the consumer, and review newer library revisions before adopting them.

```yaml
name: Repository checks
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
jobs:
  baseline:
    uses: Artic0din/reusable-workflows/.github/workflows/baseline.yml@c913ad3e22a42c75bfcf0029448cda48dc546ff1  # v1.0.0
    with:
      required-files: README.md, .gitignore
```

If branch rules already require a check name, use the aggregate pattern below and retain that exact name.

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
Record selected source files and their original revision in the consumer's .github/reusable-skills.json.
Use [skill updates](skill-updates.md) and the [rollout skill](../.github/skills/rollout-repositories/SKILL.md) to prepare later update PRs while preserving local adaptations.

## Dependency maintenance

Keep a local Dependabot github-actions entry so external reusable-workflow references receive updates.
Use release-associated SHAs with same-line version comments once releases exist.
Review workflow changes and any embedded validation-tool pin updates together.
Update matching version prose and workflow-contract links in consumer guides and skills in the same PR, including Dependabot PRs.
Keep copied-skill manifest revisions unchanged for workflow-only updates; those revisions record the skills' merge bases.
Exclude shared-workflow updates from existing dependency auto-merge paths until they receive the required review and validation.
Configure only the package ecosystems that exist in the caller.
Keep major updates separate from minor/patch groups.

Dependency auto-merge is a separate opt-in.
The caller must configure effective strict rules, thread resolution, squash merge, and auto-merge.
Serialize the privileged caller per pull request and set cancel-in-progress to false.
The workflow revokes an earlier automatic merge request whenever the complete eligibility decision no longer succeeds.
Keep invoking the workflow with enabled set to false when disabling automatic merges so the next matching Dependabot event can revoke an earlier request.
Keep the caller's target-event entrypoint and pin the shared workflow to reviewed code.
Do not automatically approve dependency reviews.

## Updates and rollback

Validate a library release against its self-tests and a representative consumer before broad adoption.
Open consumer PRs for revision changes and preserve required-check contexts.
Rollback by reverting the consumer's workflow pins to a previously verified commit.
Changes to inputs, permissions, output checks, or result semantics require a documented migration.
Never publish a release or enable privileged behavior solely because YAML parsing passed.
