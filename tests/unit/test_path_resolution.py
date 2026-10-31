"""Unit tests for repository-relative path and fixture resolution.

Ensures path resolution behaves consistently across local environments (C:\\Sahaay),
GitHub Actions runner work directories (e.g. D:\\a\\Sahaay\\Sahaay), and arbitrary working directories.
"""

import os
import tempfile

from sahaay_core.config.settings import (
    find_repo_root,
    get_fixture_path,
    get_fixtures_dir,
    get_repo_root,
)


def test_find_repo_root_locates_valid_root():
    """Verify find_repo_root finds a directory containing the Sahaay codebase structure."""
    root = find_repo_root()
    assert root.exists(), f"Repo root {root} does not exist"
    assert (root / "core").exists(), f"Repo root {root} missing 'core' directory"
    assert (root / "data").exists(), f"Repo root {root} missing 'data' directory"


def test_get_fixtures_dir_resolves_existing_directory():
    """Verify get_fixtures_dir points to the actual fixtures directory."""
    fixtures_dir = get_fixtures_dir()
    assert fixtures_dir.exists(), f"Fixtures directory {fixtures_dir} does not exist"
    assert fixtures_dir.is_dir()


def test_get_fixture_path_locates_known_fixtures():
    """Verify known test fixtures are resolved correctly."""
    known_fixtures = [
        "electricity_bill.txt",
        "deadline_notice.html",
        "project_report.txt",
        "local_notes.txt",
        "invoice_data.json",
    ]
    for fix_name in known_fixtures:
        path = get_fixture_path(fix_name)
        assert path.exists(), f"Expected fixture '{fix_name}' was not found at {path}"
        assert path.is_file(), f"Fixture path {path} is not a file"


def test_repo_root_cached_and_stable():
    """Verify get_repo_root() returns consistent results."""
    root1 = get_repo_root()
    root2 = get_repo_root()
    assert root1 == root2


def test_path_resolution_independent_of_cwd():
    """Verify path resolution still succeeds when CWD changes to a temp folder."""
    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            os.chdir(tmp_dir)
            # Both get_repo_root() and get_fixture_path() should still resolve accurately
            fix_path = get_fixture_path("electricity_bill.txt")
            assert fix_path.exists()
        finally:
            os.chdir(original_cwd)
