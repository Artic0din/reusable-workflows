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


def run_step(script: str, directory: Path, **values: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", "-euo", "pipefail", "-c", script], cwd=directory,
                          env=dict(os.environ, PATH=f'{Path(sys.executable).parent}{os.pathsep}{os.environ["PATH"]}',
                                   **values), capture_output=True, text=True,
                          timeout=15, check=False)


class WorkflowContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def test_baseline_rejects_empty_and_whitespace_lists(self) -> None:
        script = workflow_step("baseline.yml", "Reject an empty baseline")
        for value in ("", " , , \n", " \t"):
            self.assertNotEqual(run_step(script, self.root, REQUIRED_FILES=value).returncode, 0)
        self.assertEqual(run_step(script, self.root, REQUIRED_FILES="README.md").returncode, 0)

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

    def test_executable_tools_are_pinned_by_the_library(self) -> None:
        workflow = yaml.safe_load((ROOT / ".github/workflows/linter.yml").read_text())
        checkout = next(step for step in workflow["jobs"]["lint"]["steps"]
                        if step["name"] == "Check out versioned validation tools")
        self.assertEqual(checkout["with"]["repository"], "Artic0din/reusable-workflows")
        self.assertRegex(checkout["with"]["ref"], r"^[0-9a-f]{40}$")
        self.assertFalse(checkout["with"]["persist-credentials"])

    def test_skills_reviewer_is_current_head_bounded_and_pinned(self) -> None:
        source_text = (ROOT / ".github/workflows/skills-reviewer.md").read_text()
        frontmatter = yaml.safe_load(source_text.split("---", 2)[1])
        self.assertEqual(
            frontmatter["on"]["pull_request"]["types"],
            ["opened", "reopened", "synchronize", "ready_for_review"],
        )
        self.assertEqual(frontmatter["permissions"], {
            "contents": "read",
            "pull-requests": "read",
            "copilot-requests": "write",
        })
        self.assertEqual(frontmatter["safe-outputs"]["create-pull-request-review-comment"]["max"], 10)
        self.assertFalse(frontmatter["safe-outputs"]["noop"]["report-as-issue"])
        self.assertTrue(all(re.search(r"@[0-9a-f]{40}$", skill) for skill in frontmatter["skills"]))

        lock_text = (ROOT / ".github/workflows/skills-reviewer.lock.yml").read_text()
        self.assertIn('\"compiler_version\":\"v0.88.2\"', lock_text.splitlines()[0])
        self.assertRegex(lock_text, r"github/gh-aw-actions/setup@[0-9a-f]{40}")
        self.assertIn("cancel-in-progress: true", lock_text)
        self.assertIn(r'\"report-as-issue\":\"false\"', lock_text)
        self.assertIn("github.event.pull_request.head.repo.id == github.repository_id", lock_text)
        self.assertIn('GH_AW_REQUIRED_ROLES: "admin,maintainer,write"', lock_text)
        self.assertIn("deletion-only findings", source_text)

        actionlint = yaml.safe_load((ROOT / ".github/actionlint.yml").read_text())
        lock_ignores = actionlint["paths"][".github/workflows/skills-reviewer.lock.yml"]["ignore"]
        self.assertEqual(len(lock_ignores), 2)
        self.assertTrue(any("copilot-requests" in pattern for pattern in lock_ignores))
        self.assertTrue(any('unexpected key "queue"' in pattern for pattern in lock_ignores))

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
