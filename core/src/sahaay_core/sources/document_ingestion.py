"""Document Ingestion Service for Sahaay.

Supports user-initiated, local ingestion of text (.txt, .json, .csv, .log),
Markdown (.md), and PDF (.pdf) documents into structured, traceable ContextFacts.
Enforces strict size limits, local-only parsing, and safe isolation.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from pypdf import PdfReader

from sahaay_core.context.store import ContextStore
from sahaay_core.contracts.models import FactTypeEnum, SourceReference
from sahaay_core.sources.manager import SourceManager

# Maximum allowed file size for local ingestion (10 MB)
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Disallowed directory patterns (security isolation)
FORBIDDEN_PATH_SUBSTRINGS = [
    "system32",
    "windows\\system",
    ".ssh",
    ".aws",
    "id_rsa",
    ".env",
    "credentials",
]

# Supported file extensions
SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".json", ".csv", ".log", ".pdf"}


class DocumentIngestionError(Exception):
    """Raised when document ingestion fails validation or parsing."""

    pass


class DocumentIngestionService:
    """Safely extracts text and records provenance facts from user-selected files."""

    def __init__(self, source_manager: SourceManager, context_store: ContextStore) -> None:
        self.source_manager = source_manager
        self.context_store = context_store

    def ingest_file(
        self,
        file_path_str: str,
        custom_title: Optional[str] = None,
        task_id: Optional[UUID] = None,
    ) -> Dict[str, Any]:
        """Ingest a single user-authorized file, extract facts, and register source."""
        path = Path(file_path_str).resolve()

        # 1. Path existence and security checks
        if not path.is_file():
            raise DocumentIngestionError(f"File not found or inaccessible: {file_path_str}")

        path_lower = str(path).lower()
        for forbidden in FORBIDDEN_PATH_SUBSTRINGS:
            if forbidden in path_lower:
                raise DocumentIngestionError(
                    f"Access to sensitive path containing '{forbidden}' is strictly denied."
                )

        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise DocumentIngestionError(
                f"Unsupported file format '{suffix}'. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        # 2. File size enforcement
        file_size = path.stat().st_size
        if file_size > MAX_FILE_SIZE_BYTES:
            raise DocumentIngestionError(
                f"File size ({file_size} bytes) exceeds maximum limit of {MAX_FILE_SIZE_BYTES} bytes."
            )

        # 3. Read raw bytes and calculate SHA-256 checksum
        raw_bytes = path.read_bytes()
        sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

        # 4. Register SourceReference
        title = custom_title or path.name
        source_ref: SourceReference = self.source_manager.register_source(
            source_type="local_document",
            uri=str(path),
            title=title,
            checksum=sha256_hash,
            metadata={
                "fileSize": file_size,
                "fileExtension": suffix,
                "fileName": path.name,
                "taskId": str(task_id) if task_id else None,
            },
        )

        # 5. Extract text facts safely based on format
        facts_created = []
        if suffix == ".pdf":
            facts_created = self._parse_pdf(path, source_ref.sourceId)
        else:
            facts_created = self._parse_text_or_markdown(raw_bytes, suffix, source_ref.sourceId)

        return {
            "success": True,
            "sourceId": str(source_ref.sourceId),
            "uri": str(path),
            "title": title,
            "checksum": sha256_hash,
            "factsCount": len(facts_created),
            "fileSize": file_size,
        }

    def _parse_pdf(self, path: Path, source_id: UUID) -> List[Any]:
        """Extract text page-by-page from PDF."""
        facts = []
        try:
            reader = PdfReader(str(path))
            for page_idx, page in enumerate(reader.pages):
                page_text = page.extract_text() or ""
                trimmed = page_text.strip()
                if trimmed:
                    # Bounded chunk per page (max 4000 chars per fact)
                    fact = self.context_store.record_fact(
                        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                        content=trimmed[:4000],
                        source_reference_id=source_id,
                        confidence_score=1.0,
                        metadata={
                            "pageNumber": page_idx + 1,
                            "totalPages": len(reader.pages),
                            "isUntrusted": True,
                        },
                    )
                    facts.append(fact)
        except Exception as ex:
            raise DocumentIngestionError(f"PDF parsing error: {str(ex)}") from ex

        return facts

    def _parse_text_or_markdown(self, raw_bytes: bytes, suffix: str, source_id: UUID) -> List[Any]:
        """Extract text chunks with line and section metadata."""
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = raw_bytes.decode("latin-1")
            except Exception as ex:
                raise DocumentIngestionError(f"Failed to decode text content: {str(ex)}") from ex

        facts = []
        # Normalize line endings to support Windows CRLF and Unix LF
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = [p.strip() for p in normalized_text.split("\n\n") if p.strip()]
        if not paragraphs and normalized_text.strip():
            paragraphs = [normalized_text.strip()]

        char_offset = 0
        for idx, paragraph in enumerate(paragraphs):
            # Limit paragraph length to 3000 chars
            bounded_chunk = paragraph[:3000]
            fact = self.context_store.record_fact(
                fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                content=bounded_chunk,
                source_reference_id=source_id,
                confidence_score=1.0,
                metadata={
                    "paragraphIndex": idx,
                    "charOffset": char_offset,
                    "format": suffix,
                    "isUntrusted": True,
                },
            )
            facts.append(fact)
            char_offset += len(paragraph) + 2

        return facts
