import os
from typing import List
try:
    import chromadb
except ImportError:
    chromadb = None
from ..models.chunking import LDU
from ..utils.logging_utils import get_logger

logger = get_logger(__name__)

class VectorStoreIngestor:
    def __init__(self, collection_name: str = "refinery_ldus"):
        self.collection_name = collection_name
        self.persist_directory = ".refinery/vector_store"
        os.makedirs(self.persist_directory, exist_ok=True)
        
        if chromadb:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.client = chromadb.PersistentClient(path=self.persist_directory)
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            logger.info(f"Vector store initialized with collection '{collection_name}' at {self.persist_directory}")
        else:
            logger.warning("chromadb not installed. Vector store ingestion will be a placeholder.")

    def ingest_chunks(self, chunks: List[LDU]):
        if not chromadb:
            logger.warning("Skipping ingestion: chromadb missing.")
            return

        # Deduplicate chunks by ID to avoid ChromaDB error
        seen_ids = set()
        unique_chunks = []
        for c in chunks:
            if c.id not in seen_ids:
                unique_chunks.append(c)
                seen_ids.add(c.id)
        
        if not unique_chunks:
            logger.warning("No unique chunks to ingest. Skipping vector store update.")
            return
        
        if len(unique_chunks) < len(chunks):
            logger.warning(f"Deduplicated {len(chunks) - len(unique_chunks)} chunks before ingestion.")

        documents = [c.content for c in unique_chunks]
        metadatas = []
        for c in unique_chunks:
            metadatas.append({
                "chunk_id": c.id,
                "type": c.chunk_type.value,
                "pages": ",".join(map(str, c.page_refs)),
                "section": c.parent_section or "None",
                "doc_id": c.metadata.get("doc_id", "Unknown")
            })
        ids = [c.id for c in unique_chunks]
        # Generate embeddings
        embeddings = self.model.encode(documents).tolist()

        self.collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings
        )
        logger.info(f"Successfully ingested {len(unique_chunks)} chunks into vector store.")

    def search(self, query: str, top_k: int = 5, section_filter: List[str] = None):
        if not chromadb:
            return {"documents": [[]], "metadatas": [[]]}
            
        where = None
        if section_filter:
            where = {"section": {"$in": section_filter}}
            
        return self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where
        )
