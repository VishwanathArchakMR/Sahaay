---
name: Tabular Data Analysis and Workbook Creation
description: Method for deterministic statistical analysis, aggregation, SQL grouping, and Excel workbook production.
version: 1.0.0
author: Sahaay Core Team
tools: [data_analyze_tabular, artifact_generate_spreadsheet, file_read]
---

### Data Analysis Methodology:
1. **Data Ingestion & Profiling**: Profile tabular data using `data_analyze_tabular` over CSV or XLSX datasets.
2. **Deterministic Computation**: Compute exact numerical counts, sums, averages, medians, minimums, and maximums via in-memory SQLite.
3. **Spreadsheet Generation**: Use `artifact_generate_spreadsheet` to produce an editable Excel workbook (.xlsx) on the user's Desktop with headers, aligned columns, and standard formulas (e.g. SUM, AVERAGE).
4. **Readback Verification**: Reopen and verify generated workbook size and SHA-256 fingerprint.

