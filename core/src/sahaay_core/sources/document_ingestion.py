"""Document Ingestion Service for Sahaay.

Supports user-initiated, local ingestion of text (.txt, .json, .csv, .log),
Markdown (.md), and PDF (.pdf) documents into structured, traceable ContextFacts.
Enforces strict size limits, local-only parsing, and safe isolation.
"""

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

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
SUPPORTED_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".json",
    ".csv",
    ".tsv",
    ".log",
    ".pdf",
    ".html",
    ".htm",
    ".docx",
    ".xlsx",
    ".xls",
    ".pptx",
    ".xml",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".java",
    ".cpp",
    ".c",
    ".cs",
    ".rs",
    ".go",
    ".sql",
    ".sh",
    ".ps1",
    ".bat",
}


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
        elif suffix == ".docx":
            facts_created = self._parse_docx(path, source_ref.sourceId)
        elif suffix in (".xlsx", ".xls"):
            facts_created = self._parse_xlsx(path, source_ref.sourceId)
        elif suffix == ".pptx":
            facts_created = self._parse_pptx(path, source_ref.sourceId)
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

    def _parse_docx(self, path: Path, source_id: UUID) -> List[Any]:
        """Extract text paragraphs from Word DOCX XML without external dependencies."""
        import xml.etree.ElementTree as ET
        import zipfile

        facts = []
        try:
            with zipfile.ZipFile(str(path), "r") as docx_zip:
                if "word/document.xml" not in docx_zip.namelist():
                    raise DocumentIngestionError("Invalid DOCX format: missing word/document.xml")
                xml_content = docx_zip.read("word/document.xml")
                root = ET.fromstring(xml_content)
                # Namespace for WordprocessingML
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = []
                for p_elem in root.findall(".//w:p", ns):
                    texts = [t.text for t in p_elem.findall(".//w:t", ns) if t.text]
                    if texts:
                        p_str = "".join(texts).strip()
                        if p_str:
                            paragraphs.append(p_str)

                for idx, paragraph in enumerate(paragraphs):
                    fact = self.context_store.record_fact(
                        fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                        content=paragraph[:3000],
                        source_reference_id=source_id,
                        confidence_score=1.0,
                        metadata={
                            "paragraphIndex": idx,
                            "format": ".docx",
                            "isUntrusted": True,
                        },
                    )
                    facts.append(fact)
        except Exception as ex:
            raise DocumentIngestionError(f"DOCX parsing error: {str(ex)}") from ex

        return facts

    def _parse_xlsx(self, path: Path, source_id: UUID) -> List[Any]:
        """Extract tabular rows from Excel XLSX XML without external dependencies."""
        import xml.etree.ElementTree as ET
        import zipfile

        facts = []
        try:
            with zipfile.ZipFile(str(path), "r") as xlsx_zip:
                shared_strings = []
                if "xl/sharedStrings.xml" in xlsx_zip.namelist():
                    ss_root = ET.fromstring(xlsx_zip.read("xl/sharedStrings.xml"))
                    for si in ss_root.findall(
                        ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}si"
                    ):
                        t_parts = [
                            t.text
                            for t in si.findall(
                                ".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t"
                            )
                            if t.text
                        ]
                        shared_strings.append("".join(t_parts))

                # Process first sheet or all worksheets
                ns = {"s": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
                sheet_names = [
                    n
                    for n in xlsx_zip.namelist()
                    if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
                ]
                for sheet_path in sheet_names:
                    sheet_root = ET.fromstring(xlsx_zip.read(sheet_path))
                    rows_text = []
                    for row_elem in sheet_root.findall(".//s:row", ns):
                        row_vals = []
                        for c_elem in row_elem.findall("s:c", ns):
                            c_type = c_elem.get("t")
                            v_elem = c_elem.find("s:v", ns)
                            if v_elem is not None and v_elem.text:
                                val = v_elem.text
                                if (
                                    c_type == "s"
                                    and val.isdigit()
                                    and int(val) < len(shared_strings)
                                ):
                                    row_vals.append(shared_strings[int(val)])
                                else:
                                    row_vals.append(val)
                        if row_vals:
                            rows_text.append(" | ".join(row_vals))

                    if rows_text:
                        # Group rows into chunks of 25 lines
                        chunk_size = 25
                        for chunk_idx in range(0, len(rows_text), chunk_size):
                            chunk_lines = rows_text[chunk_idx : chunk_idx + chunk_size]
                            fact = self.context_store.record_fact(
                                fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                                content="\n".join(chunk_lines),
                                source_reference_id=source_id,
                                confidence_score=1.0,
                                metadata={
                                    "sheet": sheet_path,
                                    "rowRange": f"{chunk_idx + 1}-{chunk_idx + len(chunk_lines)}",
                                    "format": ".xlsx",
                                    "isUntrusted": True,
                                },
                            )
                            facts.append(fact)
        except Exception as ex:
            raise DocumentIngestionError(f"XLSX parsing error: {str(ex)}") from ex

        return facts

    def _parse_pptx(self, path: Path, source_id: UUID) -> List[Any]:
        """Extract slide texts from PowerPoint PPTX XML."""
        import xml.etree.ElementTree as ET
        import zipfile

        facts = []
        try:
            with zipfile.ZipFile(str(path), "r") as pptx_zip:
                slide_names = sorted(
                    [
                        n
                        for n in pptx_zip.namelist()
                        if n.startswith("ppt/slides/slide") and n.endswith(".xml")
                    ]
                )
                for slide_idx, slide_path in enumerate(slide_names):
                    slide_root = ET.fromstring(pptx_zip.read(slide_path))
                    texts = [
                        t.text
                        for t in slide_root.findall(
                            ".//{http://schemas.openxmlformats.org/drawingml/2006/main}t"
                        )
                        if t.text
                    ]
                    slide_text = " ".join(texts).strip()
                    if slide_text:
                        fact = self.context_store.record_fact(
                            fact_type=FactTypeEnum.SOURCE_EXTRACTED,
                            content=f"Slide {slide_idx + 1}: {slide_text[:3000]}",
                            source_reference_id=source_id,
                            confidence_score=1.0,
                            metadata={
                                "slideNumber": slide_idx + 1,
                                "format": ".pptx",
                                "isUntrusted": True,
                            },
                        )
                        facts.append(fact)
        except Exception as ex:
            raise DocumentIngestionError(f"PPTX parsing error: {str(ex)}") from ex

        return facts

    def _parse_pdf(self, path: Path, source_id: UUID) -> List[Any]:
        """Extract text page-by-page from PDF."""
        facts = []
        if PdfReader is None:
            return facts
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
