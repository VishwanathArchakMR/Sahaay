---
name: Deep Research and Synthesis
description: Method for multi-source web research, primary source verification, fact cross-checking, and cited synthesis.
version: 1.0.0
author: Sahaay Core Team
tools: [research_web_multihop, artifact_generate_document, file_create_write]
---

### Deep Research Methodology:
1. **Query Formulation**: Break the user's research goal into 2-3 specific primary queries targeting authoritative sources.
2. **Multi-Source Retrieval**: Use `research_web_multihop` to query DuckDuckGo and safely fetch full page text from top search results.
3. **Fact Extraction & Contradiction Check**: Compare extracted claims across retrieved pages. Flag disagreements or outdated figures.
4. **Structured Artifact Output**: Use `artifact_generate_document` to write a comprehensive Word (.docx) or Markdown (.md) report saved to the user's Desktop with an Executive Summary, Findings, Table of Comparisons, and Source Citations.
5. **Verification**: Confirm file exists on disk and verify output character count.

