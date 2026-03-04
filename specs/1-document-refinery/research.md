# Research Notes — Document Intelligence Refinery (Phase 0)

## Decisions

Decision: VLM Provider & Budget Cap
- Decision: Hybrid strategy — local open-source / on-prem models by default; escalate to cloud VLMs (via adapter) when confidence < 0.60. Per-document cloud VLM spend cap: $2.00 (configurable).
- Rationale: Most documents can be handled by deterministic OCR/layout models; scanned/hard pages are rare but require high-fidelity VLM extraction. A small per-document cap keeps demos affordable while allowing targeted vision calls.
- Alternatives considered:
  - Local-only: lowest cost, lower fidelity on hard scanned documents.
  - Cloud-only (no cap): highest fidelity, unpredictable costs.

Decision: Language Coverage & OCR Fallback
- Decision: Primary support: English + Amharic. Fallback policy: run language detection; for Amharic or other non-Latin scripts, route to Tesseract with language packs first; if OCR confidence < 0.60, escalate to VLM extraction.
- Rationale: The target corpus contains Ethiopian reports where Amharic coverage is important. Tesseract with appropriate language packs provides a low-cost first pass; VLM escalation addresses low-resource OCR failures.
- Alternatives considered:
  - English-only (simpler, but fails on local language docs).
  - Broad multilingual support (costly and increases engineering scope).

## Thresholds & Heuristics (initial, tunable)
These are initial empirical thresholds to be refined with real documents.

Strategy A (FastText) confidence signals per page:
- `min_char_count_per_page`: 100 characters
- `min_char_density`: 0.001 chars / point-squared (chars / page_area_pts)
- `max_image_area_pct`: 0.50 (50% of page area)
- `font_metadata_present`: boolean (true increases confidence)

Aggregate `strategy_a_confidence` (0.0-1.0): weighted sum
- char_count_score (0-0.4)
- char_density_score (0-0.3)
- image_area_score (0-0.2)
- font_metadata_score (0-0.1)
- Confidence threshold to accept Strategy A output: 0.60
- If <0.60 → escalate to Strategy B (layout-aware). If B also <0.60 → escalate to Strategy C (VLM), respecting per-document budget.

VLM budget guard
- `per_document_vlm_cap_usd`: 2.00
- Track `estimated_cost_usd` per VLM call and stop escalation if cap exceeded (mark document for manual review)

Language confidence
- OCR confidence threshold: 0.60 (below which escalate to VLM)

## Research Tasks (Phase 0 follow-ups)
- Run `pdfplumber` character-density analysis on sample documents and tune `min_char_density` and `min_char_count_per_page`.
- Run Tesseract on sample Amharic pages and measure OCR confidence distribution.
- Benchmark MinerU / Docling table extraction on sample Class D documents and measure precision/recall.
- Validate VLM extraction prompts (cost vs fidelity) on 10 scanned pages to confirm `per_document_vlm_cap_usd` is sufficient.

## Short Rationale Summary
- The hybrid approach minimizes cost while preserving the option to use high-quality VLMs only when necessary. Language support emphasizes English and Amharic to match the target corpus. Thresholds are conservative defaults to avoid false accepts; they will be refined after initial experiments.

***
Generated: 2026-03-04

