"""Validate real instruction files, links and scope failures in temporary repositories."""
from pathlib import Path
import tempfile
import unittest

from scripts.validate_agent_config import validate


class AgentConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / ".github/skills/example").mkdir(parents=True)
        (self.root / ".github/instructions").mkdir()
        (self.root / "src").mkdir()

    def write(self, path: str, content: str) -> None:
        (self.root / path).write_text(content)

    def test_valid_skill_and_instruction_scope(self) -> None:
        self.write("README.md", "# Project\n")
        self.write("AGENTS.md", "Read [README](README.md).\n")
        self.write(".github/skills/example/SKILL.md",
                   "---\nname: example\ndescription: 'Explain the selected module.'\n---\n# Example\n")
        self.write("src/app.py", "value = 1\n")
        self.write(".github/instructions/python.instructions.md",
                   "---\ndescription: Python conventions\napplyTo: 'src/**/*.py'\n---\nUse types.\n")
        self.assertEqual(validate(self.root), [])

    def test_invalid_metadata_and_unmatched_scopes_fail(self) -> None:
        self.write(".github/skills/example/SKILL.md", "---\nname: wrong\ndescription: ''\n---\n")
        self.write(".github/instructions/python.instructions.md",
                   "---\ndescription: Python\napplyTo: 'missing/**/*.py'\n---\n")
        errors = validate(self.root)
        self.assertTrue(any("name" in error for error in errors))
        self.assertTrue(any("description" in error for error in errors))
        self.assertTrue(any("matches no files" in error for error in errors))

    def test_broken_local_links_fail_but_urls_and_code_examples_do_not(self) -> None:
        self.write("AGENTS.md", "[missing](docs/missing.md)\n[web](https://example.com)\n"
                   "```md\n[example](not-an-actual-file.md)\n```\n")
        errors = validate(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("docs/missing.md", errors[0])

    def test_frontmatter_errors_and_external_symlinks_are_reported(self) -> None:
        self.write(".github/skills/example/SKILL.md", "---\nname: [invalid\n---\n")
        self.assertTrue(validate(self.root))
        (self.root / ".github/skills/example/SKILL.md").unlink()
        (self.root / "AGENTS.md").symlink_to("/etc/hosts")
        self.assertTrue(any("outside" in error for error in validate(self.root)))

    def test_root_recursive_single_segment_and_brace_scopes(self) -> None:
        self.write("root.py", "value = 1\n")
        self.write("src/app.tsx", "export const value = 1;\n")
        path = ".github/instructions/code.instructions.md"
        self.write(path, "---\ndescription: Code\napplyTo: '**/*.py,src/*.{ts,tsx}'\n---\n")
        self.assertEqual(validate(self.root), [])
        (self.root / "src/nested").mkdir()
        self.write("src/nested/deep.py", "value = 1\n")
        self.write(path, "---\ndescription: Code\napplyTo: 'src/*.py'\n---\n")
        self.assertTrue(any("matches no files" in error for error in validate(self.root)))

    def test_repository_instructions_have_plain_markdown_link_validation(self) -> None:
        self.write(".github/copilot-instructions.md", "# Instructions\nRead [build](../missing.md).\n")
        errors = validate(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("missing.md", errors[0])

    def test_commas_inside_character_classes_do_not_split_scopes(self) -> None:
        self.write("src/a.py", "value = 1\n")
        self.write(".github/instructions/code.instructions.md",
                   "---\ndescription: Code\napplyTo: 'src/[a,b].py,src/a.py'\n---\n")
        self.assertEqual(validate(self.root), [])

    def test_balanced_parentheses_and_escaped_link_destinations(self) -> None:
        for filename in ("API(v2).md", "API(v2(beta)).md", "API)v2.md", "API v2.md"):
            self.write(filename, "# API\n")
        self.write("AGENTS.md", '[guide](API(v2).md)\n[nested](API(v2(beta)).md "API title")\n'
                   '[escaped](API\\)v2.md)\n[angle](<API v2.md>)\n')
        self.assertEqual(validate(self.root), [])
        self.write("AGENTS.md", "[missing](Missing(v2).md)\n")
        errors = validate(self.root)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("Missing(v2).md", errors[0])


if __name__ == "__main__":
    unittest.main()
