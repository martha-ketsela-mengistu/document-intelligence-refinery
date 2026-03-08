from typing import List, Optional
import time
import json
import os
import chromadb
from sentence_transformers import SentenceTransformer
from ..models.chunking import LDU
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class RetrievalAgent:
    def __init__(self, collection_name: str = "refinery_ldus", persist_directory: str = ".refinery/vector_store"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.model = SentenceTransformer('all-MiniLM-L6-v2')
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        self.ledger_path = ".refinery/retrieval_ledger.jsonl"
        os.makedirs(os.path.dirname(self.ledger_path), exist_ok=True)

    def ingest_ldus(self, ldus: List[LDU]):
        logger.info(f"Ingesting {len(ldus)} chunks into vector store...")
        start_time = time.time()
        
        # De-duplicate LDUs by ID to prevent ChromaDB errors
        seen_ids = set()
        unique_ldus = []
        for ldu in ldus:
            if ldu.id not in seen_ids:
                unique_ldus.append(ldu)
                seen_ids.add(ldu.id)
        
        if not unique_ldus:
            return

        ids = [ldu.id for ldu in unique_ldus]
        documents = [ldu.content for ldu in unique_ldus]
        metadatas = [
            {
                "type": ldu.chunk_type.value,
                "section": ldu.parent_section or "N/A",
                "pages": ",".join(map(str, ldu.page_refs)),
                "hash": ldu.content_hash,
                "bbox": json.dumps(ldu.bbox.to_tuple()) if hasattr(ldu, 'bbox') and ldu.bbox else "N/A",
                "doc_id": ldu.metadata.get("doc_id", "Unknown") if isinstance(ldu.metadata, dict) else "Unknown"
            } for ldu in unique_ldus
        ]
        
        # Generate embeddings
        embeddings = self.model.encode(documents).tolist()
        
        self.collection.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
            embeddings=embeddings
        )
        duration = time.time() - start_time
        logger.info(f"Ingestion complete. {len(unique_ldus)} unique LDUs added in {duration:.2f}s.")
        self._log_to_ledger("ingestion", {"ldu_count": len(unique_ldus)}, duration)

    def search(self, query: str, top_k: int = 5, section_filter: Optional[List[str]] = None) -> List[dict]:
        logger.info(f"Performing vector search (top_k={top_k}, filter={section_filter})...")
        start_time = time.time()
        query_embedding = self.model.encode([query]).tolist()
        
        where_clause = {}
        if section_filter:
            if len(section_filter) == 1:
                where_clause = {"section": section_filter[0]}
            else:
                where_clause = {"section": {"$in": section_filter}}

        results = self.collection.query(
            query_embeddings=query_embedding,
            n_results=top_k,
            where=where_clause if section_filter else None
        )
        
        duration = time.time() - start_time
        logger.info(f"Search complete in {duration:.2f}s. Found {len(results['documents'][0])} results.")
        self._log_to_ledger("search", {"query": query, "top_k": top_k, "result_count": len(results['documents'][0])}, duration)
        return results

    def _log_to_ledger(self, action: str, metadata: dict, duration: float):
        entry = {
            "action": action,
            "metadata": metadata,
            "duration": duration,
            "timestamp": time.time()
        }
        with open(self.ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
