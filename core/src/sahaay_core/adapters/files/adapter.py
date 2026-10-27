"""File System Adapter for Permitted File Operations."""

from pathlib import Path


class FileAdapter:
    """Safe local file reader enforcing path containment and permissions."""

    @staticmethod
    def read_text_file(path_str: str, max_bytes: int = 2_000_000) -> str:
        """Read permitted file within size constraints."""
        target_path = Path(path_str).resolve()
        if not target_path.exists():
            raise FileNotFoundError(f"File not found: {path_str}")

        if not target_path.is_file():
            raise ValueError(f"Path is not a regular file: {path_str}")

        if target_path.stat().st_size > max_bytes:
            raise ValueError(f"File size exceeds limit of {max_bytes} bytes.")

        return target_path.read_text(encoding="utf-8", errors="replace")
