"""Run the actual workflow shell steps against isolated consumer repositories."""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[1]


def workflow_step(filename: str, name: str) -> str:
    workflow = yaml.safe_load((ROOT / ".github/workflows" / filename).read_text())
    return next(step["run"] for job in workflow["jobs"].values()
                for step in job.get("steps", []) if step.get("name") == name)


def agent_workflow_step(filename: str, name: str) -> str:
    source_text = (ROOT / ".github/workflows" / filename).read_text()
    frontmatter = yaml.safe_load(source_text.split("---", 2)[1])
    return next(step["run"] for step in frontmatter["steps"] if step.get("name") == name)


def run_step(script: str, directory: Path, **values: str) -> subprocess.CompletedProcess[str]:
    environment = dict(os.environ)
    environment["PATH"] = f'{Path(sys.executable).parent}{os.pathsep}{os.environ["PATH"]}'
    environment.update(values)
    return subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=directory,
                          env=environment, capture_output=True, text=True,
                          timeout=15, check=False)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_baseline_rejects_empty_and_whitespace_lists(self) -> None:
        script = workflow_step("baseline.yml", "Validate required files")
        for value in ("", " , , \n", " \t"):
            self.assertNotEqual(run_step(script, self.root, REQUIRED_FILES=value).returncode, 0)
        (self.root / "README.md").write_text("fixture\n")
        self.assertEqual(run_step(script, self.root, REQUIRED_FILES="README.md").returncode, 0)

    def test_baseline_accepts_literal_paths_and_ignores_empty_entries(self) -> None:
        script = workflow_step("baseline.yml", "Validate required files")
        (self.root / "docs").mkdir()
        (self.root / "docs/with spaces.md").write_text("fixture\n")
        (self.root / "$(touch injected)").write_text("literal filename\n")
        (self.root / "linked").symlink_to("docs/with spaces.md")
        result = run_step(script, self.root, REQUIRED_FILES=(
            " docs, docs/with spaces.md, , $(touch injected), linked, \n"
        ))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / "injected").exists())

    def test_baseline_reports_all_missing_paths_and_rejects_dangling_links(self) -> None:
        script = workflow_step("baseline.yml", "Validate required files")
        (self.root / "README.md").write_text("fixture\n")
        (self.root / "dangling").symlink_to("absent-target")
        result = run_step(script, self.root, REQUIRED_FILES="README.md, missing, dangling")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing", result.stderr)
        self.assertIn("dangling", result.stderr)

    def test_baseline_cannot_import_caller_modules(self) -> None:
        script = workflow_step("baseline.yml", "Validate required files")
        (self.root / "pathlib.py").write_text(
            "open('imported-caller-code', 'w').write('executed')\n"
            "class Path:\n"
            "    def __init__(self, path): pass\n"
            "    def exists(self): return True\n"
        )
        result = run_step(script, self.root, REQUIRED_FILES="missing", PYTHONPATH=str(self.root))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.root / "imported-caller-code").exists())
        self.assertIn("missing", result.stderr)

    def test_python_runner_propagates_failure_and_rejects_zero_tests(self) -> None:
        (self.root / "tests").mkdir()
        script = workflow_step("ci.yml", "Run Python tests")
        environment = {"TEST_DIRECTORY": "tests", "TEST_PATTERN": "test*.py"}
        self.assertNotEqual(run_step(script, self.root, **environment).returncode, 0)
        test_file = self.root / "tests/test_sample.py"
        test_file.write_text("import unittest\nclass Example(unittest.TestCase):\n"
                             "    def test_value(self):\n        self.assertEqual(2 + 2, 4)\n")
        self.assertEqual(run_step(script, self.root, **environment).returncode, 0)
        test_file.write_text(test_file.read_text().replace("2 + 2, 4", "2 + 2, 99"))
        result = run_step(script, self.root, PYTHONDONTWRITEBYTECODE="1", **environment)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("AssertionError", result.stderr)

    def test_ci_rejects_disabling_all_runners(self) -> None:
        script = workflow_step("ci.yml", "Require at least one test runner")
        self.assertNotEqual(run_step(script, self.root, PYTHON_ENABLED="false", NPM_ENABLED="false").returncode, 0)
        self.assertEqual(run_step(script, self.root, PYTHON_ENABLED="true", NPM_ENABLED="false").returncode, 0)

    def initialize_output(self) -> None:
        run_step("git init -q", self.root)
        (self.root / "dist").mkdir()
        (self.root / "dist/main.js").write_text("export const answer = 42;\n")
        (self.root / ".gitignore").write_text("dist/*.map\n")
        result = run_step("git add . && git -c user.name=Fixture -c user.email=fixture@example.invalid "
                          "commit -qm fixture", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_generated_check_detects_changes_deletions_and_untracked_files(self) -> None:
        self.initialize_output()
        script = workflow_step("check-dist.yml", "Verify generated output is unchanged")
        self.assertEqual(run_step(script, self.root, OUTPUT_PATH="dist").returncode, 0)
        target = self.root / "dist/main.js"
        target.write_text("changed\n")
        self.assertNotEqual(run_step(script, self.root, OUTPUT_PATH="dist").returncode, 0)
        target.unlink()
        self.assertNotEqual(run_step(script, self.root, OUTPUT_PATH="dist").returncode, 0)
        target.write_text("export const answer = 42;\n")
        for name in ("new.js", "ignored.map"):
            extra = self.root / "dist" / name
            extra.write_text("new output\n")
            self.assertNotEqual(run_step(script, self.root, OUTPUT_PATH="dist").returncode, 0)
            extra.unlink()

    def test_output_path_rejects_escape_missing_and_untracked_directories(self) -> None:
        self.initialize_output()
        script = workflow_step("check-dist.yml", "Validate output directory")
        self.assertEqual(run_step(script, self.root, OUTPUT_PATH="dist").returncode, 0)
        (self.root / "empty").mkdir()
        (self.root / "link").symlink_to(self.root.parent, target_is_directory=True)
        for value in ("", ".", "..", str(self.root / "dist"), "missing", "empty", "link"):
            with self.subTest(value=value):
                self.assertNotEqual(run_step(script, self.root, OUTPUT_PATH=value).returncode, 0)

    def test_executable_tools_are_library_owned(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/linter.yml").read_text())
        checkout = next(step for step in workflow["jobs"]["lint"]["steps"]
                        if step["name"] == "Check out versioned validation tools")
        self.assertEqual(checkout["with"]["repository"], "Artic0din/reusable-workflows")
        # The revision is a literal the library controls, never a caller input; callers
        # already receive the workflow from main, so the bundle tracks main rather than a pin.
        self.assertEqual(checkout["with"]["ref"], "main")
        self.assertFalse(checkout["with"]["persist-credentials"])

    def test_validate_self_gates_the_generated_lock(self) -> None:
        """The unit suite cannot recompute gh-aw's hash, so CI must run the real compiler."""
        workflow = yaml.safe_load((ROOT / ".github/workflows/validate-self.yml").read_text())
        steps = workflow["jobs"]["source"]["steps"]
        setup = next(step for step in steps if "gh-aw/actions/setup-cli" in str(step.get("uses", "")))
        lock_metadata = json.loads(
            (ROOT / ".github/workflows/skills-reviewer.lock.yml").read_text()
            .splitlines()[0].removeprefix("# gh-aw-metadata: "))
        self.assertEqual(setup["with"]["version"], lock_metadata["compiler_version"])
        gate = next(step for step in steps if "gh aw compile" in str(step.get("run", "")))
        self.assertIn("--validate", gate["run"])
        self.assertIn("git diff --exit-code", gate["run"])
        self.assertIn(".github/workflows/skills-reviewer.lock.yml", gate["run"])
        self.assertIn(".github/aw/actions-lock.json", gate["run"])

    def test_skills_reviewer_is_current_head_bounded_and_pinned(self) -> None:
        source_text = (ROOT / ".github/workflows/skills-reviewer.md").read_text()
        frontmatter = yaml.safe_load(source_text.split("---", 2)[1])
        self.assertEqual(
            frontmatter["on"]["pull_request"]["types"],
            ["opened", "reopened", "synchronize", "ready_for_review", "edited", "closed"],
        )
        self.assertEqual(frontmatter["permissions"], {
            "contents": "read",
            "pull-requests": "read",
            "copilot-requests": "write",
        })
        self.assertEqual(
            frontmatter["concurrency"]["group"],
            "gh-aw-${{ github.workflow }}-${{ github.event.action != 'edited' && github.event.pull_request.number || github.event.action == 'edited' && github.event.changes.base.ref.from && github.event.pull_request.number || github.run_id }}",
        )
        self.assertEqual(frontmatter["max-turns"], 45)
        self.assertTrue(frontmatter["concurrency"]["cancel-in-progress"])
        self.assertEqual(frontmatter["safe-outputs"]["create-pull-request-review-comment"]["max"], 10)
        self.assertEqual(frontmatter["safe-outputs"]["add-comment"]["max"], 1)
        self.assertNotIn("submit-pull-request-review", frontmatter["safe-outputs"])
        self.assertFalse(frontmatter["safe-outputs"]["noop"]["report-as-issue"])
        self.assertFalse(frontmatter["safe-outputs"]["report-failure-as-issue"])
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", skill) for skill in frontmatter["skills"]))
        self.assertIn("Prefetch pull-request review context", source_text)
        self.assertIn("/tmp/gh-aw/agent/pr-diff.patch", source_text)
        self.assertIn("compare/$current_base_sha...$current_head_sha", source_text)
        self.assertIn(r"\.github\/workflows\/.*\.lock\.yml", source_text)
        self.assertIn(r"\.github\/aw\/actions-lock\.json", source_text)
        self.assertIn(r"b\/([^\/]+\/)*(package-lock\.json", source_text)
        self.assertIn("pr-issue-comments.json", source_text)
        self.assertIn("steps.set-runtime-paths.outputs.GH_AW_SAFE_OUTPUTS", source_text)
        self.assertIn('mkdir -p "$(dirname "$GH_AW_SAFE_OUTPUTS")"', source_text)
        self.assertIn("BASE_CHANGED_FROM", source_text)
        self.assertIn("current_state", source_text)
        self.assertIn("Do not install packages, run tests", source_text)
        self.assertIn("exit 1", source_text)

        lock_text = (ROOT / ".github/workflows/skills-reviewer.lock.yml").read_text()
        lock_metadata = json.loads(lock_text.splitlines()[0].removeprefix("# gh-aw-metadata: "))
        self.assertEqual(lock_metadata["compiler_version"], "v0.88.2")
        # The hash itself is not recomputed here: gh-aw hashes its own canonical form,
        # not the raw frontmatter, so reimplementing it drifts from the compiler. The
        # `gh aw compile` plus `git diff --exit-code` gate in validate-self.yml is
        # authoritative for that, and test_validate_self_gates_the_generated_lock
        # below asserts that gate exists.
        self.assertRegex(lock_metadata["frontmatter_hash"], r"^[0-9a-f]{64}$")
        # Assert a real source-to-lock link instead, so a hand-edited lock is caught
        # without the gate. A dependency bot silently reverted this value in the
        # generated file while the source kept the intended one.
        self.assertEqual(
            frontmatter["max-turns"],
            int(re.search(r"^\s*GH_AW_MAX_TURNS: (\d+)$", lock_text, re.MULTILINE).group(1)),
        )
        self.assertIn(f'"maxRuns":{frontmatter["max-turns"]}', lock_text)
        self.assertRegex(lock_text, r"github/gh-aw-actions/setup@[0-9a-f]{40}")
        self.assertIn("cancel-in-progress: true", lock_text)
        self.assertIn('github.event.action != \'edited\'', lock_text)
        self.assertIn('github.event.action == \'edited\' && github.event.changes.base.ref.from', lock_text)
        self.assertIn(r'\"report-as-issue\":\"false\"', lock_text)
        self.assertIn("GH_AW_FAILURE_REPORT_AS_ISSUE: \"false\"", lock_text)
        self.assertIn("github.event.pull_request.head.repo.id == github.repository_id", lock_text)
        self.assertIn('GH_AW_REQUIRED_ROLES: "admin,maintainer,write"', lock_text)
        self.assertIn("deletion-only findings", source_text)
        self.assertNotIn("submit_pull_request_review", lock_text)

        actionlint = yaml.safe_load((ROOT / ".github/actionlint.yml").read_text())
        lock_ignores = actionlint["paths"][".github/workflows/skills-reviewer.lock.yml"]["ignore"]
        self.assertEqual(len(lock_ignores), 2)
        self.assertTrue(any("copilot-requests" in pattern for pattern in lock_ignores))
        self.assertTrue(any('unexpected key "queue"' in pattern for pattern in lock_ignores))

    def test_skills_reviewer_prefetch_guards_state_and_filters_nested_locks(self) -> None:
        script = agent_workflow_step("skills-reviewer.md", "Prefetch pull-request review context")
        fake_bin = self.root / "bin"
        fake_bin.mkdir()
        fake_gh = fake_bin / "gh"
        fake_gh.write_text("""#!/usr/bin/env bash
set -euo pipefail
if [ "$1 $2" = "pr view" ]; then
  cat "$PR_META_FIXTURE"
  exit 0
fi
printf '%s\\n' "$*" >> "$GH_CALL_LOG"
case "$*" in
  *compare/*) cat "$PR_DIFF_FIXTURE" ;;
  *) printf '[]\\n' ;;
esac
""")
        fake_gh.chmod(0o755)
        metadata = self.root / "pr-meta.json"
        patch = self.root / "pr.patch"
        call_log = self.root / "gh-calls.log"
        patch.write_text(
            "diff --git a/web/package-lock.json b/web/package-lock.json\n"
            "--- a/web/package-lock.json\n+++ b/web/package-lock.json\n@@ -1 +1 @@\n-old\n+new\n"
            "diff --git a/src/app.py b/src/app.py\n"
            "--- a/src/app.py\n+++ b/src/app.py\n@@ -1 +1 @@\n-old\n+new\n"
        )

        def execute(state: str, action: str, trigger_head: str = "head",
                    base_changed_from: str = "") -> subprocess.CompletedProcess[str]:
            metadata.write_text(json.dumps({
                "state": state,
                "baseRefOid": "base",
                "headRefOid": "head",
            }))
            safe_outputs = self.root / action / "outputs.jsonl"
            return run_step(
                script,
                self.root,
                PATH=f'{fake_bin}{os.pathsep}{os.environ["PATH"]}',
                PR_NUMBER="7",
                PR_REPOSITORY="example/repo",
                TRIGGER_HEAD_SHA=trigger_head,
                EVENT_ACTION=action,
                BASE_CHANGED_FROM=base_changed_from,
                GH_AW_SAFE_OUTPUTS=str(safe_outputs),
                PR_META_FIXTURE=str(metadata),
                PR_DIFF_FIXTURE=str(patch),
                GH_CALL_LOG=str(call_log),
            )

        for state, action, trigger_head in (
            ("CLOSED", "closed", "head"),
            ("OPEN", "edited", "head"),
            ("OPEN", "synchronize", "old-head"),
        ):
            with self.subTest(state=state, action=action):
                result = execute(state, action, trigger_head)
                self.assertNotEqual(result.returncode, 0, result.stderr)
                safe_outputs = self.root / action / "outputs.jsonl"
                self.assertEqual(json.loads(safe_outputs.read_text())["noop"].keys(), {"message"})

        result = execute("OPEN", "edited", base_changed_from="main")
        self.assertEqual(result.returncode, 0, result.stderr)
        context = Path("/tmp/gh-aw/agent")
        diff = (context / "pr-diff.patch").read_text()
        self.assertNotIn("package-lock.json", diff)
        self.assertIn("src/app.py", diff)
        self.assertTrue((context / "pr-issue-comments.json").is_file())
        self.assertIn("issues/7/comments", call_log.read_text())

    def test_yaml_paths_accept_trailing_newlines_and_reject_empty_lists(self) -> None:
        (self.root / ".yamllint.yml").write_text("extends: default\nrules:\n  document-start: disable\n")
        (self.root / "first.yml").write_text("name: first\n")
        (self.root / "second.yml").write_text("name: second\n")
        script = workflow_step("linter.yml", "Validate caller YAML")
        for paths in ("first.yml", "first.yml\nsecond.yml\n", "\nfirst.yml\n\n"):
            result = run_step(script, self.root, YAML_PATHS=paths, YAML_CONFIG=".yamllint.yml")
            self.assertEqual(result.returncode, 0, result.stderr)
        for paths in ("", "\n \n", "missing.yml\n"):
            self.assertNotEqual(run_step(script, self.root, YAML_PATHS=paths,
                                        YAML_CONFIG=".yamllint.yml").returncode, 0)

    def test_generated_directory_symlink_cannot_bypass_verification(self) -> None:
        self.initialize_output()
        (self.root / "alias").symlink_to("dist", target_is_directory=True)
        run_step("git add alias && git -c user.name=Fixture -c user.email=fixture@example.invalid "
                 "commit -qm symlink", self.root)
        script = workflow_step("check-dist.yml", "Validate output directory")
        self.assertNotEqual(run_step(script, self.root, OUTPUT_PATH="alias").returncode, 0)

    def test_nested_generated_symlinks_are_rejected_before_and_after_build(self) -> None:
        self.initialize_output()
        (self.root / "assets").mkdir()
        (self.root / "assets/icon.txt").write_text("original\n")
        link = self.root / "dist/assets"
        link.symlink_to("../assets", target_is_directory=True)
        result = run_step("git add . && git -c user.name=Fixture -c user.email=fixture@example.invalid "
                          "commit -qm nested-link", self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        (link / "icon.txt").write_text("changed through symlink\n")
        for name in ("Validate output directory", "Revalidate output directory"):
            with self.subTest(step=name):
                result = run_step(workflow_step("check-dist.yml", name), self.root, OUTPUT_PATH="dist")
                self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_build_cannot_introduce_directory_file_or_dangling_symlinks(self) -> None:
        self.initialize_output()
        workflow = yaml.safe_load((ROOT / ".github/workflows/check-dist.yml").read_text())
        steps = workflow["jobs"]["generated"]["steps"]
        build_index = next(index for index, step in enumerate(steps) if step["name"] == "Regenerate output")
        post_build = "\n".join(step["run"] for step in steps[build_index + 1:])
        for target in ("../dist", "../.gitignore", "../missing"):
            with self.subTest(target=target):
                self.assertEqual(run_step(workflow_step("check-dist.yml", "Validate output directory"),
                                          self.root, OUTPUT_PATH="dist").returncode, 0)
                link = self.root / "dist/link"
                link.symlink_to(target)
                try:
                    result = run_step(post_build, self.root, OUTPUT_PATH="dist")
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("nested symlinks", result.stderr)
                finally:
                    link.unlink()

    def test_npm_script_names_cannot_be_interpreted_as_options(self) -> None:
        (self.root / "script.cjs").write_text("require('fs').writeFileSync('executed', 'yes');\n")
        for filename, step_name, variable in (
            ("ci.yml", "Run npm tests", "TEST_SCRIPT"),
            ("ci.yml", "Build npm project", "BUILD_SCRIPT"),
            ("check-dist.yml", "Regenerate output", "BUILD_SCRIPT"),
        ):
            script = workflow_step(filename, step_name)
            for name in ("test", "--help", "--version", "--silent"):
                with self.subTest(step=step_name, script=name):
                    (self.root / "package.json").write_text(json.dumps({"scripts": {name: "node script.cjs"}}))
                    result = run_step(script, self.root, **{variable: name})
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertTrue((self.root / "executed").exists(), result.stdout)
                    (self.root / "executed").unlink()
                    (self.root / "package.json").write_text('{"scripts": {}}')
                    result = run_step(script, self.root, **{variable: name})
                    self.assertNotEqual(result.returncode, 0, result.stdout)


if __name__ == "__main__":
    unittest.main()
