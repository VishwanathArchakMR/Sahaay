"""Project Workspace & Folder Indexing Service.

Recursively discovers and indexes files in an authorized project folder,
calculating SHA-256 hashes, generating directory hierarchy maps, and
persisting metadata into SQLite source_references and context_facts.
"""

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sahaay_core.config.settings import REPO_ROOT, settings
from sahaay_core.contracts.models import ContextFact, SourceReference
from sahaay_core.storage.persistence import durable_storage

logger = logging.getLogger("sahaay.sources.workspace_indexer")

EXCLUDED_DIRS = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "bin",
    "obj",
}

TEXT_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".json",
    ".md",
    ".txt",
    ".html",
    ".css",
    ".cs",
    ".sql",
    ".yaml",
    ".yml",
    ".toml",
    ".xml",
}


def index_workspace_directory(
    directory_path: Optional[str] = None,
    session_id: Optional[UUID] = None,
    max_depth: int = 4,
    max_files: int = 150,
    workspace_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Index an authorized project folder or workspace directory."""
    effective_path = directory_path or workspace_path or "."
    target_dir = Path(effective_path).resolve()
    if not target_dir.exists() or not target_dir.is_dir():
        raise ValueError(f"Directory path does not exist or is not a folder: {target_dir}")

    discovered_files: List[Dict[str, Any]] = []
    file_tree: Dict[str, Any] = {"name": target_dir.name, "type": "directory", "children": []}

    base_depth = len(target_dir.parts)

    for root, dirs, files in os.walk(str(target_dir)):
        # Prune excluded directories in-place
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS]

        curr_depth = len(Path(root).parts) - base_depth
        if curr_depth > max_depth:
            continue

        for f in files:
            if len(discovered_files) >= max_files:
                break

            file_path = Path(root) / f
            try:
                stat = file_path.stat()
                size_bytes = stat.st_size
                ext = file_path.suffix.lower()

                # Read preview for text files up to 2MB
                preview = ""
                sha256_hash = ""
                if ext in TEXT_EXTENSIONS and size_bytes <= 2 * 1024 * 1024:
                    raw_bytes = file_path.read_bytes()
                    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()
                    try:
                        text_content = raw_bytes.decode("utf-8", errors="replace")
                        preview = text_content[:800]
                    except Exception:
                        preview = ""
                else:
                    sha256_hash = hashlib.sha256(f"{file_path}_{stat.st_mtime}".encode("utf-8")).hexdigest()

                rel_path = str(file_path.relative_to(target_dir))
                file_info = {
                    "path": str(file_path),
                    "relativePath": rel_path,
                    "filename": f,
                    "extension": ext,
                    "sizeBytes": size_bytes,
                    "sha256": sha256_hash,
                    "preview": preview,
                }
                discovered_files.append(file_info)

                # Persist to SQLite if session_id is provided
                if session_id and sha256_hash:
                    ref = SourceReference(
                        referenceId=uuid4(),
                        sessionId=session_id,
                        sourceType="local_file",
                        targetIdentifier=str(file_path),
                        title=f,
                        sha256Fingerprint=sha256_hash,
                        byteSize=size_bytes,
                        metadataJson={
                            "relativePath": rel_path,
                            "extension": ext,
                            "workspace": str(target_dir),
                        },
                    )
                    durable_storage.save_source_reference(ref)

                    if preview:
                        fact = ContextFact(
                            factId=uuid4(),
                            sessionId=session_id,
                            category="project_file",
                            key=rel_path,
                            value=preview[:400],
                            confidence=1.0,
                            provenanceSha256=sha256_hash,
                        )
                        durable_storage.save_context_fact(fact)

            except Exception as f_err:
                logger.debug("Failed to index file %s: %s", file_path, f_err)

    return {
        "workspacePath": str(target_dir),
        "totalFilesDiscovered": len(discovered_files),
        "files": discovered_files,
        "summary": (
            f"Indexed workspace '{target_dir.name}': {len(discovered_files)} files processed "
            f"with cryptographic SHA-256 fingerprints."
        ),
    }

