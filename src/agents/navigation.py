import os
import re
import json
from typing import List, Optional, Dict
import time
from ollama import Client
from ..models.chunking import LDU, ChunkType
from ..models.navigation import PageIndex, PageIndexNode
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class NavigationAgent:
    def __init__(self, ollama_host: Optional[str] = None, model: str = "qwen3-vl:235b-instruct"):
        self.client = Client(host=ollama_host or os.getenv("OLLAMA_HOST", "https://ollama.com"))
        self.model = model
        self.ledger_path = ".refinery/navigation_ledger.jsonl"
        self.stats = {"summary_calls": 0, "ner_calls": 0, "llm_duration": 0.0}
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

    def build_tree(self, document_id: str, chunks: List[LDU]) -> PageIndex:
        logger.info(f"Building PageIndex for {document_id} from {len(chunks)} chunks...")
        start_time = time.time()
        
        # 1. Group chunks by their parent section
        sections_map: Dict[str, List[LDU]] = {}
        for chunk in chunks:
            parent = chunk.parent_section or "Root"
            if parent not in sections_map:
                sections_map[parent] = []
            sections_map[parent].append(chunk)

        # 2. Identify top-level sections (those that appear as ChunkType.HEADING)
        headings = [c for c in chunks if c.chunk_type == ChunkType.HEADING]
        
        # 3. Build recursive structure
        # For simplicity, we'll assume a flat hierarchy for now if no numbering is present,
        # or use regex to infer level (e.g., 1. vs 1.1)
        root_node = PageIndexNode(
            title="Document Root",
            page_start=min(c.page_refs[0] for c in chunks) if chunks else 1,
            page_end=max(c.page_refs[-1] for c in chunks) if chunks else 1,
            summary="Full document overview",
            data_types_present=list(set(c.chunk_type.value for c in chunks))
        )

        current_nodes = {"Root": root_node}
        
        for heading in headings:
            title = heading.content.strip()
            # Extract content for this section
            section_chunks = sections_map.get(title, [])
            content_text = " ".join([c.content for c in section_chunks])
            
            summary = self._generate_summary(title, content_text)
            entities = self._extract_entities(title, content_text)
            
            node = PageIndexNode(
                title=title,
                page_start=heading.page_refs[0],
                page_end=max([c.page_refs[-1] for c in section_chunks] + [heading.page_refs[-1]]),
                summary=summary,
                data_types_present=list(set(c.chunk_type.value for c in section_chunks)),
                key_entities=entities
            )
            
            # Simple parent matching logic: if 1.1, look for 1.
            parent_title = self._infer_parent(title, list(current_nodes.keys()))
            if parent_title and parent_title in current_nodes:
                current_nodes[parent_title].child_sections.append(node)
            else:
                root_node.child_sections.append(node)
            
            current_nodes[title] = node

        duration = time.time() - start_time
        logger.info(f"PageIndex built for {document_id} with {len(current_nodes)} sections in {duration:.2f}s.")
        self._log_to_ledger(document_id, len(current_nodes), duration)
        return PageIndex(document_id=document_id, root=root_node)

    def _log_to_ledger(self, doc_id: str, section_count: int, total_duration: float):
        entry = {
            "doc_id": doc_id,
            "sections": section_count,
            "total_time": total_duration,
            "llm_stats": self.stats,
            "timestamp": time.time()
        }
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _generate_summary(self, title: str, text: str) -> str:
        self.stats["summary_calls"] += 1
        if not text.strip():
            return f"Section: {title}"
        
        logger.debug(f"Generating summary for section: {title}")
        prompt = f"Summarize the following section of a document titled '{title}' in one short sentence:\n\n{text[:2000]}"
        start = time.time()
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            self.stats["llm_duration"] += (time.time() - start)
            return response.get("response", f"Summary for {title}").strip()
        except Exception as e:
            logger.error(f"Failed to generate summary for {title}: {str(e)}")
            return f"Overview of {title}"

    def _extract_entities(self, title: str, text: str) -> List[str]:
        self.stats["ner_calls"] += 1
        if not text.strip():
            return []
        
        logger.debug(f"Extracting entities for section: {title}")
        prompt = f"""
        Extract key entities (Organizations, People, Locations, Dates) from the following text in section '{title}'.
        Return only a comma-separated list of entities. If none found, return empty.
        
        Text: {text[:1500]}
        """
        start = time.time()
        try:
            response = self.client.generate(model=self.model, prompt=prompt, stream=False)
            self.stats["llm_duration"] += (time.time() - start)
            raw = response.get("response", "").strip()
            # Basic cleanup of comma separated list
            entities = [e.strip() for e in raw.split(',') if e.strip()]
            return list(set(entities))[:10] # Limit to top 10
        except Exception as e:
            logger.error(f"Failed to extract entities for {title}: {str(e)}")
            return []

    def _infer_parent(self, title: str, existing_titles: List[str]) -> Optional[str]:
        # Implementation of rule-based hierarchy inference (e.g., "1.1" -> "1.")
        match = re.match(r'^(\d+\.)+(\d+)', title)
        if match:
            parts = title.split('.')
            if len(parts) > 1:
                parent_prefix = ".".join(parts[:-1])
                for t in existing_titles:
                    if t.startswith(parent_prefix):
                        return t
        return None

    def query_index(self, index: PageIndex, query: str) -> List[PageIndexNode]:
        """Traverse the tree to find top-3 most relevant sections based on title/summary."""
        relevant_nodes = []
        self._search_nodes(index.root, query, relevant_nodes)
        
        # Sort by simple inclusion/relevance (placeholder for semantic ranking)
        relevant_nodes.sort(key=lambda n: (query.lower() in n.summary.lower() or query.lower() in n.title.lower()), reverse=True)
        return relevant_nodes[:3]

    def _search_nodes(self, node: PageIndexNode, query: str, results: List[PageIndexNode]):
        if node.title != "Document Root":
            results.append(node)
        for child in node.child_sections:
            self._search_nodes(child, query, results)
