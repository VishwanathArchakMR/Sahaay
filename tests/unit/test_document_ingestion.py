"""Unit tests for local document ingestion (text, markdown, PDF)."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pypdf import PdfWriter
from sahaay_core.context.store import ContextStore
from sahaay_core.main import app
from sahaay_core.sources.document_ingestion import (
    DocumentIngestionError,
    DocumentIngestionService,
)
from sahaay_core.sources.manager import SourceManager


@pytest.mark.asyncio
async def test_ingest_markdown_file_success(tmp_path: Path):
    """Verify local Markdown document is parsed into structured facts with checksum."""
    md_file = tmp_path / "architecture_notes.md"
    md_content = "# Architecture\n\nSahaay uses a modular monolith design.\n\nAll actions require ActionGate authorization."
    md_file.write_text(md_content, encoding="utf-8")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            "/api/v1/sources/ingest-file",
            json={"filePath": str(md_file), "customTitle": "Architecture Notes"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data["title"] == "Architecture Notes"
        assert len(data["checksum"]) == 64  # SHA-256 hex string
        assert data["factsCount"] >= 2


@pytest.mark.asyncio
async def test_ingest_pdf_file_success(tmp_path: Path):
    """Verify PDF document is extracted page-by-page with page metadata."""
    pdf_file = tmp_path / "sample_policy.pdf"

    # Create a small valid PDF using pypdf
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.write(str(pdf_file))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post(
            "/api/v1/sources/ingest-file",
            json={"filePath": str(pdf_file), "customTitle": "Sample Policy"},
        )
        assert res.status_code == 201
        data = res.json()
        assert data["success"] is True
        assert data["title"] == "Sample Policy"


@pytest.mark.asyncio
async def test_ingest_rejects_forbidden_path():
    """Verify sensitive system paths or credential files are denied."""
    sm = SourceManager()
    cs = ContextStore()
    svc = DocumentIngestionService(source_manager=sm, context_store=cs)

    with pytest.raises(DocumentIngestionError) as exc_info:
        svc.ingest_file("C:\\Windows\\System32\\drivers\\etc\\hosts")
    assert "sensitive path" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_ingest_rejects_unsupported_extension(tmp_path: Path):
    """Verify unsupported binary formats like .exe or .bin are rejected."""
    bin_file = tmp_path / "program.exe"
    bin_file.write_bytes(b"\x00\x01\x02\x03")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        res = await client.post("/api/v1/sources/ingest-file", json={"filePath": str(bin_file)})
        assert res.status_code == 400
        assert "unsupported" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_search_over_ingested_document(tmp_path: Path):
    """Verify deterministic search locates exact snippet inside ingested document."""
    txt_file = tmp_path / "knowledge_base.txt"
    txt_file.write_text(
        "Sahaay was designed for voice-first Windows assistance and retrieval.",
        encoding="utf-8",
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testclient") as client:
        ingest_res = await client.post(
            "/api/v1/sources/ingest-file", json={"filePath": str(txt_file)}
        )
        assert ingest_res.status_code == 201

        search_res = await client.post(
            "/api/v1/sources/search", json={"query": "voice-first Windows"}
        )
        assert search_res.status_code == 200
        data = search_res.json()
        assert data["count"] >= 1
        assert "voice-first windows" in data["results"][0]["matchedSnippet"].lower()
        assert data["results"][0]["sourceType"] == "local_document"
