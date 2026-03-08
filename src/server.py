import os
import shutil
import uuid
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import dotenv
dotenv.load_dotenv()

from .agents.triage import TriageAgent
from .agents.extractor import ExtractionRouter
from .agents.chunker import ChunkingEngine
from .agents.indexer import NavigationAgent
from .agents.query_agent import RefineryAssistant
from .agents.retrieval import RetrievalAgent
from .utils.db_utils import init_db
from .utils.vector_utils import VectorStoreIngestor
from .utils.logging_utils import get_logger

logger = get_logger("refinery_server")

app = FastAPI(title="Document Intelligence Refinery API")

# Enable CORS for frontend integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "data/uploads"
DATA_DIR = "data"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(".refinery/profiles", exist_ok=True)

def resolve_file_path(doc_id: str) -> str:
    """Resolve doc_id to a file path, checking corpus and uploads."""
    # Check data/ (corpus)
    corpus_path = os.path.join(DATA_DIR, doc_id)
    if os.path.exists(corpus_path):
        return corpus_path
    # Check data/uploads/ (user-uploaded)
    upload_path = os.path.join(UPLOAD_DIR, doc_id)
    if os.path.exists(upload_path):
        return upload_path
    return None

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    init_db()

class QueryRequest(BaseModel):
    doc_id: str
    query: str

class AuditRequest(BaseModel):
    doc_id: str
    claim: str

@app.get("/files")
async def list_files():
    files = [f for f in os.listdir("data") if f.endswith(".pdf")]
    return {"files": files}

@app.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    file_id = str(uuid.uuid4())
    extension = os.path.splitext(file.filename)[1]
    file_path = os.path.join(UPLOAD_DIR, f"{file_id}{extension}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    return {"doc_id": f"{file_id}{extension}", "filename": file.filename}

@app.get("/triage/{doc_id:path}")
async def triage_document(doc_id: str):
    file_path = resolve_file_path(doc_id)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found in corpus or uploads")
    
    triage_agent = TriageAgent()
    profile = triage_agent.triage_document(file_path)
    
    # Save profile
    profile_path = os.path.join(".refinery/profiles", f"{doc_id}.json")
    with open(profile_path, "w") as f:
        f.write(profile.model_dump_json(indent=2))
        
    return profile

@app.get("/extract/{doc_id:path}")
async def extract_document(doc_id: str):
    file_path = resolve_file_path(doc_id)
    if not file_path:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
    
    # Load profile
    profile_path = os.path.join(".refinery/profiles", f"{doc_id}.json")
    if not os.path.exists(profile_path):
        # Trigger triage if not profiled
        triage_agent = TriageAgent()
        profile = triage_agent.triage_document(file_path)
    else:
        from .models.triage import DocumentProfile
        with open(profile_path, "r") as f:
            profile = DocumentProfile.model_validate_json(f.read())

    router = ExtractionRouter()
    # Limit to first 5 pages for demo parity with main.py
    results = router.extract_document(file_path, profile, page_range=(1, 5))
    
    # Process for frontend (serialize complex objects)
    output = []
    for res in results:
        if res.error:
            output.append({"page": res.page_number, "error": res.error})
        else:
            output.append({
                "page": res.page_number,
                "strategy": res.strategy_used,
                "confidence": res.confidence_score,
                "content": res.content.model_dump() if res.content else None
            })
    return output

@app.get("/pageindex/{doc_id:path}")
async def get_pageindex(doc_id: str):
    # This assumes chunks were already generated and index built
    # In a full flow, this might trigger the chunker/indexer
    nav_agent = NavigationAgent()
    page_index = nav_agent.load_tree(doc_id)
    if not page_index:
        # Try to build it by running the full pipeline first
        file_path = resolve_file_path(doc_id)
        if not file_path:
            raise HTTPException(status_code=404, detail=f"Document '{doc_id}' not found")
        # Run full pipeline inline
        from .agents.triage import TriageAgent as _TA
        from .agents.extractor import ExtractionRouter as _ER
        _profile = _TA().triage_document(file_path)
        _results = _ER().extract_document(file_path, _profile, page_range=(1, 10))
        _docs = [r.content for r in _results if not r.error]
        _chunks = ChunkingEngine().chunk_document(doc_id, _docs)
        page_index = NavigationAgent().build_tree(doc_id, _chunks)
        if _chunks:
            VectorStoreIngestor().ingest_chunks(_chunks)
    if not page_index:
        raise HTTPException(status_code=404, detail="Could not build PageIndex for this document.")
    return page_index

@app.post("/query")
async def query_document(request: QueryRequest):
    nav_agent = NavigationAgent()
    ret_agent = RetrievalAgent()
    page_index = nav_agent.load_tree(request.doc_id)
    
    if not page_index:
        raise HTTPException(status_code=404, detail="PageIndex not found")
        
    assistant = RefineryAssistant(
        nav_agent=nav_agent,
        ret_agent=ret_agent,
        page_index=page_index
    )
    
    response = assistant.run(request.query)
    return {"answer": response}

@app.post("/audit")
async def audit_document(request: AuditRequest):
    nav_agent = NavigationAgent()
    ret_agent = RetrievalAgent()
    page_index = nav_agent.load_tree(request.doc_id)
    
    if not page_index:
        raise HTTPException(status_code=404, detail="PageIndex not found")
        
    assistant = RefineryAssistant(
        nav_agent=nav_agent,
        ret_agent=ret_agent,
        page_index=page_index
    )
    
    response = assistant.audit_claim(request.claim)
    return {"audit_result": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
