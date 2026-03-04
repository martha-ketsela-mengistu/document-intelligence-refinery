Feature: Document Intelligence Refinery

Short description
-----------------
Build a multi-stage, agentic pipeline that converts heterogeneous document corpora (native PDFs, scanned documents, slide decks, images, spreadsheets) into structured, queryable, provenance-preserving knowledge. The pipeline uses a Triage Agent to classify documents, a Multi-Strategy Extractor (fast OCR → layout-aware → vision-augmented) with confidence-gated escalation, a Semantic Chunking Engine to emit Logical Document Units (LDUs), a PageIndex for hierarchical navigation, and a Query Interface that always returns a ProvenanceChain for each answer.

Actors
------
- Document Ingestor (automated or user-initiated)
- Forward Deployed Engineer (FDE) / Data Steward
- Retrieval Agent / LLMs used by analysts
- Audit/Compliance reviewer

Scope and goals
---------------
- Ingest a heterogeneous corpus and produce:
  - `DocumentProfile` per document (origin, layout, domain hint, extraction cost estimate)
  - `ExtractedDocument` normalized structure (text blocks, tables, figures, bboxes)
  - LDUs (chunked units with content_hash and provenance)
  - PageIndex (hierarchical section tree with summaries)
  - Vector store ingestion and a small fact table for numeric facts
  - Query interface that returns answers plus a ProvenanceChain
- Preserve spatial provenance (page, bounding box, content_hash) for every emitted fact
- Cost-optimization: prefer low-cost extractors and escalate only on low confidence

Non-goals
---------
- Prescribe specific ML model implementations or cloud vendor APIs in the spec (deferred to implementation). This spec defines WHAT, not HOW.

Key data and constraints
------------------------
- Inputs: PDFs (native + scanned), images, slide decks, Office docs, CSV/Excel
- Outputs: JSON schemas, PageIndex JSON, vector embeddings, SQLite fact table
- Every extracted item must include: `document_id`, `page_number`, `bbox` (x0,y0,x1,y1 in PDF points), `content_hash`.
- Budget guard: vision-based extraction is allowable but must be rate/budget limited per-document (parameterized).

Assumptions
-----------
- Reasonable defaults used unless clarified:
  - Start numbering at `1` for the feature branch and `specs/1-document-refinery/` for spec files.
  - Vector store is a local, free-tier-compatible solution (e.g., FAISS/Chroma) unless otherwise specified.
  - Language support: primary demonstrations in English; multi-language support will be additive.

[NEEDS CLARIFICATION: VLM Provider & Per-document Budget Cap]

[NEEDS CLARIFICATION: Required language coverage and OCR fallback policy for low-resource languages]

User scenarios & testing
------------------------
1. Triage
   - Input: Drop a 40-page annual report PDF.
   - Expected: `DocumentProfile` with `origin_type=native_digital`, `layout_complexity=multi_column`, `estimated_extraction_cost=needs_layout_model`.
   - Test: Assert profile fields are populated and persisted to `.refinery/profiles/{doc_id}.json`.

2. Extraction & Escalation
   - Input: The same document; run ExtractionRouter.
   - Expected: Strategy B selected; pages with tables extracted as structured JSON; low-confidence pages retried with Strategy C.
   - Test: Inspect `.refinery/extraction_ledger.jsonl` for strategy_used, confidence_score, cost_estimate.

3. Chunking & PageIndex
   - Input: ExtractedDocument.
   - Expected: LDUs emitted respecting chunking rules (table cells not split from headers, captions attached), PageIndex tree built with summaries.
   - Test: Validate no LDU violates chunking rules; PageIndex nodes include `page_start`, `page_end`, `summary`.

4. Query & Provenance
   - Input: Natural language query about a numeric fact.
   - Expected: Answer with `ProvenanceChain` referencing doc, page, bbox, and content_hash; verification opens cited page and highlights bbox.
   - Test: Automated test verifies cited text exists in original PDF stream or OCR text and content_hash matches.

Functional requirements (testable)
---------------------------------
FR-1: Document profiling
- Given any input document, produce a `DocumentProfile` JSON with fields: `origin_type`, `layout_complexity`, `language` (+confidence), `domain_hint`, `estimated_extraction_cost`.
- Acceptance: Unit tests feed representative files and assert correct `origin_type` and `layout_complexity` for ≥90% of test set.

FR-2: Multi-strategy extraction router
- Given `DocumentProfile`, select extractor A/B/C and log decision to `.refinery/extraction_ledger.jsonl` with `confidence_score` (0–1) and `cost_estimate`.
- Acceptance: Integration test asserts escalation occurs when Strategy A confidence < threshold.

FR-3: Normalized extraction schema
- All extractors must output `ExtractedDocument` conforming to schema: text blocks (text, bbox, page), tables (headers, rows, bboxes), figures (caption, bbox), reading_order.
- Acceptance: Schema validation tests pass for outputs of each extractor.

FR-4: Semantic chunking
- ChunkingEngine emits LDUs with fields: `id`, `content`, `chunk_type`, `page_refs`, `bbox`, `parent_section`, `token_count`, `content_hash`.
- Acceptance: ChunkValidator enforces chunking constitution; unit tests assert no rule violations on sample docs.

FR-5: PageIndex builder
- Build hierarchical section tree nodes with: `title`, `page_start`, `page_end`, `child_sections`, `key_entities`, `summary`, `data_types_present`.
- Acceptance: Query that asks for a topical section returns the correct top-3 sections in manual validation.

FR-6: Provenance in query responses
- All query responses include a `ProvenanceChain` listing sources with `document_name`, `page_number`, `bbox`, and `content_hash`.
- Acceptance: Random QA checks validate that each cited source matches original PDF content.

Success criteria (measurable)
---------------------------
- C1: Extraction fidelity — Table extraction precision ≥85% and recall ≥80% on held-out Class D documents.
- C2: Escalation effectiveness — For pages Strategy A flags as low-confidence, Strategy B/C recovers correct structure in ≥90% of retries.
- C3: Provenance verifiability — 100% of cited provenance entries correspond to an exact substring or OCR text span in the source PDF.
- C4: Cost control — Average per-document VLM spend (estimated) remains below configurable budget cap for 95% of processed docs.
- C5: Developer enablement — FDE can onboard a new document type by only adjusting `rubric/extraction_rules.yaml` (no code changes) and process sample documents within 24 hours.

Key entities
------------
- DocumentProfile
- ExtractedDocument
- LDU (Logical Document Unit)
- PageIndex (Section nodes)
- ProvenanceChain
- ExtractionLedgerEntry

Out-of-scope decisions and implementation notes
----------------------------------------------
- This spec intentionally avoids locking to a single cloud vendor or model provider. The implementation will provide adapters for ML/VLM providers.

SPEC READY: This document provides the required sections and testable requirements. Proceed to create spec file in `specs/1-document-refinery/spec.md` and the checklist in `specs/1-document-refinery/checklists/requirements.md`.
