"""
ARGUS MCP Server - Model Context Protocol server for document intelligence
Exposes ARGUS capabilities as MCP tools via SSE transport
"""
import json
import logging
import os
from datetime import datetime
from typing import Any

from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    EmbeddedResource,
    INTERNAL_ERROR,
    INVALID_PARAMS,
)

from dependencies import get_data_container, get_conf_container, get_blob_service_client
from ai_ocr.process import connect_to_cosmos, fetch_model_prompt_and_schema
from ai_ocr.azure.config import get_config
from openai import AzureOpenAI

logger = logging.getLogger(__name__)

# Create the MCP server instance
mcp_server = Server("argus")

# ============================================================================
# Tool Definitions
# ============================================================================

ARGUS_TOOLS = [
    Tool(
        name="argus_list_documents",
        description="""List all documents processed by ARGUS, optionally filtered by dataset.
        
Use this tool to:
- Get an overview of all processed documents
- Find documents by dataset name
- Check processing status of documents""",
        inputSchema={
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": "Optional dataset name to filter documents (e.g., 'default-dataset', 'invoices', 'medical-records')"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of documents to return (default: 50)",
                    "default": 50
                }
            },
            "required": []
        }
    ),
    Tool(
        name="argus_get_document",
        description="""Get detailed information about a specific document including its extracted data.
        
Use this tool to:
- Retrieve OCR text from a document
- Get GPT-extracted structured data
- View evaluation results and summaries
- Check document processing status and errors""",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The unique identifier of the document to retrieve"
                }
            },
            "required": ["document_id"]
        }
    ),
    Tool(
        name="argus_chat_with_document",
        description="""Ask questions about a processed document using AI.
        
Use this tool to:
- Query document content in natural language
- Get specific information from extracted data
- Ask clarifying questions about document details
- Summarize or analyze document content""",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The unique identifier of the document to chat about"
                },
                "message": {
                    "type": "string",
                    "description": "Your question or message about the document"
                },
                "chat_history": {
                    "type": "array",
                    "description": "Optional previous conversation history",
                    "items": {
                        "type": "object",
                        "properties": {
                            "role": {"type": "string", "enum": ["user", "assistant"]},
                            "content": {"type": "string"}
                        }
                    }
                }
            },
            "required": ["document_id", "message"]
        }
    ),
    Tool(
        name="argus_list_datasets",
        description="""List all available datasets configured in ARGUS.
        
Use this tool to:
- Discover available document processing configurations
- See what types of documents ARGUS is set up to process
- Get dataset names for filtering documents""",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": []
        }
    ),
    Tool(
        name="argus_get_dataset_config",
        description="""Get the configuration for a specific dataset including system prompt and output schema.
        
Use this tool to:
- Understand how a dataset processes documents
- View the extraction schema/structure
- See the system prompt used for GPT extraction""",
        inputSchema={
            "type": "object",
            "properties": {
                "dataset_name": {
                    "type": "string",
                    "description": "The name of the dataset to get configuration for"
                }
            },
            "required": ["dataset_name"]
        }
    ),
    Tool(
        name="argus_process_document_url",
        description="""Queue a document for processing from a blob storage URL.
        
Use this tool to:
- Trigger processing of a new document
- Reprocess an existing document from blob storage
        
Note: The document must already be uploaded to Azure Blob Storage.""",
        inputSchema={
            "type": "object",
            "properties": {
                "blob_url": {
                    "type": "string",
                    "description": "The full Azure Blob Storage URL of the document to process"
                },
                "dataset": {
                    "type": "string",
                    "description": "The dataset configuration to use for processing (default: 'default-dataset')",
                    "default": "default-dataset"
                }
            },
            "required": ["blob_url"]
        }
    ),
    Tool(
        name="argus_get_extraction",
        description="""Get just the extracted data from a document (simplified view).
        
Use this tool to:
- Quickly retrieve the GPT extraction output
- Get structured data without full document metadata
- Access the key information extracted from a document""",
        inputSchema={
            "type": "object",
            "properties": {
                "document_id": {
                    "type": "string",
                    "description": "The unique identifier of the document"
                }
            },
            "required": ["document_id"]
        }
    ),
    Tool(
        name="argus_search_documents",
        description="""Search documents by filename or content keywords.
        
Use this tool to:
- Find documents by partial filename match
- Search across document extractions
- Locate specific documents in the system""",
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query to match against filenames and content"
                },
                "dataset": {
                    "type": "string",
                    "description": "Optional dataset to search within"
                }
            },
            "required": ["query"]
        }
    ),
    Tool(
        name="argus_get_upload_url",
        description="""Get a SAS URL for directly uploading a document to ARGUS.
        
Use this tool to:
- Get a pre-signed URL for uploading a document directly to Azure Blob Storage
- The upload will automatically trigger ARGUS processing pipeline
- No base64 encoding needed - upload the file directly using HTTP PUT

After getting the URL, upload your file with: PUT <url> with file content in body
Set Content-Type header appropriately (e.g., 'application/pdf', 'image/png')

The SAS URL is valid for 1 hour.""",
        inputSchema={
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "The filename including extension (e.g., 'invoice.pdf', 'receipt.png')"
                },
                "dataset": {
                    "type": "string",
                    "description": "The dataset to upload to (default: 'default-dataset')",
                    "default": "default-dataset"
                }
            },
            "required": ["filename"]
        }
    ),
]


# ============================================================================
# Tool Handlers
# ============================================================================

@mcp_server.list_tools()
async def list_tools() -> list[Tool]:
    """Return list of available ARGUS tools"""
    return ARGUS_TOOLS


@mcp_server.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent | EmbeddedResource]:
    """Handle tool calls"""
    try:
        if name == "argus_list_documents":
            return await _handle_list_documents(arguments)
        elif name == "argus_get_document":
            return await _handle_get_document(arguments)
        elif name == "argus_chat_with_document":
            return await _handle_chat_with_document(arguments)
        elif name == "argus_list_datasets":
            return await _handle_list_datasets(arguments)
        elif name == "argus_get_dataset_config":
            return await _handle_get_dataset_config(arguments)
        elif name == "argus_process_document_url":
            return await _handle_process_document_url(arguments)
        elif name == "argus_get_extraction":
            return await _handle_get_extraction(arguments)
        elif name == "argus_search_documents":
            return await _handle_search_documents(arguments)
        elif name == "argus_get_upload_url":
            return await _handle_get_upload_url(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [TextContent(type="text", text=f"Error executing {name}: {str(e)}")]


async def _handle_list_documents(arguments: dict) -> list[TextContent]:
    """List documents, optionally filtered by dataset"""
    dataset = arguments.get("dataset")
    limit = arguments.get("limit", 50)
    
    data_container = get_data_container()
    if not data_container:
        return [TextContent(type="text", text="Error: Data container not available. Check Azure connection.")]
    
    try:
        if dataset:
            query = f"SELECT TOP {limit} * FROM c WHERE c.dataset = '{dataset}'"
        else:
            query = f"SELECT TOP {limit} * FROM c"
        
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        # Format documents for output
        documents = []
        for item in items:
            doc = {
                "id": item.get("id"),
                "filename": item.get("file_name") or item.get("filename") or item.get("id", "").split("/")[-1],
                "dataset": item.get("dataset", "default-dataset"),
                "status": _get_document_status(item),
                "created_at": item.get("request_timestamp"),
                "num_pages": item.get("num_pages"),
                "has_extraction": bool(item.get("extracted_data", {}).get("gpt_extraction_output")),
                "has_evaluation": bool(item.get("evaluation_results") or item.get("evaluation")),
            }
            documents.append(doc)
        
        result = {
            "total_count": len(documents),
            "dataset_filter": dataset,
            "documents": documents
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        return [TextContent(type="text", text=f"Error listing documents: {str(e)}")]


async def _handle_get_document(arguments: dict) -> list[TextContent]:
    """Get a specific document by ID"""
    document_id = arguments.get("document_id")
    if not document_id:
        return [TextContent(type="text", text="Error: document_id is required")]
    
    data_container = get_data_container()
    if not data_container:
        return [TextContent(type="text", text="Error: Data container not available")]
    
    try:
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            return [TextContent(type="text", text=f"Document not found: {document_id}")]
        
        item = items[0]
        
        # Format document for output (include key fields)
        doc = {
            "id": item.get("id"),
            "filename": item.get("file_name") or item.get("filename"),
            "dataset": item.get("dataset", "default-dataset"),
            "status": _get_document_status(item),
            "created_at": item.get("request_timestamp"),
            "num_pages": item.get("num_pages"),
            "processing_time": item.get("processing_time") or item.get("processing_times", {}).get("total"),
            "ocr_text": item.get("ocr_response") or item.get("ocr_text"),
            "gpt_extraction": item.get("extracted_data", {}).get("gpt_extraction_output"),
            "evaluation": item.get("evaluation_results") or item.get("evaluation"),
            "summary": item.get("summary"),
            "errors": item.get("errors"),
            "human_corrected": item.get("human_corrected", False),
            "corrections_count": len(item.get("corrections", []))
        }
        
        return [TextContent(type="text", text=json.dumps(doc, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error getting document: {e}")
        return [TextContent(type="text", text=f"Error getting document: {str(e)}")]


async def _handle_chat_with_document(arguments: dict) -> list[TextContent]:
    """Chat with a document using GPT"""
    document_id = arguments.get("document_id")
    message = arguments.get("message", "").strip()
    chat_history = arguments.get("chat_history", [])
    
    if not document_id or not message:
        return [TextContent(type="text", text="Error: document_id and message are required")]
    
    data_container = get_data_container()
    if not data_container:
        return [TextContent(type="text", text="Error: Data container not available")]
    
    try:
        # Fetch the document
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            return [TextContent(type="text", text=f"Document not found: {document_id}")]
        
        document = items[0]
        
        # Get extracted data for context
        extracted_data = document.get('extracted_data', {})
        gpt_extraction = extracted_data.get('gpt_extraction_output')
        ocr_data = extracted_data.get('ocr_output', '')
        
        if not gpt_extraction and not ocr_data:
            return [TextContent(type="text", text="No extracted data available for this document")]
        
        # Prepare context
        context_parts = []
        if gpt_extraction:
            context_parts.append("GPT EXTRACTED DATA:")
            if isinstance(gpt_extraction, dict):
                context_parts.append(json.dumps(gpt_extraction, indent=2))
            else:
                context_parts.append(str(gpt_extraction))
        
        if ocr_data and not gpt_extraction:
            context_parts.append("DOCUMENT TEXT (OCR):")
            ocr_snippet = ocr_data[:3000] + "..." if len(ocr_data) > 3000 else ocr_data
            context_parts.append(ocr_snippet)
        
        document_context = "\n\n".join(context_parts)
        
        # Build conversation context
        conversation_context = ""
        if chat_history:
            conversation_context = "\n\nPREVIOUS CONVERSATION:\n"
            for chat_item in chat_history[-5:]:
                role = chat_item.get('role', 'user')
                content = chat_item.get('content', '')
                conversation_context += f"{role.upper()}: {content}\n"
        
        # Create system prompt
        system_prompt = f"""You are an AI assistant helping users understand and analyze document content.

The user has uploaded a document that has been processed. You have access to the extracted data.

Your role is to:
- Answer questions about the document content accurately
- Help users understand specific details from the document
- Provide insights based on the extracted information
- Be concise but thorough in your responses

DOCUMENT CONTEXT:
{document_context}
{conversation_context}

Answer the user's question based on this document context."""

        # Get config and call OpenAI
        _, cosmos_config_container = connect_to_cosmos()
        config = get_config(cosmos_config_container)
        
        client = AzureOpenAI(
            api_key=config["openai_api_key"],
            api_version=config["openai_api_version"],
            azure_endpoint=config["openai_api_endpoint"]
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        response = client.chat.completions.create(
            model=config["openai_model_deployment"],
            messages=messages
        )
        
        assistant_message = response.choices[0].message.content
        
        result = {
            "response": assistant_message,
            "document_id": document_id,
            "tokens_used": response.usage.total_tokens if response.usage else None
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        return [TextContent(type="text", text=f"Error in chat: {str(e)}")]


async def _handle_list_datasets(arguments: dict) -> list[TextContent]:
    """List available datasets"""
    conf_container = get_conf_container()
    if not conf_container:
        return [TextContent(type="text", text="Error: Configuration container not available")]
    
    try:
        # Try to get configuration
        try:
            config_item = conf_container.read_item(item='configuration', partition_key='configuration')
            datasets = config_item.get('datasets', {})
        except Exception:
            datasets = {}
        
        # Also check for demo datasets
        demo_datasets = ["default-dataset", "medical-dataset", "mistral-dataset"]
        
        result = {
            "configured_datasets": list(datasets.keys()),
            "available_demo_datasets": demo_datasets,
            "dataset_details": {
                name: {
                    "has_system_prompt": bool(cfg.get("system_prompt")),
                    "has_output_schema": bool(cfg.get("output_schema")),
                    "ocr_provider": cfg.get("processing_options", {}).get("ocr_provider", "azure")
                }
                for name, cfg in datasets.items()
            } if datasets else {}
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        return [TextContent(type="text", text=f"Error listing datasets: {str(e)}")]


async def _handle_get_dataset_config(arguments: dict) -> list[TextContent]:
    """Get configuration for a specific dataset"""
    dataset_name = arguments.get("dataset_name")
    if not dataset_name:
        return [TextContent(type="text", text="Error: dataset_name is required")]
    
    try:
        # Use the existing function to fetch dataset config
        prompt, schema, max_pages, options = fetch_model_prompt_and_schema(dataset_name)
        
        result = {
            "dataset_name": dataset_name,
            "system_prompt": prompt[:500] + "..." if len(prompt) > 500 else prompt,
            "system_prompt_length": len(prompt),
            "output_schema": schema,
            "max_pages": max_pages,
            "processing_options": options
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error getting dataset config: {e}")
        return [TextContent(type="text", text=f"Error getting dataset config: {str(e)}")]


async def _handle_process_document_url(arguments: dict) -> list[TextContent]:
    """Queue a document for processing from URL"""
    blob_url = arguments.get("blob_url")
    dataset = arguments.get("dataset", "default-dataset")
    
    if not blob_url:
        return [TextContent(type="text", text="Error: blob_url is required")]
    
    try:
        # Import the processing function
        from blob_processing import process_blob_event
        
        # Create event data
        event_data = {
            "url": blob_url,
            "dataset": dataset
        }
        
        # Queue for processing (this would normally be done via background tasks)
        # For MCP, we'll trigger it directly but note it's async
        import asyncio
        asyncio.create_task(process_blob_event(blob_url, event_data))
        
        result = {
            "status": "queued",
            "message": f"Document queued for processing with dataset '{dataset}'",
            "blob_url": blob_url,
            "dataset": dataset,
            "note": "Processing happens asynchronously. Check document status later."
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error processing document: {e}")
        return [TextContent(type="text", text=f"Error processing document: {str(e)}")]


async def _handle_get_extraction(arguments: dict) -> list[TextContent]:
    """Get just the extraction data from a document"""
    document_id = arguments.get("document_id")
    if not document_id:
        return [TextContent(type="text", text="Error: document_id is required")]
    
    data_container = get_data_container()
    if not data_container:
        return [TextContent(type="text", text="Error: Data container not available")]
    
    try:
        query = f"SELECT c.id, c.file_name, c.extracted_data FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            return [TextContent(type="text", text=f"Document not found: {document_id}")]
        
        item = items[0]
        extraction = item.get("extracted_data", {}).get("gpt_extraction_output")
        
        if not extraction:
            return [TextContent(type="text", text=f"No extraction data available for document: {document_id}")]
        
        result = {
            "document_id": document_id,
            "filename": item.get("file_name"),
            "extraction": extraction
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error getting extraction: {e}")
        return [TextContent(type="text", text=f"Error getting extraction: {str(e)}")]


async def _handle_search_documents(arguments: dict) -> list[TextContent]:
    """Search documents by query"""
    query_text = arguments.get("query", "").lower()
    dataset = arguments.get("dataset")
    
    if not query_text:
        return [TextContent(type="text", text="Error: query is required")]
    
    data_container = get_data_container()
    if not data_container:
        return [TextContent(type="text", text="Error: Data container not available")]
    
    try:
        # Get all documents (or filtered by dataset)
        if dataset:
            cosmos_query = f"SELECT * FROM c WHERE c.dataset = '{dataset}'"
        else:
            cosmos_query = "SELECT * FROM c"
        
        items = list(data_container.query_items(
            query=cosmos_query,
            enable_cross_partition_query=True
        ))
        
        # Search in memory (Cosmos DB doesn't have great full-text search)
        matches = []
        for item in items:
            filename = (item.get("file_name") or item.get("filename") or "").lower()
            extraction = str(item.get("extracted_data", {}).get("gpt_extraction_output", "")).lower()
            ocr_text = (item.get("ocr_response") or item.get("ocr_text") or "").lower()
            
            if query_text in filename or query_text in extraction or query_text in ocr_text:
                matches.append({
                    "id": item.get("id"),
                    "filename": item.get("file_name") or item.get("filename"),
                    "dataset": item.get("dataset"),
                    "status": _get_document_status(item),
                    "match_in": [
                        loc for loc, text in [
                            ("filename", filename),
                            ("extraction", extraction),
                            ("ocr_text", ocr_text)
                        ] if query_text in text
                    ]
                })
        
        result = {
            "query": query_text,
            "dataset_filter": dataset,
            "total_matches": len(matches),
            "matches": matches[:20]  # Limit to 20 results
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error searching documents: {e}")
        return [TextContent(type="text", text=f"Error searching documents: {str(e)}")]


def _get_document_status(item: dict) -> str:
    """Determine document status from state"""
    state = item.get("state", {})
    if state.get("error") or item.get("errors"):
        return "failed"
    if state.get("finished") or state.get("gpt_summary") or state.get("gpt_evaluation"):
        return "completed"
    if state.get("file_landed") or state.get("ocr_completed") or state.get("gpt_extraction"):
        return "processing"
    return "pending"


async def _handle_get_upload_url(arguments: dict) -> list[TextContent]:
    """Generate a SAS URL for direct blob upload"""
    from azure.storage.blob import generate_blob_sas, BlobSasPermissions
    
    filename = arguments.get("filename")
    dataset = arguments.get("dataset", "default-dataset")
    
    if not filename:
        return [TextContent(type="text", text="Error: filename is required")]
    
    blob_service_client = get_blob_service_client()
    if not blob_service_client:
        return [TextContent(type="text", text="Error: Blob storage not available")]
    
    try:
        container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
        blob_path = f"{dataset}/{filename}"
        
        # Get account info
        account_name = blob_service_client.account_name
        
        # Get container client and blob client
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        # Generate SAS token with write permission (valid for 1 hour)
        from datetime import timedelta
        
        # Use user delegation key for SAS (more secure with managed identity)
        user_delegation_key = blob_service_client.get_user_delegation_key(
            key_start_time=datetime.utcnow(),
            key_expiry_time=datetime.utcnow() + timedelta(hours=1)
        )
        
        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_path,
            user_delegation_key=user_delegation_key,
            permission=BlobSasPermissions(write=True, create=True),
            expiry=datetime.utcnow() + timedelta(hours=1)
        )
        
        # Construct the full URL with SAS token
        upload_url = f"{blob_client.url}?{sas_token}"
        
        # Determine content type hint
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        content_type_hints = {
            'pdf': 'application/pdf',
            'png': 'image/png',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'tiff': 'image/tiff',
            'tif': 'image/tiff',
            'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        }
        content_type = content_type_hints.get(ext, 'application/octet-stream')
        
        result = {
            "upload_url": upload_url,
            "method": "PUT",
            "headers": {
                "x-ms-blob-type": "BlockBlob",
                "Content-Type": content_type
            },
            "filename": filename,
            "dataset": dataset,
            "blob_path": blob_path,
            "expires_in": "1 hour",
            "instructions": [
                f"Upload your file using HTTP PUT to the upload_url",
                f"Set header 'x-ms-blob-type: BlockBlob'",
                f"Set header 'Content-Type: {content_type}'",
                "The file body should be the raw file content (not base64)",
                "After upload, ARGUS will automatically process the document"
            ],
            "curl_example": f"curl -X PUT -H 'x-ms-blob-type: BlockBlob' -H 'Content-Type: {content_type}' --data-binary @{filename} '<upload_url>'"
        }
        
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
        
    except Exception as e:
        logger.error(f"Error generating upload URL: {e}")
        return [TextContent(type="text", text=f"Error generating upload URL: {str(e)}")]
