"""Exercise real three-way skill updates against temporary Git repositories."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sync_skills


class SyncSkillsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / 'library'
        self.consumer = self.root / 'consumer'
        self.path = '.github/skills/readme-docs/SKILL.md'
        for repository in (self.library, self.consumer):
            repository.mkdir()
            self.git(repository, 'init', '-q')
            self.git(repository, 'config', 'user.name', 'Test')
            self.git(repository, 'config', 'user.email', 'test@example.invalid')
        self.base_text = 'Shared first line\n\nStable section\n\nRepository guidance\n'
        self.write(self.library, self.path, self.base_text)
        self.base = self.commit(self.library)
        self.write(self.consumer, self.path, self.base_text)
        self.manifest = {'schema-version': 1, 'source': sync_skills.SOURCE,
                         'revision': self.base, 'files': [self.path]}
        self.write_manifest()
        self.commit(self.consumer)

    @staticmethod
    def git(repository, *args):
        return subprocess.check_output(['git', '-C', str(repository), *args], text=True).strip()

    @staticmethod
    def write(repository, path, content):
        destination = repository / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)

    def commit(self, repository):
        self.git(repository, 'add', '.')
        self.git(repository, 'commit', '-qm', 'test: fixture')
        return self.git(repository, 'rev-parse', 'HEAD')

    def write_manifest(self):
        self.write(self.consumer, sync_skills.MANIFEST, json.dumps(self.manifest))

    def update_library(self, text):
        self.write(self.library, self.path, text)
        return self.commit(self.library)

    def plan(self, revision):
        return sync_skills.prepare(self.consumer, self.library, revision)

    def test_upstream_update_is_prepared_without_writing(self):
        updated = self.base_text.replace('Shared first line', 'Updated first line')
        changes = self.plan(self.update_library(updated))
        self.assertEqual(changes[self.path], updated)
        self.assertEqual((self.consumer / self.path).read_text(), self.base_text)

    def test_non_overlapping_local_adaptation_is_preserved(self):
        local = self.base_text.replace('Repository guidance', 'Project-specific commands')
        self.write(self.consumer, self.path, local)
        changes = self.plan(self.update_library(self.base_text.replace('Shared first line', 'Updated first line')))
        self.assertIn('Updated first line', changes[self.path])
        self.assertIn('Project-specific commands', changes[self.path])

    def test_conflict_refuses_every_write(self):
        local = self.base_text.replace('Shared first line', 'Local first line')
        self.write(self.consumer, self.path, local)
        with self.assertRaisesRegex(ValueError, 'conflict'):
            self.plan(self.update_library(self.base_text.replace('Shared first line', 'Upstream first line')))
        self.assertEqual((self.consumer / self.path).read_text(), local)

    def test_same_revision_has_no_changes(self):
        self.assertEqual(self.plan(self.base), {})

    def test_release_without_skill_changes_has_no_changes(self):
        self.write(self.library, 'README.md', 'A new library release\n')
        self.assertEqual(self.plan(self.commit(self.library)), {})

    def test_unknown_and_symbolic_revisions_are_rejected(self):
        for revision in ('main', '--help', 'a' * 40):
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                self.plan(revision)

    def test_manifest_cannot_select_another_source(self):
        self.manifest['source'] = 'other/repository'
        self.write_manifest()
        with self.assertRaisesRegex(ValueError, 'source'):
            self.plan(self.base)

    def test_unmanaged_and_traversal_paths_are_rejected(self):
        for path in ('../../outside', 'AGENTS.md', '.github/workflows/ci.yml'):
            self.manifest['files'] = [path]
            self.write_manifest()
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'file'):
                self.plan(self.base)

    def test_empty_duplicate_and_non_string_paths_are_rejected(self):
        for files in ([], [self.path, self.path], [None], 'not-a-list'):
            self.manifest['files'] = files
            self.write_manifest()
            with self.subTest(files=files), self.assertRaises(ValueError):
                self.plan(self.base)

    def test_consumer_symlink_is_rejected(self):
        outside = self.root / 'outside.md'
        outside.write_text(self.base_text)
        (self.consumer / self.path).unlink()
        (self.consumer / self.path).symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.plan(self.base)

    def test_source_symlink_is_rejected(self):
        (self.library / self.path).unlink()
        (self.library / self.path).symlink_to('missing.md')
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.plan(self.commit(self.library))

    def test_missing_managed_file_is_not_recreated(self):
        (self.consumer / self.path).unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            self.plan(self.base)

    def test_successful_apply_updates_files_and_manifest(self):
        updated = self.base_text.replace('Shared first line', 'Updated first line')
        revision = self.update_library(updated)
        sync_skills.apply(self.consumer, self.plan(revision))
        self.assertEqual((self.consumer / self.path).read_text(), updated)
        self.assertEqual(json.loads((self.consumer / sync_skills.MANIFEST).read_text())['revision'], revision)

    def test_apply_refuses_dirty_consumer(self):
        revision = self.update_library(self.base_text.replace('Shared first line', 'Updated first line'))
        self.write(self.consumer, 'unrelated.txt', 'Local work\n')
        with self.assertRaisesRegex(ValueError, 'clean'):
            sync_skills.apply(self.consumer, self.plan(revision))
        self.assertEqual((self.consumer / self.path).read_text(), self.base_text)


if __name__ == '__main__':
    unittest.main()
