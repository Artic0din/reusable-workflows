# Updating tailored skills

Workflow references and copied skills have separate update paths.
Applying updates rejects managed files with assume-unchanged or skip-worktree index flags, including selected files with no incoming change.
Reviewed source revisions are read without Git replacement objects or implicit network fetches.
Dependabot updates versioned workflow pins.
Those PRs must also update matching workflow-version prose and contract links in consumer guides and skills.
They must preserve the copied-skill manifest revision unless copied skills are updated through the three-way merge process.
The [rollout skill](../.github/skills/rollout-repositories/SKILL.md) prepares skill-update pull requests using the maintainer's existing GitHub CLI session.
It is explicitly invoked; installation does not schedule work, create cross-repository credentials, or merge changes.

## Record adoption

Copy selected skill files from a reviewed library release and adapt them to the consumer.
Retain repository instructions and existing stronger skills.
Record the original library revision, not the consumer commit or a hash of its adapted text.

This minimal .github/reusable-skills.json tracks only the README skill:

```json
{
  "schema-version": 1,
  "source": "Artic0din/reusable-workflows",
  "revision": "c913ad3e22a42c75bfcf0029448cda48dc546ff1",
  "files": [".github/skills/readme-docs/SKILL.md"]
}
```

Supported paths are the four original .github/skills folders' SKILL.md files and .github/agents/readme-specialist.agent.md.
Paths must match the library; an existing agent with another filename can be retained outside the managed set.
The manifest never selects application code, workflows, AGENTS.md, custom instructions or arbitrary files.
Keep consumer names, inventories and private project context in the consumer or private operator workspace.

## Prepare an update

Use a clean feature-branch checkout of the consumer.
In the library checkout, fetch and review the desired release and ensure both commits and their selected skill blobs are available locally.
Use a Git version supporting --no-lazy-fetch; partial clones must fetch needed blobs explicitly before running the helper.
Then run the script's --help and pass the exact reviewed commit with --revision:

```sh
python scripts/sync_skills.py --help
```

The first positional argument is the absolute consumer checkout path.
Without --apply, exit 0 means no selected upstream skills changed, exit 1 means a complete update is ready for review, and exit 2 means validation or merging failed.
Add --apply after reviewing the preview to write changes to a clean checkout.
The script never fetches, executes consumer commands, commits, pushes or opens a pull request itself.
Use the rollout skill to complete the consumer's checks, contribution requirements and normal GitHub PR process.

Three-way merging preserves non-overlapping repository adaptations.
Conflicting edits, missing or untracked files, symbolic or hard links, unselected paths and invalid revisions fail before writes.
The manifest and every selected file must already be tracked, including when ignore rules match them.
Reading a missing source blob fails without allowing Git to fetch it implicitly.
A release that changes no selected upstream skill produces no update.
All selected files are validated before any update is applied.
Local links and agent metadata still need validation after a successful merge; textual compatibility alone does not prove semantic compatibility.

## Rollback

Revert the consumer's skill-update commit, including its manifest revision.
Workflow rollback separately restores the previous pinned workflow revision.
Never reset unrelated consumer changes to roll back shared guidance.
