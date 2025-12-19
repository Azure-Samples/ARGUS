"""
ARGUS Container App - Main FastAPI Application
Reorganized modular structure for better maintainability
"""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from starlette.types import Receive, Scope, Send

from dependencies import initialize_azure_clients, cleanup_azure_clients
import api_routes
from mcp_server import mcp_server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_TIMEOUT = 45*60  # Set timeout duration in seconds

# Create the StreamableHTTP session manager (created here so it's available for lifespan)
mcp_session_manager: StreamableHTTPSessionManager | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):  # noqa: ARG001
    """Initialize Azure clients and MCP session manager on startup"""
    global mcp_session_manager  # noqa: PLW0603
    
    try:
        await initialize_azure_clients()
        logger.info("Successfully initialized Azure clients")
    except Exception as e:
        logger.error("Failed to initialize Azure clients: %s", e)
        raise
    
    # Initialize MCP session manager
    mcp_session_manager = StreamableHTTPSessionManager(
        app=mcp_server,
        event_store=None,  # No resumability - stateless mode
        json_response=True,  # Use JSON responses for better compatibility
        stateless=True,  # Stateless mode for scalability
    )
    
    # Run MCP session manager
    async with mcp_session_manager.run():
        logger.info("MCP Streamable HTTP session manager started")
        yield
    
    # Cleanup
    await cleanup_azure_clients()
    logger.info("Application shutdown complete")


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

# Default allowed origins for local development
default_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Add any dynamically configured origins
all_origins = list(set(default_origins + cors_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=False,  # Must be False when using allow_origins=["*"]
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["Mcp-Session-Id"],  # Required for MCP Streamable HTTP transport
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


# MCP-powered chat endpoint with tool calling
@app.post("/api/mcp-chat")
async def mcp_chat(request: Request):
    return await api_routes.mcp_chat(request)


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


@app.post("/api/datasets")
async def create_dataset(request: Request):
    """Create a new dataset configuration"""
    return await api_routes.create_dataset_endpoint(request)


@app.get("/api/datasets/{dataset_name}/documents")
async def get_dataset_documents(dataset_name: str):
    return await api_routes.get_dataset_documents(dataset_name)


@app.post("/api/datasets/{dataset_name}/upload")
async def upload_file(dataset_name: str, request: Request, background_tasks: BackgroundTasks):
    return await api_routes.upload_file(dataset_name, request, background_tasks)


@app.get("/api/upload-url")
async def get_upload_url(filename: str, dataset: str = "default-dataset"):
    """Get a pre-signed SAS URL for direct blob upload"""
    return await api_routes.get_upload_url(filename, dataset)


# ============================================================================
# MCP (Model Context Protocol) Endpoints - Streamable HTTP Transport
# ============================================================================

@app.get("/mcp/info")
async def mcp_info(request: Request):
    """
    Get information about the ARGUS MCP server.
    
    Returns available tools and connection instructions.
    """
    # Dynamically construct the MCP URL from the current request
    base_url = str(request.base_url).rstrip('/')
    mcp_url = f"{base_url}/mcp"
    
    return {
        "name": "argus",
        "description": "ARGUS Document Intelligence MCP Server",
        "version": "1.0.0",
        "transport": "streamable-http",
        "endpoints": {
            "mcp": "/mcp"
        },
        "tools": [
            {
                "name": "argus_list_documents",
                "description": "List all processed documents"
            },
            {
                "name": "argus_get_document", 
                "description": "Get detailed document information"
            },
            {
                "name": "argus_chat_with_document",
                "description": "Ask questions about a document"
            },
            {
                "name": "argus_list_datasets",
                "description": "List available dataset configurations"
            },
            {
                "name": "argus_get_dataset_config",
                "description": "Get dataset configuration details"
            },
            {
                "name": "argus_process_document_url",
                "description": "Queue document for processing"
            },
            {
                "name": "argus_get_extraction",
                "description": "Get extracted data from document"
            },
            {
                "name": "argus_search_documents",
                "description": "Search documents by keyword"
            },
            {
                "name": "argus_get_upload_url",
                "description": "Get a pre-signed SAS URL for direct blob upload"
            },
            {
                "name": "argus_create_dataset",
                "description": "Create a new dataset configuration"
            }
        ],
        "configuration_example": {
            "mcpServers": {
                "argus": {
                    "url": mcp_url
                }
            }
        }
    }


async def handle_mcp_request(scope: Scope, receive: Receive, send: Send) -> None:
    """ASGI handler for MCP Streamable HTTP requests."""
    if mcp_session_manager is None:
        raise RuntimeError("MCP session manager not initialized")
    await mcp_session_manager.handle_request(scope, receive, send)


# Mount MCP at /mcp endpoint (supports GET, POST, DELETE)
# Note: /mcp/info is defined above as a FastAPI route, which takes precedence
app.mount("/mcp", handle_mcp_request)


# Optional: If you want to run this directly
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

