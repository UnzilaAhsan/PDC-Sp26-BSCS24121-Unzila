"""
FastAPI Main Application with Circuit Breaker for LLM
Student ID: BSCS24121
"""

import asyncio
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List
import time

from middleware import StudentIDMiddleware
from llm_service import LLMService

# Initialize FastAPI
app = FastAPI(title="StudySync API", description="Resilient Distributed System Demo")

# Add custom middleware (REQUIRED for assignment)
app.add_middleware(StudentIDMiddleware)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize LLM Service
# In production, load from env var
llm_service = LLMService(api_key="sk-demo-key-do-not-use-in-production")


# ========== MODELS ==========

class SuggestionRequest(BaseModel):
    prompt: str
    document_id: Optional[str] = None


class SuggestionResponse(BaseModel):
    suggestion: str
    from_cache: bool
    circuit_state: str
    response_time_ms: float


# ========== PROBLEM 3: FAULT TOLERANT LLM ENDPOINT ==========

@app.post("/api/suggest", response_model=SuggestionResponse)
async def get_suggestion(request: SuggestionRequest):
    """
    Generate AI suggestion for document editing.
    Protected by Circuit Breaker - never hangs more than 3 seconds.
    """
    start_time = time.time()
    
    # Call LLM with circuit breaker protection
    result = await llm_service.generate_suggestion(request.prompt)
    
    response_time = (time.time() - start_time) * 1000
    
    # Extract suggestion text
    try:
        suggestion = result.get("choices", [{}])[0].get("message", {}).get("content", str(result))
    except:
        suggestion = str(result)
    
    # Determine if response came from cache/mock
    from_cache = "_cached" in result or "_fallback_reason" in result
    
    return SuggestionResponse(
        suggestion=suggestion,
        from_cache=from_cache,
        circuit_state=llm_service.circuit_breaker.state.value,
        response_time_ms=round(response_time, 2)
    )


@app.get("/api/circuit-status")
async def get_circuit_status():
    """Monitoring endpoint to check circuit breaker state."""
    return llm_service.get_circuit_status()


# ========== PROBLEM 1: OPTIMISTIC LOCKING (Bonus implementation) ==========

# In-memory document store with versioning
documents: Dict[str, Dict] = {
    "doc1": {
        "id": "doc1",
        "content": "Initial document content",
        "version": 1,
        "last_modified": time.time()
    }
}


class DocumentUpdate(BaseModel):
    content: str
    expected_version: int


@app.get("/api/documents/{doc_id}")
async def get_document(doc_id: str):
    """Get document with current version number."""
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"id": doc_id, "content": documents[doc_id]["content"], "version": documents[doc_id]["version"]}


@app.put("/api/documents/{doc_id}")
async def update_document(doc_id: str, update: DocumentUpdate):
    """
    Update document with optimistic locking.
    Returns 409 Conflict if version mismatch (lost update detected).
    """
    if doc_id not in documents:
        raise HTTPException(status_code=404, detail="Document not found")
    
    doc = documents[doc_id]
    
    # Optimistic locking check
    if update.expected_version != doc["version"]:
        raise HTTPException(
            status_code=409,
            detail=f"Conflict: Document version {doc['version']} does not match expected {update.expected_version}. Please refresh and retry."
        )
    
    # Update document
    doc["content"] = update.content
    doc["version"] += 1
    doc["last_modified"] = time.time()
    
    return {"id": doc_id, "content": doc["content"], "version": doc["version"], "success": True}


# ========== HEALTH CHECK ==========

@app.get("/health")
async def health_check():
    """Simple health check endpoint."""
    return {"status": "healthy", "circuit_state": llm_service.circuit_breaker.state.value}