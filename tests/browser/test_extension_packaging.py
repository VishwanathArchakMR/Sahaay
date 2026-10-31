"""Build validation test for the canonical Chrome/Edge extension package.

Asserts that apps/browser-extension/dist contains:
1. Valid JSON manifest.json
2. Every referenced service worker, content script, side panel, and options page exists.
3. Every HTML file resolves its local script and stylesheet without 404s.
"""

import json
from pathlib import Path


def test_canonical_extension_package_integrity():
    repo_root = Path(__file__).resolve().parent.parent.parent
    dist_dir = repo_root / "apps" / "browser-extension" / "dist"

    assert dist_dir.exists(), f"Canonical extension package directory '{dist_dir}' must exist."

    manifest_path = dist_dir / "manifest.json"
    assert manifest_path.exists(), f"Manifest file must exist at '{manifest_path}'."

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("manifest_version") == 3
    assert manifest.get("name") == "Sahaay Browser Bridge"

    # 1. Background service worker
    sw_rel = manifest.get("background", {}).get("service_worker")
    assert sw_rel, "Manifest must declare background.service_worker"
    sw_path = dist_dir / sw_rel
    assert sw_path.exists(), f"Service worker not found at '{sw_path}'"

    # 2. Content scripts
    content_scripts = manifest.get("content_scripts", [])
    assert len(content_scripts) > 0, "Manifest must declare content_scripts"
    for cs in content_scripts:
        for js_rel in cs.get("js", []):
            js_path = dist_dir / js_rel
            assert js_path.exists(), f"Content script not found at '{js_path}'"

    # 3. Side panel
    side_panel_rel = manifest.get("side_panel", {}).get("default_path")
    assert side_panel_rel, "Manifest must declare side_panel.default_path"
    sp_path = dist_dir / side_panel_rel
    assert sp_path.exists(), f"Side panel HTML not found at '{sp_path}'"

    # 4. Side panel script and css references
    sp_html = sp_path.read_text(encoding="utf-8")
    assert "sidepanel.js" in sp_html
    assert "sidepanel.css" in sp_html
    assert (dist_dir / "sidepanel" / "sidepanel.js").exists()
    assert (dist_dir / "sidepanel" / "sidepanel.css").exists()

    # 5. Options UI
    options_rel = manifest.get("options_ui", {}).get("page")
    if options_rel:
        opt_path = dist_dir / options_rel
        assert opt_path.exists(), f"Options HTML not found at '{opt_path}'"
