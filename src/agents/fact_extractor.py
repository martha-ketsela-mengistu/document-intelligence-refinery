import os
import json
import hashlib
from typing import List, Optional
from ollama import Client
from ..models.chunking import LDU, ChunkType
from ..models.extraction import FactEntry
from ..utils.db_utils import insert_facts, init_db
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class FactExtractor:
    def __init__(self, ollama_host: Optional[str] = None, model: str = "qwen3-vl:235b-instruct"):
        self.client = Client(host=ollama_host or os.getenv("OLLAMA_HOST", "https://ollama.com"))
        self.model = model
        init_db()

    def extract_facts(self, doc_id: str, chunks: List[LDU]) -> List[FactEntry]:
        """Process chunks to extract structured numerical/financial facts."""
        logger.info(f"Extracting facts for {doc_id} from {len(chunks)} chunks...")
        
        all_facts = []
        # Focus on tables and lists as they are most likely to contain dense facts
        # But also scan text chunks that might contain financial figures
        for chunk in chunks:
            if chunk.chunk_type in [ChunkType.TABLE, ChunkType.LIST] or any(char.isdigit() for char in chunk.content):
                facts = self._extract_from_chunk(doc_id, chunk)
                all_facts.extend(facts)
        
        # Save to DB
        db_entries = []
        for f in all_facts:
            db_entries.append({
                "id": f"{f.doc_id}_{f.content_hash[:8]}",
                "doc_id": f.doc_id,
                "entity": f.entity,
                "attribute": f.attribute,
                "value": f.value,
                "unit": f.unit,
                "page_number": f.page_number,
                "bbox_json": json.dumps(f.bbox.to_tuple()),
                "content_hash": f.content_hash
            })
        
        if db_entries:
            insert_facts(db_entries)
            
        logger.info(f"Total facts extracted and stored for {doc_id}: {len(all_facts)}")
        return all_facts

    def _extract_from_chunk(self, doc_id: str, chunk: LDU) -> List[FactEntry]:
        """Use LLM to identify and extract facts from a single chunk."""
        prompt = f"""
        Extract key-value facts from the following document chunk. 
        Focus on numerical values, dates, financial figures, and specific attributes of entities.
        Format EACH fact as a JSON object with: 'entity', 'attribute', 'value', 'unit'.
        Return a JSON list of these objects. If no facts found, return [].
        
        Chunk content:
        {chunk.content}
        """
        
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            raw_output = response.get("response", "[]")
            
            # Basic JSON parsing from LLM output
            start = raw_output.find("[")
            end = raw_output.rfind("]") + 1
            if start == -1 or end == 0:
                return []
            
            fact_data = json.loads(raw_output[start:end])
            
            extracted = []
            for item in fact_data:
                if all(k in item for k in ['entity', 'attribute', 'value']):
                    # Create content hash for tracing
                    fact_str = f"{item['entity']}_{item['attribute']}_{item['value']}"
                    content_hash = hashlib.md5(fact_str.encode()).hexdigest()
                    
                    extracted.append(FactEntry(
                        doc_id=doc_id,
                        entity=item['entity'],
                        attribute=item['attribute'],
                        value=str(item['value']),
                        unit=item.get('unit'),
                        page_number=chunk.page_refs[0],
                        bbox=chunk.bbox,
                        content_hash=content_hash
                    ))
            return extracted
            
        except Exception as e:
            logger.error(f"Fact extraction failed for chunk: {str(e)}")
            return []
