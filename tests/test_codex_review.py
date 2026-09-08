"""Exercise the actual review-gate workflow against an isolated GitHub API fake."""
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_workflows import workflow_step

HEAD = "a" * 40
REVIEWED_AT = "2026-09-09T01:00:00Z"


def summary(*, status: str = "Completed", sha: str = HEAD[:7],
            reviewed_at: str = REVIEWED_AT) -> dict[str, object]:
    return {
        "id": 10,
        "user": {"id": 199175422, "login": "chatgpt-codex-connector[bot]", "type": "Bot"},
        "body": "<!-- codex-pull-request-review-summary -->\n"
                f'| 📝 **Code Review** | ✅ **{status}** <relative-time datetime="{reviewed_at}">'
                f"{reviewed_at}</relative-time> | `{sha}` | New commits |\n"
                f"| 🔒 **Security Review** | ✅ **Completed** | `{HEAD[:7]}` | PR opened |",
        "updated_at": REVIEWED_AT,
        "html_url": "https://github.com/fixture/repo/pull/1#issuecomment-10",
    }


def request(*, association: str = "OWNER", created_at: str = "2026-09-09T02:00:00Z") -> dict[str, object]:
    return {"id": 20, "user": {"id": 1, "login": "owner", "type": "User"},
            "author_association": association, "body": "@codex review",
            "created_at": created_at, "updated_at": created_at}


class CodexReviewGateTests(unittest.TestCase):
    def run_gate(self, comments: object, *, resolved_sha: str = HEAD,
                 later_head: str = HEAD, fail_comments: bool = False,
                 draft: bool = False, state: str = "open", fail_statuses: int = 0,
                 event: dict | None = None, previous_statuses: list | None = None
                 ) -> tuple[subprocess.CompletedProcess[str], list]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = {"comments": comments, "resolved_sha": resolved_sha,
                       "later_head": later_head, "fail_comments": fail_comments,
                       "draft": draft, "state": state, "fail_statuses": fail_statuses,
                       "previous_statuses": previous_statuses or []}
            (root / "fixture.json").write_text(json.dumps(fixture))
            (root / "event.json").write_text(json.dumps(event or {}))
            fake = root / "gh"
            fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['FIXTURES'])
fixture = json.loads((root / 'fixture.json').read_text())
args = sys.argv[1:]
endpoint = next(arg for arg in args if arg.startswith('repos/'))
if '/statuses/' in endpoint:
    counter = root / 'status-count'
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    if count < fixture['fail_statuses']:
        sys.exit(1)
    payload = json.load(sys.stdin)
    payload['sha'] = endpoint.rsplit('/', 1)[1]
    payload['creator'] = {'id': 41898282, 'login': 'github-actions[bot]', 'type': 'Bot'}
    with (root / 'statuses.jsonl').open('a') as output:
        output.write(json.dumps(payload) + '\\n')
    print('{}')
elif endpoint.endswith('/pulls/1'):
    count_path = root / 'pull-count'
    count = int(count_path.read_text()) if count_path.exists() else 0
    count_path.write_text(str(count + 1))
    sha = 'a' * 40 if count == 0 else fixture['later_head']
    print(json.dumps({'state': fixture['state'], 'draft': fixture['draft'],
                      'head': {'sha': sha}, 'base': {'repo': {'full_name': 'fixture/repo'}}}))
elif '/comments?' in endpoint:
    if fixture['fail_comments']:
        sys.exit(1)
    print(json.dumps(fixture['comments']))
elif '/statuses?' in endpoint:
    print(json.dumps([fixture['previous_statuses']]))
elif '/commits/' in endpoint:
    print(json.dumps({'sha': fixture['resolved_sha']}))
else:
    sys.exit('Unexpected API call: ' + endpoint)
""")
            fake.chmod(0o700)
            environment = dict(os.environ, PATH=f'{root}{os.pathsep}{os.environ["PATH"]}',
                               FIXTURES=str(root), REPOSITORY="fixture/repo", PR_NUMBER="1",
                               GITHUB_EVENT_PATH=str(root / "event.json"),
                               RUN_URL="https://github.com/fixture/repo/actions/runs/1")
            result = subprocess.run(
                ["bash", "-euo", "pipefail", "-c", workflow_step("codex-review-gate.yml", "Check Codex completion")],
                env=environment, capture_output=True, text=True, timeout=10, check=False)
            path = root / "statuses.jsonl"
            statuses = [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []
            return result, statuses

    def test_completed_current_head_passes_after_pending(self) -> None:
        result, statuses = self.run_gate([[summary()]])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([s["state"] for s in statuses], ["pending", "success"])
        self.assertTrue(all(s["sha"] == HEAD and s["context"] == "Codex review complete" for s in statuses))

    def test_missing_running_stale_and_security_only_do_not_pass(self) -> None:
        security_only = summary()
        security_only["body"] = "<!-- codex-pull-request-review-summary -->\n" + str(security_only["body"]).splitlines()[-1]
        for comments in ([[]], [[summary(status="Running")]], [[summary(sha="b" * 7)]], [[security_only]]):
            with self.subTest(comments=comments):
                result, statuses = self.run_gate(comments)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(statuses[-1]["state"], "pending")

    def test_spoofed_bot_identity_cannot_satisfy_gate(self) -> None:
        for key, value in (("id", 1), ("login", "other[bot]"), ("type", "User")):
            forged = summary()
            forged["user"][key] = value
            _, statuses = self.run_gate([[forged]])
            self.assertEqual(statuses[-1]["state"], "pending")

    def test_unknown_failed_malformed_and_duplicate_rows_fail_closed(self) -> None:
        invalid_date = summary(reviewed_at="not-a-date")
        duplicate = summary()
        duplicate["body"] += "\n" + str(duplicate["body"]).splitlines()[1]
        ambiguous = summary()
        ambiguous["body"] = str(ambiguous["body"]).replace("**Completed**", "**Completed** **Failed**", 1)
        for comment in (summary(status="Failed"), summary(status="Cancelled"),
                        summary(status="Unexpected"), invalid_date, duplicate, ambiguous):
            with self.subTest(comment=comment):
                _, statuses = self.run_gate([[comment]])
                self.assertNotEqual(statuses[-1]["state"], "success")

    def test_manual_request_invalidates_older_completion_only_for_trusted_users(self) -> None:
        _, statuses = self.run_gate([[summary(), request()]])
        self.assertEqual(statuses[-1]["state"], "pending")
        _, statuses = self.run_gate([[summary(), request(association="NONE")]])
        self.assertEqual(statuses[-1]["state"], "success")
        _, statuses = self.run_gate([[summary(reviewed_at="2026-09-09T03:00:00Z"), request()]])
        self.assertEqual(statuses[-1]["state"], "success")

    def test_edited_request_uses_the_edit_time(self) -> None:
        edited = request(created_at="2026-09-08T00:00:00Z")
        edited["updated_at"] = "2026-09-09T02:00:00Z"
        _, statuses = self.run_gate([[summary(), edited]])
        self.assertEqual(statuses[-1]["state"], "pending")

    def test_deleted_request_survives_later_refreshes_until_review_completes(self) -> None:
        event = {"action": "deleted", "comment": request()}
        result, statuses = self.run_gate([[summary()]], event=event)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(statuses[-1]["state"], "pending")
        _, later = self.run_gate([[summary()]], previous_statuses=statuses)
        self.assertEqual(later[-1]["state"], "pending")
        _, completed = self.run_gate([[summary(reviewed_at="2026-09-09T03:00:00Z")]],
                                     previous_statuses=later)
        self.assertEqual(completed[-1]["state"], "success")

    def test_editing_away_request_and_spoofed_request_history(self) -> None:
        edited = request()
        edited["body"] = "Request removed"
        event = {"action": "edited", "comment": edited,
                 "changes": {"body": {"from": "@codex review"}}}
        _, statuses = self.run_gate([[summary()]], event=event)
        self.assertEqual(statuses[-1]["state"], "pending")
        for key, value in (("id", 1), ("login", "other[bot]"), ("type", "User")):
            forged = copy.deepcopy(statuses[-1])
            forged["creator"][key] = value
            _, later = self.run_gate([[summary()]], previous_statuses=[forged])
            self.assertEqual(later[-1]["state"], "success")

    def test_transient_initial_status_failure_retries_and_can_fail_closed(self) -> None:
        result, statuses = self.run_gate([[summary()]], fail_statuses=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([item["state"] for item in statuses], ["pending", "success"])
        result, statuses = self.run_gate([[summary()]], fail_statuses=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(statuses[-1]["state"], "error")

    def test_latest_summary_and_every_page_are_considered(self) -> None:
        old = summary(status="Running")
        old["updated_at"] = "2026-09-08T00:00:00Z"
        _, statuses = self.run_gate([[old], [summary()]])
        self.assertEqual(statuses[-1]["state"], "success")
        latest = copy.deepcopy(old)
        latest["updated_at"] = "2026-09-10T00:00:00Z"
        _, statuses = self.run_gate([[summary()], [latest]])
        self.assertEqual(statuses[-1]["state"], "pending")

    def test_resolution_must_equal_full_current_sha(self) -> None:
        _, statuses = self.run_gate([[summary()]], resolved_sha="b" * 40)
        self.assertNotEqual(statuses[-1]["state"], "success")

    def test_head_change_and_api_failure_never_publish_success(self) -> None:
        for kwargs in ({"later_head": "b" * 40}, {"fail_comments": True}):
            _, statuses = self.run_gate([[summary()]], **kwargs)
            self.assertTrue(statuses)
            self.assertNotIn("success", [s["state"] for s in statuses])

    def test_draft_waits_and_closed_pull_request_is_ignored(self) -> None:
        _, statuses = self.run_gate([[summary()]], draft=True)
        self.assertEqual(statuses[-1]["state"], "pending")
        _, statuses = self.run_gate([[summary()]], state="closed")
        self.assertEqual(statuses, [])
