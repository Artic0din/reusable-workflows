# Consumer setup

## Reference the library

Use `@main` in the external job-level uses reference.
`@main` resolves to the tip of this repository's default branch each time the caller runs, so no bump pull request is needed in each consumer.
A caller that needs a change frozen can still use a full commit SHA. That caller stays on the named workflow commit until a pull request in its own repository advances the reference.
A pinned reference freezes the workflow definition only. `linter.yml` checks its validation bundle out of this library at `main`, so the scripts, the dependency lock and the actionlint image it runs still track the tip even for a pinned caller.
Nothing else in the library reaches a pinned caller.
The library checks out its own executable tools; no second caller input is required.
GitHub Actions does not follow repository redirects, so references use the permanent Artic0din/reusable-workflows namespace.

A caller whose organization enables "Require actions to be pinned to a full-length commit SHA" may be unable to consume these workflows.
GitHub documents that setting as exempting reusable workflows referenced by tag, but not what it does to the action references inside a called workflow, which run in the caller's context.
This library now references its actions by floating major ref, so a caller under that policy should verify a real run before adopting it. No current consumer enables it.

The executable local calls in [validate-self.yml](../.github/workflows/validate-self.yml) demonstrate each input.
The external pilot is maintained as a separate consumer pull request.
A public library can be called from public or private projects when their Actions policy permits it.

This complete caller tracks `@main` with a minimal file baseline.
Change the required file list to match the consumer.

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
    uses: Artic0din/reusable-workflows/.github/workflows/baseline.yml@main
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

## Install the engineering skills reviewer

Copy `.github/workflows/skills-reviewer.md` and `.github/workflows/skills-reviewer.lock.yml` into the consumer.
Add the lock-file rule to the consumer's `.gitattributes` without replacing existing attributes.
If `.github/aw/actions-lock.json` already exists, merge the `github/gh-aw-actions/setup@v0.88.2` entry and reject a conflicting value; copy the complete file only when the consumer has no action lock.
Review the Markdown source against the consumer's instructions and adapt only the prompt or trigger policy.
Do not edit the generated lock.
The strict generated activation guard supports same-repository pull requests initiated by actors with write, maintain, or admin access; document a narrower caller policy and do not advertise fork review.

If the consumer uses actionlint 1.7.12, merge this repository's two `.github/actionlint.yml` ignores for the skills reviewer lock.
They suppress only the unknown `copilot-requests` permission and generated concurrency `queue` key.
For a newer actionlint release, confirm both constructs are recognized before omitting those exceptions.
If the consumer applies formatting or source-oriented security rules to generated YAML, add narrow path-specific exclusions for the lock while retaining gh-aw compilation, actionlint, and all checks on the maintained source.

When the source changes, install the gh-aw CLI version recorded in the lock metadata and regenerate from the repository root:

```sh
gh aw compile skills-reviewer --approve --action-mode action --action-tag v0.88.2 --validate --no-check-update
```

Commit the source and regenerated files together.
The consumer needs GitHub Copilot agentic workflow access; the generated workflow uses the caller's `GITHUB_TOKEN` and declares its own least-privilege job permissions.
Run a real pull request before treating its check as required.
Keep existing human, Copilot, Codex, and required-thread policies until the new reviewer has been observed on both a clean change and an actionable finding.

The copied workflow pair is separate from `.github/reusable-skills.json` because that manifest tracks tailored instruction skills only.
Record its library source revision in the rollout pull-request body and use the normal workflow update path for later releases.

## Dependency maintenance

A `@main` reference never changes in the caller, so Dependabot has nothing to bump and this library needs no github-actions entry there.
Keep a local Dependabot github-actions entry for any third-party actions the caller uses directly.
Review workflow and validation-tool changes together; both reach callers from `main` on their next run.
Update matching workflow-contract links in consumer guides and skills in the same PR, including Dependabot PRs.
Keep copied-skill manifest revisions unchanged for workflow-only updates; those revisions record the skills' merge bases.
Exclude shared-workflow updates from existing dependency auto-merge paths until they receive the required review and validation.
Configure only the package ecosystems that exist in the caller.
Keep major updates separate from minor/patch groups.

Dependency auto-merge is a separate opt-in.
The caller must configure effective strict rules, thread resolution, squash merge, and auto-merge.
Do not enable this capability on a branch that requires GitHub's merge queue; preflight rejects that configuration.
If an older revision was used with a merge queue, inspect and remove any existing queue entries through GitHub before adopting this revision.
Before enabling a merge queue later, disable this capability and clear earlier automatic merge requests and queue entries; a configuration change during an active run can race its preflight check.
The shared dependency job serializes attempts per repository and pull request with `queue: max` and `cancel-in-progress: false`.
No caller lock is required.
If the caller retains its own concurrency group, use a different group name with `queue: max` and `cancel-in-progress: false` so it cannot discard events before they reach the shared job.
See the [Dependabot contract](workflow-contracts.md#dependabot) for the reserved group name, queue limit and recovery requirements.
The workflow revokes an earlier automatic merge request whenever the complete eligibility decision no longer succeeds.
It clears earlier requests before verification begins and enables a new request only after success.
Keep invoking the workflow with enabled set to false when disabling automatic merges so the next matching Dependabot event can revoke an earlier request.
Keep the caller's target-event entrypoint and reference the shared workflow at `@main`.
Do not automatically approve dependency reviews.

## Updates and rollback

Validate a change against this library's self-tests and a representative consumer before merging it to the default branch, because every `@main` caller runs it from that point.
A change that alters a check context also needs matching ruleset or branch-protection updates in each consumer; a `@main` caller adopts every other change without a pull request.
Roll back by reverting the change in this library; every `@main` caller runs the reverted code from that point.
A caller that chose a full commit SHA rolls back the workflow definition by reverting that reference.
That does not roll back `linter.yml`'s validation bundle, which resolves `main` on every run regardless of how the caller references the workflow.
A bad change to the scripts, the dependency lock or the actionlint image has to be reverted in this library; there is no caller-side rollback for it.
Changes to inputs, permissions, output checks, or result semantics require a documented migration.
Never publish a release or enable privileged behavior solely because YAML parsing passed.
