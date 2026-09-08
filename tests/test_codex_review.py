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
                 event: dict | None = None, previous_statuses: list | None = None,
                 later_base: str = "main", extra_pulls: list | None = None,
                 later_extra_pulls: list | None = None, initial_head: str = HEAD
                 ) -> tuple[subprocess.CompletedProcess[str], list]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = {"comments": comments, "resolved_sha": resolved_sha,
                       "later_head": later_head, "fail_comments": fail_comments,
                       "draft": draft, "state": state, "fail_statuses": fail_statuses,
                       "previous_statuses": previous_statuses or [], "later_base": later_base,
                       "initial_head": initial_head,
                       "extra_pulls": extra_pulls or [],
                       "later_extra_pulls": extra_pulls or [] if later_extra_pulls is None else later_extra_pulls}
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
    sha = fixture['initial_head'] if count == 0 else fixture['later_head']
    print(json.dumps({'number': 1, 'state': fixture['state'], 'draft': fixture['draft'],
                      'head': {'sha': sha}, 'base': {'ref': 'main' if count == 0 else fixture['later_base'],
                                                   'repo': {'full_name': 'fixture/repo'}}}))
elif '/pulls?' in endpoint:
    counter = root / 'list-count'
    count = int(counter.read_text()) if counter.exists() else 0
    counter.write_text(str(count + 1))
    pulls = [{'number': 1, 'state': fixture['state'], 'draft': fixture['draft'],
              'head': {'sha': fixture['initial_head'] if count == 0 else fixture['later_head']},
              'base': {'ref': 'main' if count == 0 else fixture['later_base'],
                       'repo': {'full_name': 'fixture/repo'}}}]
    pulls += fixture['extra_pulls'] if count == 0 else fixture['later_extra_pulls']
    print(json.dumps([[pull for pull in pulls if pull['state'] == 'open']]))
elif '/comments?' in endpoint:
    if fixture['fail_comments']:
        sys.exit(1)
    number = int(endpoint.split('/issues/')[1].split('/')[0])
    comments = fixture['comments'] if number == 1 else next(
        pull['comments'] for pull in fixture['extra_pulls'] if pull['number'] == number)
    print(json.dumps(comments))
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

    def test_same_second_completion_cannot_establish_request_order(self) -> None:
        for completed in (REVIEWED_AT, "2026-09-09T01:00:00.999999Z"):
            _, statuses = self.run_gate([[summary(reviewed_at=completed), request(created_at=REVIEWED_AT)]])
            self.assertEqual(statuses[-1]["state"], "pending")
        _, statuses = self.run_gate([[summary(reviewed_at="2026-09-09T01:00:01Z"),
                                     request(created_at=REVIEWED_AT)]])
        self.assertEqual(statuses[-1]["state"], "success")

    def test_base_change_requires_fresh_review_but_title_edit_does_not(self) -> None:
        event = {"action": "edited", "pull_request": {"updated_at": "2026-09-09T02:00:00Z"},
                 "changes": {"base": {"ref": {"from": "main"}}}}
        _, statuses = self.run_gate([[summary()]], event=event)
        self.assertEqual(statuses[-1]["state"], "pending")
        _, later = self.run_gate([[summary()]], previous_statuses=statuses)
        self.assertEqual(later[-1]["state"], "pending")
        event["changes"] = {"title": {"from": "Old title"}}
        _, statuses = self.run_gate([[summary()]], event=event)
        self.assertEqual(statuses[-1]["state"], "success")

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
            forged = copy.deepcopy(next(item for item in statuses if "[pr:1 request:" in item["description"]))
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

    def test_event_request_is_preserved_before_draft_or_api_failure(self) -> None:
        for kwargs in ({"draft": True}, {"fail_comments": True}):
            _, statuses = self.run_gate([[summary()]], event={"action": "deleted", "comment": request()}, **kwargs)
            self.assertIn("[pr:1 request:2026-09-09T02:00:00Z]", statuses[0]["description"])
            _, later = self.run_gate([[summary()]], previous_statuses=statuses)
            self.assertEqual(later[-1]["state"], "pending")

    def test_retarget_during_refresh_cannot_publish_success(self) -> None:
        _, statuses = self.run_gate([[summary()]], later_base="release")
        self.assertNotIn("success", [item["state"] for item in statuses])

    def test_shared_head_requires_all_open_pull_requests_to_finish(self) -> None:
        other = {"number": 2, "state": "open", "draft": False, "head": {"sha": HEAD},
                 "base": {"ref": "release", "repo": {"full_name": "fixture/repo"}}, "comments": [[]]}
        _, statuses = self.run_gate([[summary()]], extra_pulls=[other])
        self.assertEqual(statuses[-1]["state"], "pending")
        other["comments"] = [[summary()]]
        result, statuses = self.run_gate([[summary()]], extra_pulls=[other])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(statuses[-1]["state"], "success")
        other["draft"] = True
        _, statuses = self.run_gate([[summary()]], extra_pulls=[other])
        self.assertEqual(statuses[-1]["state"], "pending")
        other["head"]["sha"] = "b" * 40
        _, statuses = self.run_gate([[summary()]], extra_pulls=[other])
        self.assertEqual(statuses[-1]["state"], "success")

    def test_new_shared_head_pull_request_during_refresh_stays_pending(self) -> None:
        other = {"number": 2, "state": "open", "draft": False, "head": {"sha": HEAD},
                 "base": {"ref": "release", "repo": {"full_name": "fixture/repo"}}, "comments": [[]]}
        _, statuses = self.run_gate([[summary()]], later_extra_pulls=[other])
        self.assertNotIn("success", [item["state"] for item in statuses])

    def test_closed_pull_refreshes_remaining_shared_head(self) -> None:
        other = {"number": 2, "state": "open", "draft": False, "head": {"sha": HEAD},
                 "base": {"ref": "release", "repo": {"full_name": "fixture/repo"}}, "comments": [[summary()]]}
        result, statuses = self.run_gate([[summary()]], state="closed", extra_pulls=[other])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(statuses)
        self.assertEqual(statuses[-1]["state"], "success")

    def test_push_refreshes_reviews_remaining_on_previous_head(self) -> None:
        other = {"number": 2, "state": "open", "draft": False, "head": {"sha": HEAD},
                 "base": {"ref": "release", "repo": {"full_name": "fixture/repo"}}, "comments": [[summary()]]}
        result, statuses = self.run_gate([[]], initial_head="b" * 40, later_head="b" * 40,
                                         extra_pulls=[other], event={"action": "synchronize", "before": HEAD})
        self.assertEqual(result.returncode, 0, result.stderr)
        previous = [item for item in statuses if item["sha"] == HEAD]
        self.assertTrue(previous)
        self.assertEqual(previous[-1]["state"], "success")
        self.assertEqual([item for item in statuses if item["sha"] == "b" * 40][-1]["state"], "pending")
