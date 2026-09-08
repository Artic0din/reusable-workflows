"""Exercise both automatic merge eligibility and cancellation with a fake GitHub CLI."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]
QUEUE_NAME = "Queue eligible update"
CANCEL_NAME = "Cancel automatic merges requiring manual review"
PR_URL = "https://github.com/example/repository/pull/1"
HEAD_SHA = "0123456789abcdef0123456789abcdef01234567"


class SharedWorkflowAutomergeTests(unittest.TestCase):
    def steps(self) -> tuple[dict[str, object], dict[str, object]]:
        workflow = yaml.safe_load((ROOT / ".github/workflows/dependabot-automerge.yml").read_text())
        steps = workflow["jobs"]["dependency"]["steps"]
        return (
            next(step for step in steps if step["name"] == QUEUE_NAME),
            next(step for step in steps if step["name"] == CANCEL_NAME),
        )

    def run_policy(
        self, overrides: dict[str, str] | None = None
    ) -> tuple[subprocess.CompletedProcess[str] | None, subprocess.CompletedProcess[str], list[list[str]]]:
        queue, cancel = self.steps()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake = root / "gh"
            fake.write_text(
                f"#!{sys.executable}\n"
                "import json, os, pathlib, sys\n"
                "args = sys.argv[1:]\n"
                "root = pathlib.Path(os.environ['RUNNER_TEMP'])\n"
                "with (root / 'calls').open('a') as out:\n"
                "    out.write(json.dumps(args) + '\\n')\n"
                "if args[:2] == ['pr', 'view']:\n"
                "    state = os.environ['GH_AUTO_STATE']\n"
                "    if '--jq' in args:\n"
                "        print(state)\n"
                "    else:\n"
                "        request = {} if state == 'true' else None if state == 'false' else state\n"
                "        print(json.dumps({'autoMergeRequest': request,\n"
                "            'headRefOid': os.environ.get('GH_LIVE_HEAD', os.environ['PR_HEAD_SHA']),\n"
                "            'author': {'login': os.environ.get('GH_LIVE_AUTHOR', 'app/dependabot'), 'is_bot': True},\n"
                "            'isCrossRepository': os.environ.get('GH_LIVE_CROSS', 'false') == 'true',\n"
                "            'state': os.environ.get('GH_LIVE_STATE', 'OPEN')}))\n"
                "    sys.exit(int(os.environ['GH_READ_EXIT']))\n"
                "if args[:2] == ['pr', 'merge']:\n"
                "    key = 'GH_CANCEL_EXIT' if '--disable-auto' in args else 'GH_MERGE_EXIT'\n"
                "    sys.exit(int(os.environ[key]))\n"
                "if args[0] == 'api':\n"
                "    if any('/commits' in arg for arg in args):\n"
                "        commit = {'sha': os.environ['PR_HEAD_SHA'],\n"
                "                  'author': {'login': 'dependabot[bot]'},\n"
                "                  'commit': {'verification': {'verified': True}}}\n"
                "        print(json.dumps([[commit]]))\n"
                "    elif any('/rules/branches/' in arg for arg in args):\n"
                "        checks = [{'context': c, 'integration_id': 15368}\n"
                "                  for c in ['baseline', 'pytest', 'ha-runtime', 'lint', 'Analyze (python)']]\n"
                "        checks.append({'context': 'CodeQL', 'integration_id': 57789})\n"
                "        print(json.dumps([{'type': 'required_status_checks',\n"
                "                           'parameters': {'required_status_checks': checks}}]))\n"
                "    else:\n"
                "        print('true')\n"
                "    sys.exit(0)\n"
                "sys.exit(37)\n"
            )
            fake.chmod(0o700)
            env = {
                **os.environ,
                "PATH": str(root) + os.pathsep + os.environ["PATH"],
                "RUNNER_TEMP": str(root),
                "GITHUB_OUTPUT": str(root / "output"),
                "GITHUB_REPOSITORY": "example/repository",
                "GH_REPO": "example/repository",
                "GH_AUTO_STATE": "true",
                "GH_READ_EXIT": "0",
                "GH_CANCEL_EXIT": "0",
                "GH_MERGE_EXIT": "0",
                "DEPENDENCY_NAMES": "actions/checkout",
                "METADATA_OUTCOME": "success",
                "JOB_STATUS": "success",
                "UPDATE_TYPE": "version-update:semver-patch",
                "PACKAGE_ECOSYSTEM": "github_actions",
                "MAINTAINER_CHANGES": "false",
                "CODEQL_ADVANCED_SETUP": "false",
                "PR_URL": PR_URL,
                "PR_HEAD_SHA": HEAD_SHA,
                "PR_HEAD": HEAD_SHA,
                "PR_NUMBER": "1",
                **(overrides or {}),
            }

            def execute(script: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", script],
                    env=env,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )

            if env.get("RUN_INITIAL") == "true":
                workflow = yaml.safe_load((ROOT / ".github/workflows/dependabot-automerge.yml").read_text())
                initial_step = workflow["jobs"]["dependency"]["steps"][0]
                initial_result = execute(initial_step["run"])
                if initial_result.returncode != 0:
                    env["JOB_STATUS"] = "failure"

            result = None
            env["QUEUE_OUTCOME"] = "skipped"
            if env["JOB_STATUS"] == env["METADATA_OUTCOME"] == "success":
                result = execute(queue["run"])
                env["QUEUE_OUTCOME"] = "success" if result.returncode == 0 else "failure"
                if result.returncode:
                    env["JOB_STATUS"] = "failure"
            output = root / "output"
            fields = dict(line.split("=", 1) for line in output.read_text().splitlines()) if output.exists() else {}
            env["QUEUE_ELIGIBLE"] = fields.get("eligible", "")
            if env.get("CANCEL_AFTER_QUEUE") == "true":
                env["JOB_STATUS"] = "cancelled"
                env["QUEUE_OUTCOME"] = "cancelled"
            cleanup = execute(cancel["run"])
            calls_path = root / "calls"
            calls = [json.loads(line) for line in calls_path.read_text().splitlines()] if calls_path.exists() else []
            return result, cleanup, calls

    def test_ordinary_patch_and_minor_updates_reach_head_matched_queue(self) -> None:
        for update in ("version-update:semver-patch", "version-update:semver-minor"):
            with self.subTest(update=update):
                queue, cleanup, calls = self.run_policy({"UPDATE_TYPE": update})
                self.assertIsNotNone(queue)
                self.assertEqual(queue.returncode, 0, queue.stderr)
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                merges = [call for call in calls if call[:2] == ["pr", "merge"]]
                self.assertEqual(len(merges), 1, calls)
                self.assertIn("--auto", merges[0])
                self.assertIn("--squash", merges[0])
                self.assertEqual(merges[0][merges[0].index("--match-head-commit") + 1], HEAD_SHA)
                self.assertFalse(any(call[:2] == ["pr", "view"] for call in calls), calls)

    def test_ineligible_updates_cannot_queue_or_retain_an_existing_queue(self) -> None:
        cases = [
            {"DEPENDENCY_NAMES": ""},
            {"DEPENDENCY_NAMES": "Artic0din/reusable-workflows"},
            {"DEPENDENCY_NAMES": "actions/checkout,artic0din/reusable-workflows"},
            {"UPDATE_TYPE": "version-update:semver-major"},
            {"UPDATE_TYPE": ""},
        ]
        cases += [{"MAINTAINER_CHANGES": "true"}, {"MAINTAINER_CHANGES": ""}]
        for metadata in cases:
            for state in ("true", "false"):
                with self.subTest(metadata=metadata, state=state):
                    queue, cleanup, calls = self.run_policy({**metadata, "GH_AUTO_STATE": state})
                    self.assertIsNotNone(queue)
                    self.assertEqual(queue.returncode, 0, queue.stderr)
                    self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                    self.assertFalse(any("--auto" in call for call in calls), calls)
                    self.assertTrue(any(call[:2] == ["pr", "view"] for call in calls), calls)
                    cancellations = [call for call in calls if "--disable-auto" in call]
                    self.assertEqual(
                        cancellations, [["pr", "merge", "--disable-auto", PR_URL]] if state == "true" else []
                    )

    def test_failed_or_cancelled_steps_revoke_prior_queue(self) -> None:
        for outcome, status in (
            ("failure", "failure"),
            ("failure", "success"),
            ("cancelled", "cancelled"),
            ("skipped", "failure"),
            ("", "success"),
            ("success", "cancelled"),
        ):
            with self.subTest(outcome=outcome, status=status):
                queue, cleanup, calls = self.run_policy({"METADATA_OUTCOME": outcome, "JOB_STATUS": status})
                self.assertIsNone(queue)
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                self.assertIn(["pr", "merge", "--disable-auto", PR_URL], calls)
                self.assertFalse(any("--auto" in call for call in calls), calls)

    def test_queue_command_failure_revokes_an_earlier_request(self) -> None:
        queue, cleanup, calls = self.run_policy({"GH_MERGE_EXIT": "7"})
        self.assertIsNotNone(queue)
        self.assertEqual(queue.returncode, 7)
        self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
        self.assertEqual(calls[-1], ["pr", "merge", "--disable-auto", PR_URL])

    def test_cancellation_after_eligibility_still_revokes_queue(self) -> None:
        _, cleanup, calls = self.run_policy({"CANCEL_AFTER_QUEUE": "true"})
        self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
        self.assertEqual(calls[-1], ["pr", "merge", "--disable-auto", PR_URL])

    def test_lookup_and_cancellation_failures_fail_closed(self) -> None:
        for values in ({"GH_READ_EXIT": "7"}, {"GH_AUTO_STATE": "unknown"}, {"GH_CANCEL_EXIT": "9"}):
            with self.subTest(values=values):
                _, cleanup, calls = self.run_policy({"DEPENDENCY_NAMES": "", **values})
                self.assertNotEqual(cleanup.returncode, 0)
                if values.get("GH_READ_EXIT"):
                    self.assertIn("Cannot read existing auto-merge state.", cleanup.stderr)
                self.assertFalse(any("--auto" in call for call in calls), calls)

    def test_disabled_automation_can_cancel_an_existing_queue(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/dependabot-automerge.yml").read_text())
        job = workflow["jobs"]["dependency"]
        self.assertNotIn("inputs.enabled", job["if"])
        for step in job["steps"]:
            if step.get("id") == "enable-automerge" or step["name"] in {
                CANCEL_NAME,
                "Clear previous automatic merge request",
            }:
                continue
            self.assertEqual(step["if"], "${{ inputs.enabled }}")
        queue, cleanup, calls = self.run_policy({"METADATA_OUTCOME": "skipped"})
        self.assertIsNone(queue)
        self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
        self.assertEqual(
            calls,
            [
                ["pr", "view", PR_URL, "--json", "autoMergeRequest,headRefOid,author,isCrossRepository,state"],
                ["pr", "merge", "--disable-auto", PR_URL],
            ],
        )

    def test_stale_events_do_not_cancel_current_merge_requests(self) -> None:
        for values in (
            {"GH_LIVE_HEAD": "b" * 40},
            {"GH_LIVE_AUTHOR": "human"},
            {"GH_LIVE_CROSS": "true"},
            {"GH_LIVE_STATE": "CLOSED"},
        ):
            with self.subTest(values=values):
                queue, cleanup, calls = self.run_policy(
                    {"RUN_INITIAL": "true", "METADATA_OUTCOME": "skipped", **values}
                )
                self.assertIsNone(queue)
                self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
                self.assertEqual(len(calls), 2, calls)
                self.assertTrue(all(call[:2] == ["pr", "view"] for call in calls), calls)

    def test_previous_request_is_cleared_before_verification(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/dependabot-automerge.yml").read_text())
        initial_step = workflow["jobs"]["dependency"]["steps"][0]
        self.assertEqual(initial_step["name"], "Clear previous automatic merge request")
        self.assertNotIn("if", initial_step)
        self.assertNotIn("--auto", initial_step["run"])
        for state in ("true", "false"):
            _, cleanup, calls = self.run_policy({"RUN_INITIAL": "true", "GH_AUTO_STATE": state})
            self.assertEqual(cleanup.returncode, 0, cleanup.stderr)
            self.assertEqual(calls[0][:2], ["pr", "view"])
            if state == "true":
                self.assertEqual(calls[1], ["pr", "merge", "--disable-auto", PR_URL])
            self.assertIn("--auto", calls[-1])
        for failure in ({"GH_READ_EXIT": "7"}, {"GH_CANCEL_EXIT": "9"}):
            queue, cleanup, calls = self.run_policy({"RUN_INITIAL": "true", **failure})
            self.assertIsNone(queue)
            self.assertNotEqual(cleanup.returncode, 0)
            self.assertFalse(any("--auto" in call for call in calls), calls)

    def test_cleanup_cannot_enable_merging_and_uses_queue_result(self) -> None:
        queue, cleanup = self.steps()
        self.assertEqual(queue["if"], "${{ success() && steps.metadata.outcome == 'success' }}")
        self.assertEqual(cleanup["if"], "${{ always() }}")
        self.assertNotIn("--auto", cleanup["run"])
        self.assertEqual(cleanup["env"]["QUEUE_OUTCOME"], "${{ steps.enable-automerge.outcome }}")
        self.assertEqual(cleanup["env"]["QUEUE_ELIGIBLE"], "${{ steps.enable-automerge.outputs.eligible }}")


if __name__ == "__main__":
    unittest.main()
