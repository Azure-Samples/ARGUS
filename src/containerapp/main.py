"""
ARGUS Container App - Main FastAPI Application
Reorganized modular structure for better maintainability
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from dependencies import initialize_azure_clients, cleanup_azure_clients
import api_routes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_TIMEOUT = 45*60  # Set timeout duration in seconds


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Azure clients on startup"""
    try:
        await initialize_azure_clients()
        logger.info("Successfully initialized Azure clients")
    except Exception as e:
        logger.error(f"Failed to initialize Azure clients: {e}")
        raise
    
    yield
    
    # Cleanup
    await cleanup_azure_clients()


# Initialize FastAPI app
app = FastAPI(
    title="ARGUS Backend",
    description="Document processing backend using Azure AI services",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - Allow frontend origins
# Get allowed origins from environment or use defaults
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]

# Default allowed origins for production
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://ca-frontend-js23nrf4s4ha2.nicesand-0a67ac7b.eastus2.azurecontainerapps.io",
]

# Add any dynamically configured origins
all_origins = list(set(default_origins + cors_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)


# Health check endpoints
@app.get("/")
async def root():
    return await api_routes.root()


@app.get("/health")
async def health_check():
    return await api_routes.health_check()


# Blob processing endpoints
@app.post("/api/blob-created")
async def handle_blob_created(request: Request, background_tasks: BackgroundTasks):
    return await api_routes.handle_blob_created(request, background_tasks)


@app.post("/api/process-blob")
async def process_blob_manual(request: Request, background_tasks: BackgroundTasks):
    return await api_routes.process_blob_manual(request, background_tasks)


@app.post("/api/process-file")
async def process_file(request: Request, background_tasks: BackgroundTasks):
    return await api_routes.process_file(request, background_tasks)


# Configuration management endpoints
@app.get("/api/configuration")
async def get_configuration():
    return await api_routes.get_configuration()


@app.post("/api/configuration")
async def update_configuration(request: Request):
    return await api_routes.update_configuration(request)


@app.post("/api/configuration/refresh")
async def refresh_configuration():
    return await api_routes.refresh_configuration()


# Logic App concurrency management endpoints
@app.get("/api/concurrency")
async def get_concurrency_settings():
    return await api_routes.get_concurrency_settings()


@app.put("/api/concurrency")
async def update_concurrency_settings(request: Request):
    return await api_routes.update_concurrency_settings(request)


@app.get("/api/workflow-definition")
async def get_workflow_definition():
    return await api_routes.get_workflow_definition()


@app.put("/api/concurrency-full")
async def update_full_concurrency_settings(request: Request):
    return await api_routes.update_full_concurrency_settings(request)


@app.get("/api/concurrency/diagnostics")
async def get_concurrency_diagnostics():
    return await api_routes.get_concurrency_diagnostics()


# OpenAI configuration management endpoints
@app.get("/api/openai-settings")
async def get_openai_settings():
    return await api_routes.get_openai_settings()


@app.put("/api/openai-settings")
async def update_openai_settings(request: Request):
    return await api_routes.update_openai_settings(request)


# Chat endpoint
@app.post("/api/chat")
async def chat_with_document(request: Request):
    return await api_routes.chat_with_document(request)


# Human-in-the-loop correction endpoints
@app.patch("/api/documents/{document_id}/corrections")
async def submit_correction(document_id: str, request: Request):
    return await api_routes.submit_correction(document_id, request)


@app.get("/api/documents/{document_id}/corrections")
async def get_correction_history(document_id: str):
    return await api_routes.get_correction_history(document_id)


@app.get("/api/documents/{document_id}/file")
async def get_document_file(document_id: str):
    return await api_routes.get_document_file(document_id)


# Document management endpoints
@app.get("/api/documents")
async def list_documents(dataset: str = None):
    return await api_routes.list_documents(dataset)


@app.get("/api/documents/{document_id}")
async def get_document(document_id: str):
    return await api_routes.get_document(document_id)


@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    return await api_routes.delete_document(document_id)


@app.post("/api/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str, background_tasks: BackgroundTasks):
    return await api_routes.reprocess_document(document_id, background_tasks)


# Dataset management endpoints
@app.get("/api/datasets")
async def list_datasets():
    return await api_routes.list_datasets()


@app.get("/api/datasets/{dataset_name}/documents")
async def get_dataset_documents(dataset_name: str):
    return await api_routes.get_dataset_documents(dataset_name)


@app.post("/api/datasets/{dataset_name}/upload")
async def upload_file(dataset_name: str, request: Request, background_tasks: BackgroundTasks):
    return await api_routes.upload_file(dataset_name, request, background_tasks)


# Optional: If you want to run this directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

