import json
from src.models import (
    DocumentProfile, OriginType, LayoutComplexity, DomainHint, ExtractionCostTier,
    ExtractedDocument, TextBlock, Table, Figure,
    LDU, ChunkType,
    PageIndex, PageIndexNode,
    ProvenanceChain, ProvenanceEntry
)

def verify_document_profile():
    profile = DocumentProfile(
        document_id="doc_001",
        origin_type=OriginType.NATIVE_DIGITAL,
        layout_complexity=LayoutComplexity.MULTI_COLUMN,
        language={"code": "en", "confidence": 0.99},
        domain_hint=DomainHint.FINANCIAL,
        estimated_extraction_cost=ExtractionCostTier.NEEDS_LAYOUT_MODEL
    )
    print("✓ DocumentProfile validated")
    return profile

def verify_extracted_document():
    doc = ExtractedDocument(
        document_id="doc_001",
        text_blocks=[
            TextBlock(
                document_id="doc_001",
                page_number=1,
                bbox=(50.0, 700.0, 300.0, 750.0),
                content_hash="h1",
                text="This is a heading"
            )
        ],
        tables=[
            Table(
                document_id="doc_001",
                page_number=1,
                bbox=(50.0, 500.0, 500.0, 650.0),
                content_hash="h2",
                headers=["Date", "Revenue"],
                rows=[["2023", "$1B"], ["2024", "$1.2B"]]
            )
        ],
        figures=[
            Figure(
                document_id="doc_001",
                page_number=2,
                bbox=(100.0, 100.0, 400.0, 400.0),
                content_hash="h3",
                caption="Figure 1: Performance Growth"
            )
        ],
        reading_order=["h1", "h2", "h3"]
    )
    print("✓ ExtractedDocument validated")
    return doc

def verify_ldu():
    ldu = LDU(
        id="ldu_001",
        content="2023 revenue was $1B",
        chunk_type=ChunkType.TEXT,
        page_refs=[1],
        bbox=(50.0, 500.0, 500.0, 650.0),
        token_count=10,
        content_hash="h2"
    )
    print("✓ LDU validated")
    return ldu

def verify_page_index():
    node = PageIndexNode(
        title="Introduction",
        page_start=1,
        page_end=2,
        summary="Overview of the annual report goals.",
        data_types_present=["text", "figures"],
        child_sections=[
            PageIndexNode(
                title="Mission Statement",
                page_start=1,
                page_end=1,
                summary="The core focus of the organization.",
                data_types_present=["text"]
            )
        ]
    )
    index = PageIndex(document_id="doc_001", root=node)
    print("✓ PageIndex validated")
    return index

def verify_provenance_chain():
    chain = ProvenanceChain(
        entries=[
            ProvenanceEntry(
                document_name="annual_report_2023.pdf",
                page_number=1,
                bbox=(50.0, 500.0, 500.0, 650.0),
                content_hash="h2"
            )
        ]
    )
    print("✓ ProvenanceChain validated")
    return chain

if __name__ == "__main__":
    try:
        verify_document_profile()
        verify_extracted_document()
        verify_ldu()
        verify_page_index()
        verify_provenance_chain()
        print("\nAll models verified successfully!")
    except Exception as e:
        print(f"\nVerification failed: {e}")
        exit(1)
