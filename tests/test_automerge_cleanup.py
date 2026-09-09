"""Exercise queued auto-merge state across later failed or skipped attempts."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

import test_automerge as guard_tests

WORKFLOW = Path(__file__).resolve().parents[1] / '.github/workflows/dependabot-automerge.yml'


class AutoMergeCleanupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.state = root / 'state.json'
        self.output = root / 'output'
        self.open_pull = {'state': 'OPEN', 'headRefOid': guard_tests.HEAD, 'autoMergeRequest': None,
                          'author': {'login': 'app/dependabot', 'is_bot': True}, 'isCrossRepository': False}
        self.state.write_text(json.dumps(self.open_pull))
        executable = root / 'gh'
        executable.write_text('#!/bin/sh\nset -eu\ncase "$*" in\n'
                              '"api repos/fixture/repo --jq .default_branch") printf "%s\\n" main ;;\n'
                              '"api repos/fixture/repo/pulls/1")\n'
                              '  jq --arg repo "$REPOSITORY" \'{state: (.state | ascii_downcase), draft: false,\n'
                              '    user: {login: "dependabot[bot]"}, head: {sha: .headRefOid, repo: {full_name: $repo}},\n'
                              '    base: {ref: "main", repo: {full_name: $repo}}}\' "$STATE_FILE" ;;\n'
                              'pr\\ view*)\n'
                              '  test "${READ_FAILURE:-false}" = false || exit 31\n'
                              '  cat "$STATE_FILE" ;;\n'
                              'pr\\ merge\\ --auto*)\n'
                              '  jq \'.autoMergeRequest = {enabled_by: "bot"}\' "$STATE_FILE" > "$STATE_FILE.next"\n'
                              '  mv "$STATE_FILE.next" "$STATE_FILE"\n'
                              '  test "${QUEUE_FAILURE:-false}" = false || exit 32 ;;\n'
                              'pr\\ merge\\ --disable-auto*)\n'
                              '  test "${CLEANUP_FAILURE:-false}" = false || exit 33\n'
                              '  jq \'.autoMergeRequest = null\' "$STATE_FILE" > "$STATE_FILE.next"\n'
                              '  mv "$STATE_FILE.next" "$STATE_FILE" ;;\n'
                              '*) exit 34 ;;\nesac\n')
        executable.chmod(0o700)
        self.environment = dict(os.environ, PATH=f'{root}{os.pathsep}{os.environ["PATH"]}',
                                STATE_FILE=str(self.state), RUNNER_TEMP=str(root),
                                REPOSITORY='fixture/repo', PR_NUMBER='1', PR_HEAD_SHA='a' * 40, BASE_BRANCH='main',
                                PR_URL='https://github.com/fixture/repo/pull/1', GITHUB_OUTPUT=str(self.output),
                                DEPENDENCY_NAMES='actions/checkout', UPDATE_TYPE='version-update:semver-patch',
                                MAINTAINER_CHANGES='false')
        self.steps = yaml.safe_load(WORKFLOW.read_text())['jobs']['dependency']['steps']

    def run_shell(self, script: str, **environment: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(['bash', '-euo', 'pipefail', '-c', script],
                              env=self.environment | environment, capture_output=True,
                              text=True, timeout=5, check=False)

    def queue(self, **environment: str) -> subprocess.CompletedProcess[str]:
        step = next(step for step in self.steps if step['name'] == 'Queue eligible update')
        return self.run_shell(step['run'], **environment)

    def cleanup(self, outcome: str, **environment: str) -> subprocess.CompletedProcess[str]:
        step = next(step for step in self.steps if step['name'] == 'Cancel automatic merges requiring manual review')
        fields = (dict(line.split('=', 1) for line in self.output.read_text().splitlines())
                  if self.output.exists() else {})
        return self.run_shell(step['run'], QUEUE_OUTCOME=outcome, QUEUE_ELIGIBLE=fields.get('eligible', ''),
                              METADATA_OUTCOME='skipped' if outcome == 'skipped' else 'success',
                              JOB_STATUS=outcome if outcome in ('failure', 'cancelled') else 'success', **environment)

    def test_queued_update_is_cancelled_after_a_human_committer_fails_guard(self) -> None:
        self.assertEqual(self.queue().returncode, 0)
        self.assertIsNotNone(json.loads(self.state.read_text())['autoMergeRequest'])
        commit = guard_tests.bot_commit()
        commit['committer']['login'] = 'human-collaborator'
        result = guard_tests.DependencyGuardTests().run_guard(commits=[[commit]])
        self.assertNotEqual(result.returncode, 0)
        self.cleanup('skipped')
        self.assertIsNone(json.loads(self.state.read_text())['autoMergeRequest'])

    def test_failed_cancelled_or_skipped_queue_is_cancelled(self) -> None:
        for outcome in ('failure', 'cancelled', 'skipped'):
            with self.subTest(outcome=outcome):
                self.assertEqual(self.queue().returncode, 0)
                result = self.cleanup(outcome)
                self.assertIsNotNone(result)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIsNone(json.loads(self.state.read_text())['autoMergeRequest'])

    def test_successful_queue_is_preserved(self) -> None:
        self.assertEqual(self.queue().returncode, 0)
        result = self.cleanup('success')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNotNone(json.loads(self.state.read_text())['autoMergeRequest'])

    def test_stale_run_cannot_cancel_a_newer_head_queue(self) -> None:
        self.assertEqual(self.queue().returncode, 0)
        state = json.loads(self.state.read_text())
        state['headRefOid'] = 'b' * 40
        self.state.write_text(json.dumps(state))
        result = self.cleanup('skipped', CLEANUP_FAILURE='true')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.state.read_text()), state)

    def test_queue_and_cleanup_share_a_non_cancelling_pr_lock(self) -> None:
        job = yaml.safe_load(WORKFLOW.read_text())['jobs']['dependency']
        self.assertEqual(job.get('concurrency'), {
            'group': 'reusable-dependabot-automerge-${{ github.repository }}-${{ github.event.pull_request.number }}',
            'cancel-in-progress': False,
            'queue': 'max',
        })

    def test_delayed_older_run_does_not_evict_current_head_cleanup(self) -> None:
        self.assertEqual(self.queue().returncode, 0)
        current_head = 'd' * 40
        state = json.loads(self.state.read_text())
        state['headRefOid'] = current_head
        self.state.write_text(json.dumps(state))
        concurrency = yaml.safe_load(WORKFLOW.read_text())['jobs']['dependency']['concurrency']
        pending: list[str] = []
        # Model GitHub's documented queue replacement while an older run is active.
        for head in (current_head, 'c' * 40):
            if concurrency.get('queue', 'single') == 'single':
                pending.clear()
            pending.append(head)
        for head in ('b' * 40, *pending):
            result = self.cleanup('failure', PR_HEAD_SHA=head)
            self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIsNone(json.loads(self.state.read_text())['autoMergeRequest'])

    def test_ambiguous_queue_failure_is_cancelled(self) -> None:
        self.assertNotEqual(self.queue(QUEUE_FAILURE='true').returncode, 0)
        self.cleanup('failure')
        self.assertIsNone(json.loads(self.state.read_text())['autoMergeRequest'])

    def test_already_disabled_or_closed_pull_needs_no_write(self) -> None:
        for state in (self.open_pull, self.open_pull | {'state': 'CLOSED', 'autoMergeRequest': {'enabled_by': 'bot'}}):
            with self.subTest(state=state):
                self.state.write_text(json.dumps(state))
                result = self.cleanup('skipped', CLEANUP_FAILURE='true')
                self.assertIsNotNone(result)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(self.state.read_text()), state)

    def test_cleanup_api_failures_are_not_suppressed(self) -> None:
        self.assertEqual(self.queue().returncode, 0)
        for environment in ({'READ_FAILURE': 'true'}, {'CLEANUP_FAILURE': 'true'}):
            with self.subTest(environment=environment):
                result = self.cleanup('skipped', **environment)
                self.assertIsNotNone(result)
                self.assertNotEqual(result.returncode, 0)

    def test_malformed_cleanup_response_is_not_an_empty_success(self) -> None:
        for payload in ({'message': 'unavailable'}, {}, [],
                        self.open_pull | {'autoMergeRequest': False}):
            with self.subTest(payload=payload):
                self.state.write_text(json.dumps(payload))
                result = self.cleanup('skipped')
                self.assertIsNotNone(result)
                self.assertNotEqual(result.returncode, 0)
