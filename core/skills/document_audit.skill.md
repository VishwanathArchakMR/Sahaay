---
name: Multi-Document Audit and Inconsistency Analysis
description: Method for ingesting local PDFs, Word docs, spreadsheets, and detecting discrepancies or missing clauses.
version: 1.0.0
author: Sahaay Core Team
tools: [document_ingest_file, document_search_knowledge, document_compare_sources, artifact_generate_document]
---

### Document Audit Methodology:
1. **Source Ingestion**: Ingest target files with `document_ingest_file` (supports .pdf, .docx, .xlsx, .pptx, .csv, code).
2. **Fact Ledger**: All extracted paragraphs and rows are hashed via SHA-256 and stored in the durable ContextStore.
3. **Cross-Source Search**: Use `document_search_knowledge` and `document_compare_sources` to retrieve relevant clauses, price points, dates, or specifications.
4. **Discrepancy Identification**: Flag mismatched dates, conflicting terms, price variations, or missing deliverables.
5. **Report Generation**: Compile an audit report using `artifact_generate_document` detailing matching terms, discovered discrepancies, and recommended resolutions.

