"""Prepare reviewed shared-skill updates while retaining consumer adaptations."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import tempfile

SOURCE = 'Artic0din/reusable-workflows'
MANIFEST = '.github/reusable-skills.json'
ALLOWED_FILES = frozenset({
    '.github/skills/readme-docs/SKILL.md',
    '.github/skills/refresh-instructions/SKILL.md',
    '.github/skills/github-actions/SKILL.md',
    '.github/skills/test-gap-audit/SKILL.md',
    '.github/agents/readme-specialist.agent.md',
})
REVISION = re.compile(r'[0-9a-f]{40}')


def git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(['git', '-C', str(repository), *arguments],
                            check=False, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'Git {arguments[0]} failed: {result.stderr.strip()}')
    return result.stdout


def checked_path(root: Path, relative: str) -> Path:
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'{relative}: symlink or path escapes the repository')
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink():
            raise ValueError(f'{relative}: symlinks are not managed')
    if not path.is_file():
        raise ValueError(f'{relative}: managed file is missing')
    return path


def read_manifest(root: Path) -> dict:
    manifest = json.loads(checked_path(root, MANIFEST).read_text())
    if not isinstance(manifest, dict) or set(manifest) != {'schema-version', 'source', 'revision', 'files'}:
        raise ValueError('Invalid skill manifest fields')
    if type(manifest['schema-version']) is not int or manifest['schema-version'] != 1:
        raise ValueError('Unsupported skill manifest schema-version')
    if manifest['source'] != SOURCE:
        raise ValueError(f'The source must be {SOURCE}')
    if not isinstance(manifest['revision'], str) or not REVISION.fullmatch(manifest['revision']):
        raise ValueError('The source revision must be a full lowercase commit SHA')
    files = manifest['files']
    if (not isinstance(files, list) or not files
            or not all(isinstance(path, str) and path in ALLOWED_FILES for path in files)
            or len(files) != len(set(files))):
        raise ValueError('Manifest files must be a nonempty, unique list of approved skill files')
    return manifest


def source_text(library: Path, revision: str, path: str) -> str:
    entry = git(library, 'ls-tree', revision, '--', path).strip()
    if not entry.startswith('100644 blob ') or entry.split('\t')[-1] != path:
        raise ValueError(f'{path}: source must be a tracked regular file at {revision}')
    return git(library, 'show', f'{revision}:{path}')


def merge_text(current: str, base: str, incoming: str, path: str) -> str:
    with tempfile.TemporaryDirectory(prefix='shared-skill-merge-') as directory:
        paths = [Path(directory) / name for name in ('current', 'base', 'incoming')]
        for target, content in zip(paths, (current, base, incoming), strict=True):
            target.write_text(content)
        result = subprocess.run(['git', 'merge-file', '--stdout', '--diff3', *map(str, paths)],
                                check=False, capture_output=True, text=True)
    if result.returncode:
        raise ValueError(f'{path}: three-way merge conflict or merge error; no files were written')
    return result.stdout


def prepare(consumer: Path, library: Path, revision: str) -> dict[str, str]:
    """Validate every selected file and return a complete, unwritten change set."""
    if not REVISION.fullmatch(revision):
        raise ValueError('The target revision must be a full lowercase commit SHA')
    manifest = read_manifest(consumer)
    git(library, 'cat-file', '-e', f'{revision}^{{commit}}')
    git(library, 'cat-file', '-e', f'{manifest["revision"]}^{{commit}}')
    changes = {}
    upstream_changed = False
    for relative in manifest['files']:
        current = checked_path(consumer, relative).read_text()
        base = source_text(library, manifest['revision'], relative)
        incoming = source_text(library, revision, relative)
        upstream_changed |= base != incoming
        merged = merge_text(current, base, incoming, relative)
        if merged != current:
            changes[relative] = merged
    if upstream_changed:
        manifest['revision'] = revision
        changes[MANIFEST] = json.dumps(manifest, indent=2) + '\n'
    return changes


def apply(consumer: Path, changes: dict[str, str]) -> None:
    """Apply a prepared update only to a clean, explicitly selected Git root."""
    root = consumer.resolve()
    if Path(git(root, 'rev-parse', '--show-toplevel').strip()).resolve() != root:
        raise ValueError('The consumer must be the Git repository root')
    if git(root, 'status', '--porcelain', '--untracked-files=all').strip():
        raise ValueError('The consumer checkout must be clean before applying an update')
    if not set(changes).issubset(ALLOWED_FILES | {MANIFEST}):
        raise ValueError('Changes include an unmanaged file')
    destinations = {name: checked_path(root, name) for name in changes}
    original = {name: path.read_text() for name, path in destinations.items()}
    try:
        for name, path in destinations.items():
            path.write_text(changes[name])
    except OSError:
        for name, path in destinations.items():
            path.write_text(original[name])
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repository', type=Path)
    parser.add_argument('--revision', required=True, help='Reviewed library commit SHA, already fetched locally')
    parser.add_argument('--apply', action='store_true', help='Write the prepared update to a clean consumer checkout')
    arguments = parser.parse_args()
    library = Path(__file__).resolve().parents[1]
    try:
        changes = prepare(arguments.repository, library, arguments.revision)
        if arguments.apply:
            apply(arguments.repository, changes)
        for path in sorted(changes):
            print(f'{"Updated" if arguments.apply else "Would update"}: {path}')
        if not changes:
            print('Selected shared skills are up to date; local adaptations were retained.')
        return int(bool(changes) and not arguments.apply)
    except (ValueError, OSError) as error:
        print(f'Cannot update shared skills: {error}')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
