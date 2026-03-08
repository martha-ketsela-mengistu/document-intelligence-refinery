import hashlib
import re
import json
import os
from typing import List, Optional, Dict, Any
import time
from ..models.extraction import ExtractedDocument, TextBlock, Table, Figure
from ..models.chunking import LDU, ChunkType
from ..models.base import BoundingBox
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class ChunkingEngine:
    def __init__(self, rules: Optional[dict] = None):
        self.rules = rules or {
            "max_tokens_per_ldu": 1024,
            "table_cell_split": False,
            "caption_attached_to_figure": True,
            "numbered_list_as_single_ldu": True,
            "section_headers_as_parent_metadata": True,
            "resolve_cross_references": True,
            "ledger_path": ".refinery/chunking_ledger.jsonl"
        }
        self.current_section = None
        self.token_ratio = 0.75 # Estimated words per token
        os.makedirs(os.path.dirname(self.rules["ledger_path"]), exist_ok=True)

    def chunk_document(self, document_id: str, pages: List[ExtractedDocument]) -> List[LDU]:
        logger.info(f"Chunking document {document_id} ({len(pages)} pages)...")
        start_time = time.time()
        
        all_chunks = []
        for page in pages:
            all_chunks.extend(self.process_page(page))
        
        # Rule 5: Cross-reference resolution (second pass)
        if self.rules["resolve_cross_references"]:
            all_chunks = self._resolve_cross_references(all_chunks)
            
        duration = time.time() - start_time
        logger.info(f"Chunking finished for {document_id}. Generated {len(all_chunks)} LDUs in {duration:.2f}s.")
        self._log_to_ledger(document_id, len(pages), len(all_chunks), duration)
        return all_chunks

    def _log_to_ledger(self, doc_id: str, page_count: int, ldu_count: int, duration: float):
        entry = {
            "doc_id": doc_id,
            "page_count": page_count,
            "ldu_count": ldu_count,
            "processing_time": duration,
            "timestamp": time.time()
        }
        with open(self.rules["ledger_path"], "a") as f:
            f.write(json.dumps(entry) + "\n")

    def process_page(self, page: ExtractedDocument) -> List[LDU]:
        logger.info(f"Processing page {page.page_number} of document {page.document_id}...")
        page_chunks = []
        
        # Sort items by vertical position for reading order if not provided
        # For now, we trust the reading_order if it exists, otherwise we'll simplify
        
        # Rule 3: Collect potential list items
        pending_list = []
        
        # Rule 2 & 5 state management
        self.figures_on_page = page.figures
        self.tables_on_page = page.tables
        
        for item_id in page.reading_order:
            item = self._get_item_by_id(page, item_id)
            if not item: continue

            if isinstance(item, TextBlock):
                # Rule 2: Figure Caption Detection & Suppression
                if self._is_figure_caption(item):
                    # Check if this caption belongs to a figure on the same page
                    if self._link_caption_to_figure(item):
                        continue # Skip creating a separate LDU for the caption

                # Rule 4: Header Detection
                if self._is_header(item):
                    self.current_section = item.text
                    ldu = self._create_ldu(item, ChunkType.HEADING, page.document_id)
                    page_chunks.append(ldu)
                    continue

                # Rule 3: List Detection
                if self._is_list_item(item):
                    pending_list.append(item)
                    continue
                else:
                    if pending_list:
                        page_chunks.append(self._group_list_to_ldu(pending_list, page.document_id))
                        pending_list = []
                
                # Rule 2: Figure Caption Detection (simplified)
                # If it looks like a caption, wait to see if it belongs to a figure
                if self._is_figure_caption(item):
                    # We'll handle this in the figure pass or by looking ahead
                    # For now, let's just make it a text block if no figure found
                    pass

                ldu = self._create_ldu(item, ChunkType.TEXT, page.document_id)
                page_chunks.append(ldu)

            elif isinstance(item, Table):
                # Rule 1: Tables are atomic
                ldu = self._create_ldu(item, ChunkType.TABLE, page.document_id)
                page_chunks.append(ldu)

            elif isinstance(item, Figure):
                # Rule 2: Figures with metadata
                ldu = self._create_ldu(item, ChunkType.FIGURE, page.document_id)
                page_chunks.append(ldu)

        if pending_list:
            page_chunks.append(self._group_list_to_ldu(pending_list, page.document_id))

        return page_chunks

    def _get_item_by_id(self, page: ExtractedDocument, item_id: str):
        for b in page.text_blocks:
            if b.content_hash == item_id: return b
        for t in page.tables:
            if t.content_hash == item_id: return t
        for f in page.figures:
            if f.content_hash == item_id: return f
        return None

    def _is_header(self, block: TextBlock) -> bool:
        # Heuristic: Starts with numbers (1.1, 2.), short, or uppercase
        # return bool(re.match(r'^\d+(\.\d+)*\s+[A-Z]', block.text)) or (len(block.text) < 100 and block.text.isupper())
        # Let's be a bit more flexible for the demo
        return bool(re.match(r'^(\d+\.)+\d*\s*\w+', block.text.strip())) or (len(block.text.strip()) < 80 and block.text.strip().isupper())

    def _is_list_item(self, block: TextBlock) -> bool:
        # Heuristic: Starts with bullet or number
        return bool(re.match(r'^[\u2022\u00b7\-\*]\s+', block.text.strip())) or bool(re.match(r'^\d+[\.\)]\s+', block.text.strip()))

    def _is_figure_caption(self, block: TextBlock) -> bool:
        return bool(re.match(r'^(Figure|Fig|Table|Image)\s+\d+', block.text.strip(), re.I))

    def _create_ldu(self, item: Any, chunk_type: ChunkType, doc_id: str) -> LDU:
        content = ""
        metadata = {"original_hash": item.content_hash, "doc_id": doc_id}
        
        if isinstance(item, TextBlock):
            content = item.text
        elif isinstance(item, Table):
            # Atomic table representation
            content = f"Table: {item.headers}\n" + "\n".join([str(r) for r in item.rows])
        elif isinstance(item, Figure):
            content = f"[Figure: {item.caption or 'No caption'}]"
            metadata["caption"] = item.caption
            metadata["alt_text"] = item.alt_text

        # Generate content hash: doc_id + page + bbox + text hash
        bbox_str = f"{item.bbox.x0},{item.bbox.y0},{item.bbox.x1},{item.bbox.y1}"
        hash_input = f"{doc_id}:{item.page_number}:{bbox_str}:{content}"
        content_hash = hashlib.md5(hash_input.encode()).hexdigest()

        return LDU(
            id=f"ldu_{content_hash}",
            content=content,
            chunk_type=chunk_type,
            page_refs=[item.page_number],
            bbox=item.bbox,
            parent_section=self.current_section,
            token_count=int(len(content.split()) / self.token_ratio),
            content_hash=content_hash,
            metadata=metadata
        )

    def _group_list_to_ldu(self, blocks: List[TextBlock], doc_id: str) -> LDU:
        content = "\n".join([b.text for b in blocks])
        # Combine bboxes for the list
        x0 = min(b.bbox.x0 for b in blocks)
        y0 = min(b.bbox.y0 for b in blocks)
        x1 = max(b.bbox.x1 for b in blocks)
        y1 = max(b.bbox.y1 for b in blocks)
        
        # Simplified hash for group
        hash_input = f"{doc_id}:{blocks[0].page_number}:list:{content[:200]}"
        content_hash = hashlib.md5(hash_input.encode()).hexdigest()

        return LDU(
            id=f"ldu_list_{content_hash}",
            content=content,
            chunk_type=ChunkType.LIST,
            page_refs=list(set(b.page_number for b in blocks)),
            bbox=BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1),
            parent_section=self.current_section,
            token_count=int(len(content.split()) / self.token_ratio),
            content_hash=content_hash,
            metadata={"item_count": len(blocks), "doc_id": doc_id}
        )

    def _link_caption_to_figure(self, block: TextBlock) -> bool:
        # Rule 2: Link caption to the closest figure vertically
        for fig in self.figures_on_page:
            # If the block is within 50 units vertically of the figure
            if abs(block.bbox.y0 - fig.bbox.y1) < 50 or abs(block.bbox.y1 - fig.bbox.y0) < 50:
                # Update figure caption if it was empty or mismatched
                if not fig.caption or len(block.text) > len(fig.caption):
                    fig.caption = block.text
                return True
        return False

    def _resolve_cross_references(self, chunks: List[LDU]) -> List[LDU]:
        # Rule 5: Simple regex resolution
        # Find all chunks that are tables or figures to build a registry
        registry = {}
        for c in chunks:
            if c.chunk_type == ChunkType.TABLE:
                # Try to find a table number in content (e.g. "Table 1")
                match = re.search(r'Table\s+(\d+)', c.content, re.I)
                if match: registry[f"table_{match.group(1)}"] = c.id
            elif c.chunk_type == ChunkType.FIGURE:
                match = re.search(r'Figure\s+(\d+)', c.content, re.I)
                if match: registry[f"figure_{match.group(1)}"] = c.id

        # Second pass: link references in text
        for c in chunks:
            refs = []
            # Find "See Table 1" or similar
            table_refs = re.findall(r'Table\s+(\d+)', c.content, re.I)
            for r in table_refs:
                key = f"table_{r}"
                if key in registry: refs.append(registry[key])
            
            fig_refs = re.findall(r'Figure\s+(\d+)', c.content, re.I)
            for r in fig_refs:
                key = f"figure_{r}"
                if key in registry: refs.append(registry[key])
            
            if refs:
                c.metadata["cross_references"] = list(set(refs))
                
        return chunks

class ChunkValidator:
    def validate(self, chunks: List[LDU]) -> List[str]:
        errors = []
        for ldu in chunks:
            # Rule 1 Check
            if ldu.chunk_type == ChunkType.TABLE:
                if "Table:" not in ldu.content:
                    errors.append(f"LDU {ldu.id}: Table structure missing headers/data")
            
            # Rule 4 Check
            if not ldu.parent_section and ldu.chunk_type != ChunkType.HEADING:
                # In some docs there might be text before any header, but usually we expect a header
                pass

            # Token Limit Check
            if ldu.token_count > 1024:
                errors.append(f"LDU {ldu.id}: Exceeds max token count ({ldu.token_count})")

        return errors
