"""Automated Secret Scanning Test for Repository Files."""

import re
from pathlib import Path

# Patterns that detect potential live secrets / private keys / tokens
SECRET_REGEXES = [
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"ghp_[A-Za-z0-9_]{36}"),
    re.compile(r"xox[baprs]-[0-9A-Za-z]{10,48}"),
    re.compile(r"AIza[0-9A-Za-z-_]{35}"),
    re.compile(r"baseten_[a-zA-Z0-9]{32}"),
    re.compile(r"sk-[a-zA-Z0-9]{48}"),
]

# File extensions to scan
SCANNED_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".json",
    ".md",
    ".yml",
    ".yaml",
    ".cs",
    ".txt",
}

# Ignore paths
IGNORED_DIRS = {
    ".git",
    ".venv",
    "node_modules",
    "dist",
    "out",
    "obj",
    "bin",
    "__pycache__",
}


def test_no_secrets_in_repository():
    repo_root = Path(__file__).resolve().parent.parent.parent
    violations = []

    for path in repo_root.rglob("*"):
        if path.is_file() and path.suffix in SCANNED_EXTENSIONS:
            # Check if any parent is in IGNORED_DIRS
            if any(part in IGNORED_DIRS for part in path.parts):
                continue

            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                for regex in SECRET_REGEXES:
                    match = regex.search(content)
                    if match:
                        violations.append(
                            f"Potential secret in {path.relative_to(repo_root)}: {match.group(0)[:10]}..."
                        )
            except (OSError, UnicodeDecodeError):
                pass

    assert not violations, "Secret scanner discovered potential secrets:\n" + "\n".join(violations)
