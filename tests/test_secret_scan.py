"""Prove that the scanner command includes changes introduced only by a merge."""
from pathlib import Path
import shutil
import tempfile
import unittest

from test_workflows import run_step, workflow_step


class SecretHistoryTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("gitleaks"), "Gitleaks binary required for scanner integration")
    def test_merge_resolution_is_scanned(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        setup = run_step("""
          git init -q
          git -c user.name=Fixture -c user.email=fixture@example.invalid commit --allow-empty -qm root
          git checkout -qb side
          echo side > side.txt
          git add side.txt
          git -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm side
          git checkout -q -
          echo main > main.txt
          git add main.txt
          git -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm main
          git -c user.name=Fixture -c user.email=fixture@example.invalid merge --no-commit --no-ff side
          echo SYNTHETIC_MERGE_ONLY_MARKER > merge.txt
          git add merge.txt
          git -c user.name=Fixture -c user.email=fixture@example.invalid commit -qm merge
        """, self.root)
        self.assertEqual(setup.returncode, 0, setup.stderr)
        (self.root / ".gitleaks.toml").write_text(
            '[[rules]]\nid = "merge-fixture"\ndescription = "Synthetic test marker"\n'
            'regex = "SYNTHETIC_MERGE_ONLY_MARKER"\n')
        (self.root / "gitleaks").symlink_to(Path(shutil.which("gitleaks")).resolve())
        result = run_step(workflow_step("secret-scan.yml", "Scan history with redacted output"),
                          self.root, RUNNER_TEMP=str(self.root))
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("leaks found", result.stderr)
