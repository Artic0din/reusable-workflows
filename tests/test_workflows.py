"""Run the actual workflow shell steps against isolated consumer repositories."""
import os
from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
