"""Exercise the real privileged workflow guard using a fake read-only GitHub API."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_workflows import workflow_step

HEAD = "a" * 40
CHECKS = ["Tests", "Lint"]


def bot_commit(sha: str = HEAD) -> dict[str, object]:
    return {"sha": sha, "author": {"login": "dependabot[bot]"}, "committer": {"login": "web-flow"},
            "commit": {"verification": {"verified": True}}}


def required_rules() -> list[dict[str, object]]:
    return [
        {"type": "pull_request", "parameters": {"required_review_thread_resolution": True}},
        {"type": "required_status_checks", "parameters": {
            "strict_required_status_checks_policy": True,
            "required_status_checks": [{"context": name} for name in CHECKS]}},
    ]


class DependencyGuardTests(unittest.TestCase):
    def run_guard(self, *, rules: object = None, checks: object = None,
                  commits: object = None, pull_overrides: dict[str, object] | None = None,
                  enabled: bool = True) -> subprocess.CompletedProcess[str]:
        pull = {"state": "open", "draft": False, "user": {"login": "dependabot[bot]"},
                "head": {"sha": HEAD, "repo": {"full_name": "fixture/repo"}},
                "base": {"ref": "main", "repo": {"full_name": "fixture/repo"}}, "commits": 1}
        pull.update(pull_overrides or {})
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payloads = {
                "repository": {"allow_auto_merge": enabled, "allow_squash_merge": True, "default_branch": "main"},
                "rules": required_rules() if rules is None else rules,
                "pull": pull,
                "commits": [[bot_commit()]] if commits is None else commits,
            }
            for name, value in payloads.items():
                (root / f"fixture-{name}.json").write_text(json.dumps(value))
            executable = root / "gh"
            executable.write_text('#!/bin/sh\ncase "$*" in\n'
                                  '*/commits*) cat "$FIXTURES/fixture-commits.json" ;;\n'
                                  '*/pulls/*) cat "$FIXTURES/fixture-pull.json" ;;\n'
                                  '*/rules/branches/*) cat "$FIXTURES/fixture-rules.json" ;;\n'
                                  '*) cat "$FIXTURES/fixture-repository.json" ;;\nesac\n')
            executable.chmod(0o700)
            environment = dict(os.environ, PATH=f'{root}{os.pathsep}{os.environ["PATH"]}',
                               FIXTURES=str(root), REPOSITORY="fixture/repo", BASE_BRANCH="main",
                               RUNNER_TEMP=str(root), PR_NUMBER="1", PR_HEAD_SHA=HEAD,
                               REQUIRED_CHECKS=json.dumps(CHECKS if checks is None else checks))
            return subprocess.run(
                ["bash", "-euo", "pipefail", "-c",
                 workflow_step("dependabot-automerge.yml", "Verify current merge eligibility")],
                env=environment, capture_output=True, text=True, timeout=10, check=False)

    def test_verified_bot_with_strict_rules_is_eligible(self) -> None:
        result = self.run_guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.run_guard(commits=[[bot_commit("b" * 40)], [bot_commit()]],
                                pull_overrides={"commits": 2})
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_or_non_strict_checks_and_empty_requirements_fail(self) -> None:
        for checks in ([], [""], "Tests"):
            self.assertNotEqual(self.run_guard(checks=checks).returncode, 0)
        for rules in ([], {"message": "unavailable"}, required_rules()[:1], required_rules()[1:]):
            self.assertNotEqual(self.run_guard(rules=rules).returncode, 0)
        rules = required_rules()
        rules[1]["parameters"]["strict_required_status_checks_policy"] = False
        self.assertNotEqual(self.run_guard(rules=rules).returncode, 0)
        self.assertNotEqual(self.run_guard(enabled=False).returncode, 0)

    def test_live_identity_head_and_branch_are_rechecked(self) -> None:
        cases = [
            {"user": {"login": "human"}}, {"state": "closed"}, {"draft": True},
            {"head": {"sha": "b" * 40, "repo": {"full_name": "fixture/repo"}}},
            {"head": {"sha": HEAD, "repo": {"full_name": "fork/repo"}}},
            {"base": {"ref": "different", "repo": {"full_name": "fixture/repo"}}},
        ]
        for case in cases:
            with self.subTest(case=case):
                self.assertNotEqual(self.run_guard(pull_overrides=case).returncode, 0)

    def test_unverified_human_incomplete_and_malformed_commits_fail(self) -> None:
        human = bot_commit()
        human["author"]["login"] = "human"
        unsigned = bot_commit()
        unsigned["commit"]["verification"]["verified"] = False
        for commits in ([[]], [[human]], [[unsigned]], [[bot_commit("b" * 40)]], {"message": "unavailable"}):
            self.assertNotEqual(self.run_guard(commits=commits).returncode, 0)
        self.assertNotEqual(self.run_guard(pull_overrides={"commits": 2}).returncode, 0)

    def test_verified_human_committer_cannot_impersonate_bot_author(self) -> None:
        commit = bot_commit()
        commit["committer"]["login"] = "human-collaborator"
        self.assertNotEqual(self.run_guard(commits=[[commit]]).returncode, 0)
        commit["committer"] = None
        self.assertNotEqual(self.run_guard(commits=[[commit]]).returncode, 0)
