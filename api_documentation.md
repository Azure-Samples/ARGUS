# 🚀 ARGUS API Documentation

## Overview

ARGUS (Automated Retrieval and GPT Understanding System) is a document intelligence platform that provides APIs for document processing, AI-powered extraction, and chat-based document interaction. The system is built with FastAPI and integrates with Azure services for scalable document processing.

## Base URLs

- **Production**: Container App endpoint (configured via Azure deployment)
- **Local Development**: `http://localhost:8000`
- **Frontend**: Streamlit app on `http://localhost:8501`

## Authentication

- **Azure Services**: Uses Azure Default Credentials
- **API Keys**: OpenAI API key configured via environment variables
- **CORS**: Enabled for frontend integration

---

## 📍 Health & Status Endpoints

### GET `/`
**Root Health Check**

Simple health check endpoint to verify service availability.

**Response:**
```json
{
  "status": "healthy",
  "service": "ARGUS Backend"
}
```

### GET `/health`
**Detailed Health Check**

Comprehensive health check including Azure service connectivity.

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-07-17T10:30:00.123456Z",
  "services": {
    "storage": "connected",
    "cosmos_db": "connected"
  }
}
```

**Error Response (503):**
```json
{
  "detail": "Service unhealthy"
}
```

---

## 📄 Document Processing Endpoints

### POST `/api/blob-created`
**Handle Event Grid Blob Events**

Processes Azure Event Grid blob created events for automatic document processing.

**Request Body:**
```json
{
  "eventType": "Microsoft.Storage.BlobCreated",
  "subject": "/blobServices/default/containers/documents/blobs/sample.pdf",
  "data": {
    "url": "https://storage.blob.core.windows.net/documents/sample.pdf"
  }
}
```

**Response:**
```json
{
  "message": "Blob processing queued successfully",
  "blob_url": "https://storage.blob.core.windows.net/documents/sample.pdf"
}
```

### POST `/api/process-blob`
**Manual Blob Processing**

Manually trigger processing of a blob in Azure Storage.

**Request Body:**
```json
{
  "blob_url": "https://storage.blob.core.windows.net/documents/sample.pdf",
  "dataset": "default-dataset"
}
```

**Response:**
```json
{
  "message": "Blob processing queued successfully",
  "blob_url": "https://storage.blob.core.windows.net/documents/sample.pdf"
}
```

### POST `/api/process-file`
**Process File (Logic App Integration)**

Endpoint called by Azure Logic Apps to process uploaded files.

**Request Body:**
```json
{
  "filename": "invoice.pdf",
  "dataset": "invoices",
  "blob_path": "invoices/invoice.pdf",
  "trigger_source": "logic_app"
}
```

**Response:**
```json
{
  "message": "File invoice.pdf queued for processing",
  "filename": "invoice.pdf",
  "dataset": "invoices",
  "blob_url": "https://storage.blob.core.windows.net/invoices/invoice.pdf"
}
```

---

## ⚙️ Configuration Management

### GET `/api/configuration`
**Get Configuration**

Retrieve current system configuration from Cosmos DB including datasets, prompts and schemas.

**Response:**
```json
{
  "id": "configuration",
  "partitionKey": "configuration",
  "datasets": {
    "default-dataset": {
      "system_prompt": "Extract key information from the document...",
      "output_schema": {
        "type": "object",
        "properties": {
          "invoice_number": {"type": "string"},
          "total_amount": {"type": "number"}
        }
      }
    },
    "medical-dataset": {
      "system_prompt": "Extract medical information...",
      "output_schema": {...}
    }
  }
}
```

**Default Response (when no config exists):**
```json
{
  "id": "configuration",
  "partitionKey": "configuration",
  "datasets": {}
}
```

### POST `/api/configuration`
**Update Configuration**

Update system configuration in Cosmos DB with new prompts, schemas, or settings.

**Request Body:**
```json
{
  "id": "configuration",
  "partitionKey": "configuration",
  "datasets": {
    "default-dataset": {
      "system_prompt": "Updated extraction prompt...",
      "output_schema": {
        "type": "object",
        "properties": {
          "document_type": {"type": "string"},
          "key_data": {"type": "object"}
        }
      }
    }
  }
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Configuration updated"
}
```

### POST `/api/configuration/refresh`
**Refresh Configuration**

Force refresh configuration by reloading demo datasets from filesystem.

**Response:**
```json
{
  "status": "success",
  "message": "Configuration refreshed from demo files"
}
```

---

## 🔄 Logic App Concurrency Management

### GET `/api/concurrency`
**Get Concurrency Settings**

Retrieve current Logic App concurrency configuration.

**Response:**
```json
{
  "enabled": true,
  "trigger_concurrency": 5,
  "workflow_name": "document-processing-workflow",
  "subscription_id": "12345678-1234-1234-1234-123456789012",
  "resource_group": "argus-rg",
  "logic_app_name": "argus-logic-app"
}
```

**Error Response (503 - Logic App Manager not initialized):**
```json
{
  "detail": "Logic App Manager not initialized"
}
```

### PUT `/api/concurrency`
**Update Concurrency Settings**

Update Logic App concurrency settings for optimal performance.

**Request Body:**
```json
{
  "max_runs": 10
}
```

**Response:**
```json
{
  "success": true,
  "message": "Concurrency updated successfully",
  "new_max_runs": 10,
  "backend_semaphore_updated": true,
  "backend_max_concurrent": 10
}
```

### GET `/api/workflow-definition`
**Get Workflow Definition**

Retrieve the current Logic App workflow definition.

**Response:**
```json
{
  "definition": {
    "triggers": {
      "When_a_blob_is_added_or_modified": {
        "type": "ApiConnection",
        "inputs": {...}
      }
    },
    "actions": {
      "Process_Document": {
        "type": "Http",
        "inputs": {...}
      }
    }
  },
  "parameters": {...}
}
```

### PUT `/api/concurrency-full`
**Update Full Concurrency Settings**

Update both trigger and action concurrency settings.

**Request Body:**
```json
{
  "max_runs": 15
}
```

**Response:**
```json
{
  "success": true,
  "message": "Full concurrency settings updated successfully",
  "trigger_concurrency_updated": true,
  "action_concurrency_updated": true
}
```

### GET `/api/concurrency/diagnostics`
**Concurrency Diagnostics**

Get diagnostic information about Logic App Manager setup.

**Response:**
```json
{
  "timestamp": "2025-07-17T10:30:00.123456Z",
  "logic_app_manager_initialized": true,
  "logic_app_manager_enabled": true,
  "subscription_id_configured": true,
  "resource_group_configured": true,
  "logic_app_name_configured": true,
  "environment_variables": {
    "AZURE_SUBSCRIPTION_ID": true,
    "AZURE_RESOURCE_GROUP_NAME": true,
    "LOGIC_APP_NAME": true
  },
  "environment_values": {
    "AZURE_SUBSCRIPTION_ID": "12345678...",
    "AZURE_RESOURCE_GROUP_NAME": "argus-rg",
    "LOGIC_APP_NAME": "argus-logic-app"
  },
  "azure_credentials_available": true
}
```

---

## 🤖 OpenAI Configuration

### GET `/api/openai-settings`
**Get OpenAI Settings**

Retrieve current OpenAI configuration from environment variables (read-only).

**Response:**
```json
{
  "openai_endpoint": "https://myopenai.openai.azure.com/",
  "openai_key": "***HIDDEN***",
  "deployment_name": "gpt-4",
  "note": "Configuration is read from environment variables only. Update via deployment/infrastructure."
}
```

### PUT `/api/openai-settings`
**Update OpenAI Settings**

Update OpenAI configuration by modifying environment variables.

**Request Body:**
```json
{
  "openai_endpoint": "https://myopenai.openai.azure.com/",
  "openai_key": "your-api-key",
  "deployment_name": "gpt-4"
}
```

**Response:**
```json
{
  "message": "Environment variables updated successfully",
  "config": {
    "openai_endpoint": "https://myopenai.openai.azure.com/",
    "deployment_name": "gpt-4"
  }
}
```

---

## 💬 Chat & Document Interaction

### POST `/api/chat`
**Chat with Document**

Interactive chat endpoint for asking questions about processed documents.

**Request Body:**
```json
{
  "document_id": "sample-invoice-123",
  "message": "What is the total amount on this invoice?",
  "chat_history": [
    {
      "role": "user",
      "content": "Previous question..."
    },
    {
      "role": "assistant",
      "content": "Previous response..."
    }
  ]
}
```

**Response:**
```json
{
  "response": "The total amount on this invoice is $1,250.00.",
  "finish_reason": "stop",
  "usage": {
    "prompt_tokens": 456,
    "completion_tokens": 23,
    "total_tokens": 479
  }
}
```

**Error Responses:**
- `400`: Missing required parameters or no extracted data available
- `404`: Document not found
- `500`: Chat processing failed

---

## 📋 Document Management (Local Development Only)

*Note: These endpoints are only available in local development mode (`main_local.py`) for testing without Azure dependencies.*

### GET `/api/documents`
**List Documents (Local Development Only)**

Get all documents in local memory storage.

**Response:**
```json
{
  "documents": [
    {
      "id": "sample-invoice-123",
      "properties": {
        "blob_name": "sample-invoice.pdf",
        "blob_size": 12345,
        "request_timestamp": "2025-07-17T10:00:00.123456",
        "num_pages": 2,
        "dataset": "default-dataset"
      },
      "state": {
        "file_landed": true,
        "ocr_completed": true,
        "gpt_extraction_completed": true,
        "gpt_evaluation_completed": false,
        "gpt_summary_completed": false,
        "processing_completed": false
      },
      "extracted_data": {
        "ocr_output": "Sample OCR text...",
        "gpt_output": {"invoice_number": "INV-001", "total": 1250.00},
        "gpt_evaluation": {},
        "gpt_summary": ""
      }
    }
  ],
  "count": 1
}
```

### GET `/api/documents/{doc_id}`
**Get Document (Local Development Only)**

Retrieve a specific document by ID.

**Response:**
```json
{
  "id": "sample-invoice-123",
  "properties": {
    "blob_name": "sample-invoice.pdf",
    "blob_size": 12345,
    "request_timestamp": "2025-07-17T10:00:00.123456",
    "num_pages": 2,
    "dataset": "default-dataset"
  },
  "state": {
    "file_landed": true,
    "ocr_completed": true,
    "gpt_extraction_completed": true,
    "gpt_evaluation_completed": false,
    "gpt_summary_completed": false,
    "processing_completed": false
  },
  "extracted_data": {
    "ocr_output": "Sample OCR text...",
    "gpt_output": {"invoice_number": "INV-001", "total": 1250.00},
    "gpt_evaluation": {},
    "gpt_summary": ""
  }
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found"
}
```

### POST `/api/documents/{doc_id}`
**Update Document (Local Development Only)**

Update a document in local storage.

**Request Body:**
```json
{
  "id": "sample-invoice-123",
  "properties": {
    "blob_name": "updated-invoice.pdf",
    "blob_size": 15000,
    "request_timestamp": "2025-07-17T11:00:00.123456",
    "num_pages": 3,
    "dataset": "invoices"
  },
  "state": {
    "file_landed": true,
    "ocr_completed": true,
    "gpt_extraction_completed": true,
    "gpt_evaluation_completed": true,
    "gpt_summary_completed": true,
    "processing_completed": true
  },
  "extracted_data": {
    "ocr_output": "Updated OCR text...",
    "gpt_output": {"invoice_number": "INV-002", "total": 1500.00},
    "gpt_evaluation": {"quality_score": 0.95},
    "gpt_summary": "This is an invoice for services..."
  }
}
```

**Response:**
```json
{
  "message": "Document updated successfully",
  "id": "sample-invoice-123"
}
```

### DELETE `/api/documents/{doc_id}`
**Delete Document (Local Development Only)**

Remove a document from local storage.

**Response:**
```json
{
  "message": "Document deleted successfully",
  "id": "sample-invoice-123"
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found"
}
```

---

## 📤 File Upload & Dataset APIs (Local Development Only)

*Note: These endpoints are only available in local development mode (`main_local.py`) and are NOT implemented in the production backend.*

### POST `/api/upload`
**Upload File (Local Development Only)**

Upload files for processing in local development environment.

**Request:** Multipart form data
- `file`: File content (UploadFile)
- `dataset_name`: Target dataset name (default: "default-dataset")

**Response:**
```json
{
  "message": "File uploaded successfully",
  "id": "uploaded-20250717-103000-invoice.pdf",
  "filename": "invoice.pdf",
  "dataset": "default-dataset",
  "status": "uploaded"
}
```

### GET `/api/datasets`
**List Datasets (Local Development Only)**

Get available datasets in local development.

**Response:**
```json
["default-dataset", "medical-dataset", "test-dataset"]
```

### GET `/api/datasets/{dataset_name}/files`
**Get Dataset Files (Local Development Only)**

List files in a specific dataset (mock data in local development).

**Response:**
```json
[
  {
    "filename": "invoice-001.pdf",
    "size": 12345,
    "uploaded_at": "2025-06-17T09:00:00Z"
  },
  {
    "filename": "receipt-002.pdf",
    "size": 8765,
    "uploaded_at": "2025-06-17T08:30:00Z"
  }
]
```

### POST `/api/process/{doc_id}`
**Process Document (Local Development Only)**

Start processing an uploaded document in local development.

**Response:**
```json
{
  "message": "Document processing started",
  "id": "uploaded-20250717-103000-invoice.pdf",
  "status": "processing"
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found"
}
```

### GET `/api/stats`
**Get Statistics (Local Development Only)**

Get processing statistics for local development.

**Response:**
```json
{
  "total_documents": 5,
  "completed_documents": 3,
  "pending_documents": 2,
  "success_rate": 0.6
}
```

### DELETE `/api/documents/{document_id}`
**Delete Document (Local Development Only)**

Remove a document from local storage.

**Response:**
```json
{
  "message": "Document deleted successfully",
  "id": "sample-invoice-123"
}
```

**Error Response (404):**
```json
{
  "detail": "Document not found"
}
```

## 🚨 Production Document Access

**Important**: The production backend does NOT have document management endpoints like `/api/documents`. Document data in production is stored in Azure Cosmos DB and accessed through the chat endpoint or through direct Cosmos DB queries.

For production document access:
1. **Chat Interface**: Use `/api/chat` to interact with processed documents
2. **Direct Database Access**: Query Cosmos DB directly for document retrieval
3. **Frontend Integration**: The Streamlit frontend handles document listing and management

## ⚠️ Missing Frontend Integration Endpoints

The frontend expects these endpoints that are **NOT implemented** in the current backend:

- `POST /api/upload` - ❌ Only available in local development
- `GET /api/datasets` - ❌ Only available in local development  
- `GET /api/datasets/{dataset_name}/files` - ❌ Only available in local development
- `DELETE /api/documents/{document_id}` - ❌ Only available in local development
- `POST /api/documents/{document_id}/reprocess` - ❌ Not implemented anywhere

## 🚨 Production File Upload

**Important**: The production backend does NOT have a direct file upload endpoint. Instead, files are processed through:

1. **Azure Blob Storage**: Files uploaded to Azure Storage trigger Event Grid events
2. **Event Grid Integration**: `/api/blob-created` processes these events
3. **Logic Apps**: `/api/process-file` handles Logic App-triggered processing
4. **Manual Processing**: `/api/process-blob` for manual blob processing

For production file uploads, you need to:
1. Upload files directly to Azure Blob Storage using Azure SDKs or Storage Explorer
2. Configure Azure Logic Apps for automated processing triggers
3. Use Event Grid to automatically trigger processing when files are uploaded
4. Or manually trigger processing via `/api/process-blob` with the blob URL

---

## 🔧 Data Models

### Document Model (Local Development)
```json
{
  "id": "string",
  "properties": {
    "blob_name": "string",
    "blob_size": "number",
    "request_timestamp": "string (ISO datetime)",
    "num_pages": "number",
    "dataset": "string"
  },
  "state": {
    "file_landed": "boolean",
    "ocr_completed": "boolean",
    "gpt_extraction_completed": "boolean",
    "gpt_evaluation_completed": "boolean",
    "gpt_summary_completed": "boolean",
    "processing_completed": "boolean"
  },
  "extracted_data": {
    "ocr_output": "string",
    "gpt_output": "object",
    "gpt_evaluation": "object",
    "gpt_summary": "string"
  }
}
```

### Configuration Model
```json
{
  "id": "configuration",
  "partitionKey": "configuration",
  "datasets": {
    "dataset-name": {
      "system_prompt": "string",
      "output_schema": "object",
      "max_pages": "number",
      "options": "object"
    }
  }
}
```

### Event Grid Event Model
```json
{
  "eventType": "Microsoft.Storage.BlobCreated",
  "subject": "string",
  "data": {
    "url": "string",
    "api": "string",
    "requestId": "string",
    "eTag": "string",
    "contentType": "string",
    "contentLength": "number",
    "blobType": "string"
  },
  "eventTime": "string (ISO datetime)",
  "id": "string",
  "dataVersion": "string",
  "metadataVersion": "string"
}
```

### Chat Request Model
```json
{
  "document_id": "string",
  "message": "string",
  "chat_history": [
    {
      "role": "user | assistant",
      "content": "string"
    }
  ]
}
```

### Chat Response Model
```json
{
  "response": "string",
  "finish_reason": "stop | length | content_filter",
  "usage": {
    "prompt_tokens": "number",
    "completion_tokens": "number", 
    "total_tokens": "number"
  }
}
```

---

## 🚨 Error Handling

### Common HTTP Status Codes

- **200**: Success
- **400**: Bad Request - Invalid parameters or missing required fields
- **404**: Not Found - Document or resource not found
- **500**: Internal Server Error - Processing failed or Azure service unavailable
- **503**: Service Unavailable - Health check failed or dependencies unavailable

### Error Response Format
```json
{
  "detail": "Error message describing what went wrong"
}
```

### Common Error Scenarios

**Configuration Issues:**
- `503`: "Configuration container not available" - Cosmos DB connection issue
- `503`: "Logic App Manager not initialized" - Azure credentials or environment variables missing

**Document Processing:**
- `400`: "Missing required parameters: filename, dataset, blob_path" - Invalid request body
- `404`: "Document not found" - Document ID doesn't exist in storage
- `500`: "Internal server error" - Azure service communication failure

**Chat Endpoint:**
- `400`: "document_id and message are required" - Missing required fields
- `400`: "No extracted data available for this document" - Document hasn't been processed
- `404`: "Document not found" - Invalid document ID

---

## 🔍 Usage Examples

### Local Development Setup
```bash
# Run local development server
cd src/containerapp
python main_local.py

# Health check
curl -X GET "http://localhost:8000/health"

# Upload a file (local development only)
curl -X POST "http://localhost:8000/api/upload" \
  -F "file=@invoice.pdf" \
  -F "dataset_name=invoices"

# List documents
curl -X GET "http://localhost:8000/api/documents"

# Get processing statistics
curl -X GET "http://localhost:8000/api/stats"
```

### Production Document Processing
```bash
# 1. Manual blob processing (most common)
curl -X POST "http://your-container-app.azurecontainerapps.io/api/process-blob" \
  -H "Content-Type: application/json" \
  -d '{
    "blob_url": "https://storage.blob.core.windows.net/docs/invoice.pdf",
    "dataset": "invoices"
  }'

# 2. Logic App integration (automated)
curl -X POST "http://your-container-app.azurecontainerapps.io/api/process-file" \
  -H "Content-Type: application/json" \
  -d '{
    "filename": "invoice.pdf",
    "dataset": "invoices", 
    "blob_path": "invoices/invoice.pdf",
    "trigger_source": "logic_app"
  }'

# 3. Chat with processed document
curl -X POST "http://your-container-app.azurecontainerapps.io/api/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "invoice-123",
    "message": "What is the total amount on this invoice?"
  }'
```

### Configuration Management
```bash
# Get current configuration
curl -X GET "http://your-container-app.azurecontainerapps.io/api/configuration"

# Update configuration with new dataset
curl -X POST "http://your-container-app.azurecontainerapps.io/api/configuration" \
  -H "Content-Type: application/json" \
  -d '{
    "id": "configuration",
    "partitionKey": "configuration",
    "datasets": {
      "custom-dataset": {
        "system_prompt": "Extract all key financial data from the document...",
        "output_schema": {
          "type": "object",
          "properties": {
            "amount": {"type": "number"},
            "date": {"type": "string"},
            "vendor": {"type": "string"}
          }
        }
      }
    }
  }'

# Refresh configuration from files
curl -X POST "http://your-container-app.azurecontainerapps.io/api/configuration/refresh"
```

### Logic App Concurrency Management
```bash
# Check current concurrency settings
curl -X GET "http://your-container-app.azurecontainerapps.io/api/concurrency"

# Update concurrency limit
curl -X PUT "http://your-container-app.azurecontainerapps.io/api/concurrency" \
  -H "Content-Type: application/json" \
  -d '{"max_runs": 10}'

# Get detailed diagnostics
curl -X GET "http://your-container-app.azurecontainerapps.io/api/concurrency/diagnostics"
```

### OpenAI Configuration
```bash
# Get current OpenAI settings
curl -X GET "http://your-container-app.azurecontainerapps.io/api/openai-settings"

# Update OpenAI endpoint and model
curl -X PUT "http://your-container-app.azurecontainerapps.io/api/openai-settings" \
  -H "Content-Type: application/json" \
  -d '{
    "openai_endpoint": "https://my-openai.openai.azure.com/",
    "openai_key": "your-api-key",
    "deployment_name": "gpt-4"
  }'
```

---

## 🏗️ Architecture Notes

### Production Architecture
- **FastAPI Backend**: Container App running the main API
- **Azure Cosmos DB**: Document storage and configuration
- **Azure Blob Storage**: File storage with Event Grid integration
- **Azure Logic Apps**: Automated workflow triggers
- **Azure OpenAI**: AI processing for extraction and chat

### Local Development Architecture  
- **FastAPI Backend**: Local server with in-memory storage
- **Mock Services**: Simulated Azure services for testing
- **File Upload**: Direct file upload for testing without Azure dependencies

### Processing Pipeline
1. **File Upload**: To Azure Blob Storage (production) or local endpoint (development)
2. **Event Trigger**: Event Grid notification or manual API call
3. **OCR Processing**: Azure Document Intelligence extracts text
4. **AI Extraction**: Azure OpenAI processes text with custom prompts
5. **Storage**: Results stored in Cosmos DB (production) or memory (local)
6. **Chat Interface**: Interactive Q&A about processed documents

---

## 📚 Additional Resources

- **Project Repository**: [Azure-Samples/ARGUS](https://github.com/Azure-Samples/ARGUS)
- **Architecture Overview**: See `docs/ArchitectureOverview.png`
- **Setup Instructions**: See `README.md`
- **Frontend Documentation**: See `frontend/` directory
- **Infrastructure**: See `infra/` directory for Bicep templates

---

*Last Updated: July 17, 2025*
*Version: 1.0.0*
