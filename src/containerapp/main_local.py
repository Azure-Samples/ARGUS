"""
Local development version of the ARGUS backend
Works without Azure Cosmos DB by using in-memory storage
"""
import logging
import os
import json
import traceback
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Any, List, Optional
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# In-memory storage for local development
documents_storage = {}
config_storage = {}

class DocumentModel(BaseModel):
    id: str
    properties: Dict[str, Any]
    state: Dict[str, bool]
    extracted_data: Dict[str, Any]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str

class DocumentListResponse(BaseModel):
    documents: List[DocumentModel]
    count: int

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize local development environment"""
    logger.info("Starting ARGUS Backend in LOCAL DEVELOPMENT mode")
    logger.info("Note: Using in-memory storage instead of Azure Cosmos DB")
    
    # Create some sample data for testing
    sample_doc = DocumentModel(
        id="sample-invoice-123",
        properties={
            "blob_name": "sample-invoice.pdf",
            "blob_size": 12345,
            "request_timestamp": datetime.now().isoformat(),
            "num_pages": 2
        },
        state={
            "file_landed": True,
            "ocr_completed": True,
            "gpt_extraction_completed": True,
            "gpt_evaluation_completed": False,
            "gpt_summary_completed": False,
            "processing_completed": False
        },
        extracted_data={
            "ocr_output": "Sample OCR text from invoice...",
            "gpt_output": {"invoice_number": "INV-001", "total": 1250.00},
            "gpt_evaluation": {},
            "gpt_summary": ""
        }
    )
    
    documents_storage[sample_doc.id] = sample_doc
    
    logger.info("Successfully initialized local development environment")
    yield
    logger.info("Shutting down local development environment")

# Initialize FastAPI app
app = FastAPI(
    title="ARGUS Backend (Local Development)",
    description="Document processing backend - Local development version",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0-local"
    )

@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents():
    """List all documents"""
    documents = list(documents_storage.values())
    return DocumentListResponse(
        documents=documents,
        count=len(documents)
    )

@app.get("/api/documents/{doc_id}", response_model=DocumentModel)
async def get_document(doc_id: str):
    """Get a specific document by ID"""
    if doc_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return documents_storage[doc_id]

@app.post("/api/documents/{doc_id}")
async def update_document(doc_id: str, document: DocumentModel):
    """Update a document"""
    documents_storage[doc_id] = document
    return {"message": "Document updated successfully", "id": doc_id}

@app.delete("/api/documents/{doc_id}")
async def delete_document(doc_id: str):
    """Delete a document"""
    if doc_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    del documents_storage[doc_id]
    return {"message": "Document deleted successfully", "id": doc_id}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), dataset_name: str = "default-dataset"):
    """Upload a file for processing (mock implementation)"""
    doc_id = f"uploaded-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{file.filename}"
    
    # Create a mock document entry
    document = DocumentModel(
        id=doc_id,
        properties={
            "blob_name": f"{dataset_name}/{file.filename}",
            "blob_size": file.size or 0,
            "request_timestamp": datetime.now().isoformat(),
            "num_pages": 1,  # Mock value
            "dataset": dataset_name
        },
        state={
            "file_landed": True,
            "ocr_completed": False,
            "gpt_extraction_completed": False,
            "gpt_evaluation_completed": False,
            "gpt_summary_completed": False,
            "processing_completed": False
        },
        extracted_data={
            "ocr_output": "",
            "gpt_output": {},
            "gpt_evaluation": {},
            "gpt_summary": ""
        }
    )
    
    documents_storage[doc_id] = document
    
    return {
        "message": "File uploaded successfully",
        "id": doc_id,
        "filename": file.filename,
        "dataset": dataset_name,
        "status": "uploaded"
    }

@app.post("/api/process/{doc_id}")
async def process_document(doc_id: str, background_tasks: BackgroundTasks):
    """Start processing a document (mock implementation)"""
    if doc_id not in documents_storage:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Mock processing - update states progressively
    background_tasks.add_task(mock_process_document, doc_id)
    
    return {
        "message": "Document processing started",
        "id": doc_id,
        "status": "processing"
    }

async def mock_process_document(doc_id: str):
    """Mock document processing function"""
    import asyncio
    
    if doc_id not in documents_storage:
        return
    
    document = documents_storage[doc_id]
    
    # Simulate OCR processing
    await asyncio.sleep(2)
    document.state["ocr_completed"] = True
    document.extracted_data["ocr_output"] = "Mock OCR text extracted from document..."
    
    # Simulate GPT extraction
    await asyncio.sleep(3)
    document.state["gpt_extraction_completed"] = True
    document.extracted_data["gpt_output"] = {
        "document_type": "invoice",
        "total_amount": 1250.00,
        "invoice_number": "INV-001",
        "date": "2024-01-15"
    }
    
    # Simulate GPT evaluation
    await asyncio.sleep(2)
    document.state["gpt_evaluation_completed"] = True
    document.extracted_data["gpt_evaluation"] = {
        "confidence_score": 0.95,
        "quality_score": 0.88
    }
    
    # Simulate GPT summary
    await asyncio.sleep(1)
    document.state["gpt_summary_completed"] = True
    document.extracted_data["gpt_summary"] = "This is a mock summary of the processed document."
    
    # Mark as completed
    document.state["processing_completed"] = True
    
    logger.info(f"Mock processing completed for document {doc_id}")

@app.get("/api/config")
async def get_config():
    """Get configuration settings"""
    return {
        "environment": "local-development",
        "features": {
            "ocr_enabled": True,
            "gpt_extraction_enabled": True,
            "gpt_evaluation_enabled": True,
            "gpt_summary_enabled": True
        },
        "limits": {
            "max_file_size_mb": 50,
            "max_pages": 100
        }
    }

@app.get("/api/configuration")
async def get_configuration():
    """Get configuration settings (alternative endpoint for frontend compatibility)"""
    return await get_config()

@app.post("/api/configuration")
async def update_configuration(config_data: dict):
    """Update configuration settings"""
    # In local development, just return the updated config
    return {
        "message": "Configuration updated successfully (local development mode)",
        "config": config_data
    }

@app.get("/api/datasets")
async def get_datasets():
    """Get list of available datasets"""
    return ["default-dataset", "medical-dataset", "test-dataset"]

@app.get("/api/datasets/{dataset_name}/files")
async def get_dataset_files(dataset_name: str):
    """Get files in a specific dataset"""
    # Mock files for different datasets
    mock_files = {
        "default-dataset": [
            {"filename": "invoice-001.pdf", "size": 12345, "uploaded_at": "2025-06-17T09:00:00Z"},
            {"filename": "receipt-002.pdf", "size": 8765, "uploaded_at": "2025-06-17T08:30:00Z"}
        ],
        "medical-dataset": [
            {"filename": "medical-report-001.pdf", "size": 23456, "uploaded_at": "2025-06-17T07:15:00Z"}
        ],
        "test-dataset": []
    }
    return mock_files.get(dataset_name, [])

@app.get("/api/stats")
async def get_stats():
    """Get processing statistics"""
    total_docs = len(documents_storage)
    completed_docs = sum(1 for doc in documents_storage.values() if doc.state["processing_completed"])
    
    return {
        "total_documents": total_docs,
        "completed_documents": completed_docs,
        "pending_documents": total_docs - completed_docs,
        "success_rate": completed_docs / total_docs if total_docs > 0 else 0.0
    }

if __name__ == "__main__":
    uvicorn.run(
        "main_local:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
