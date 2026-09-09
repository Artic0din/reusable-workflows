---
name: rollout-repositories
description: Onboard explicitly selected repositories or open reviewed shared-skill update pull requests while preserving project-specific instructions and CI.
---

# Roll out shared repository automation

Use this skill for an authorized initial rollout or shared-skill update across named repositories.
Read [consumer setup](../../../docs/consumer-setup.md), [skill updates](../../../docs/skill-updates.md), and each consumer's current instructions, contribution guide and PR template.
Keep the inventory private when it contains private repositories.

## Select and inspect

Use the authenticated GitHub account and exact owner names to enumerate active repositories and verify write access.
Exclude forks and archived repositories unless the user explicitly includes them.
Use an isolated checkout per repository, record the default branch and current head, and inspect overlapping open pull requests.
Follow required repository setup or agent lifecycle commands before editing.
Match the README agent's tools to mandatory consumer lifecycle commands; add scoped execution only where those commands require it.
Do not infer a build, license, test command or deployment permission from a template.

## Prepare changes

For onboarding, select applicable reusable workflows and pin a reviewed release commit with its version comment.
Preserve existing checks, events, runner requirements and aggregate failure handling.
Check existing dependency auto-merge paths and require manual review for shared-workflow upgrades.
Update associated workflow-contract links and version prose in the same PR as each pin change, including Dependabot PRs.
Do not advance the copied-skill manifest revision for a workflow-only change.
Select and tailor skills, retain existing stronger guidance, and record only supported managed paths in .github/reusable-skills.json.
Keep project-specific context in the consumer's documentation.

For updates, fetch the reviewed old and new library commits in this library checkout.
Run scripts/sync_skills.py against a clean consumer checkout, first to preview and then with --apply.
The command compares the old library source, the consumer's adapted file, and the new library source.
A conflict requires review; never overwrite local adaptations or insert conflict markers.
The command changes selected skills and their manifest only; it does not commit, push or merge.

## Validate and open pull requests

Read the prepared diff and follow each repository's validation and changelog policy.
Check managed skill metadata and local links with the library validator, then run applicable workflow checks and the required staged and outgoing secret scans.
Preserve generated changelog ownership where the repository requires it.
Use one feature branch and normal pull request per repository; use GitHub CLI with the operator's existing authentication.
Prepare the body from the current PR template, explain retained local adaptations, and report checks actually performed.
Check CI and review findings on the resulting head; do not merge or change branch protection as part of an update.
Report each repository's PR or exact blocker and keep issues open until implementation merges.
