"""Check portable agent metadata and local file references without executing instructions."""
import argparse
import os
from pathlib import Path, PurePosixPath
import re
from urllib.parse import unquote, urlsplit

import yaml

EXCLUDED_DIRECTORIES = {".git", ".venv", "node_modules", "__pycache__"}
LINK = re.compile(r"\[[^\]]*\]\((?:<([^>]+)>|([^\s)]+))(?:\s+[^)]*)?\)")
CHARACTER_CLASS = re.compile(r"\[(?:[!^])?\]?[^]]*\]")


def repository_files(root: Path) -> list[Path]:
    files = []
    for directory, children, names in os.walk(root):
        children[:] = [name for name in children if name not in EXCLUDED_DIRECTORIES]
        files.extend(Path(directory) / name for name in names)
    return files


def without_fences(text: str) -> str:
    lines = []
    fence = ""
    for line in text.splitlines():
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines)


def scope_patterns(scope: str) -> list[str]:
    patterns = []
    start = depth = 0
    protected = {index for match in CHARACTER_CLASS.finditer(scope) for index in range(*match.span())}
    for index, character in enumerate(scope):
        if index in protected:
            continue
        if character == "{":
            depth += 1
        elif character == "}":
            depth -= 1
        elif character == "," and depth == 0:
            patterns.append(scope[start:index].strip())
            start = index + 1
    patterns.append(scope[start:].strip())
    return patterns


def matches_scope(relative: str, pattern: str) -> bool:
    masked = CHARACTER_CLASS.sub(lambda match: "_" * len(match[0]), pattern)
    brace = re.search(r"\{([^{}]+)\}", masked)
    if brace:
        return any(matches_scope(relative, pattern[:brace.start()] + option + pattern[brace.end():])
                   for option in scope_patterns(pattern[brace.start() + 1:brace.end() - 1]))
    return PurePosixPath(relative).full_match(pattern, case_sensitive=True)


def metadata_errors(path: Path, text: str, files: list[str]) -> list[str]:
    parts = re.split(r"^---\s*$", text, maxsplit=2, flags=re.MULTILINE)
    if len(parts) != 3 or parts[0].strip():
        return ["missing YAML frontmatter"]
    try:
        metadata = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return ["invalid YAML frontmatter"]
    if not isinstance(metadata, dict):
        return ["frontmatter must be a mapping"]
    errors = []
    if not isinstance(metadata.get("description"), str) or not metadata["description"].strip():
        errors.append("description must be nonempty text")
    if path.name == "SKILL.md" and metadata.get("name") != path.parent.name:
        errors.append("skill name must match its folder")
    if path.name.endswith(".instructions.md"):
        scope = metadata.get("applyTo")
        if not isinstance(scope, str) or not scope.strip():
            errors.append("applyTo must contain a file scope")
        else:
            for pattern in scope_patterns(scope):
                pattern = pattern.strip()
                if not pattern or not any(matches_scope(file, pattern) for file in files):
                    errors.append(f"scope {pattern!r} matches no files")
    return errors


def validate(root: Path) -> list[str]:
    root = root.resolve()
    if not root.is_dir():
        return [f"{root}: repository directory does not exist"]
    files = repository_files(root)
    relative_files = [str(path.relative_to(root)) for path in files]
    candidates = [path for path in files if path.name in {"AGENTS.md", "copilot-instructions.md"} or (
        ".github" in path.relative_to(root).parts and
        (path.name == "SKILL.md" or path.name.endswith((".instructions.md", ".agent.md"))))]
    errors = []
    for path in candidates:
        label = str(path.relative_to(root))
        if not path.resolve().is_relative_to(root):
            errors.append(f"{label}: file points outside the repository")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            errors.append(f"{label}: cannot read file ({type(error).__name__})")
            continue
        if path.name not in {"AGENTS.md", "copilot-instructions.md"}:
            errors.extend(f"{label}: {error}" for error in metadata_errors(path, text, relative_files))
        for match in LINK.finditer(without_fences(text)):
            destination = match.group(1) or match.group(2)
            parsed = urlsplit(destination)
            if parsed.scheme or parsed.netloc or not parsed.path:
                continue
            target = path.parent / unquote(parsed.path)
            if not target.resolve().is_relative_to(root) or not target.exists():
                errors.append(f"{label}: missing or external local link {destination}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repository", type=Path)
    errors = validate(parser.parse_args().repository)
    for error in errors:
        print(error)
    if not errors:
        print("Agent configuration structure passed; agent behavior was not evaluated.")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
