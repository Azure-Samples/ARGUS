"""
Container App version of the ARGUS backend
Handles HTTP requests from Event Grid instead of blob triggers
"""
import logging
import os
import json
import traceback
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Any
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.identity import DefaultAzureCredential
import uvicorn

# Import your existing processing functions
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functionapp'))

from ai_ocr.process import (
    run_ocr_processing, run_gpt_extraction, run_gpt_evaluation, run_gpt_summary,
    prepare_images, initialize_document, update_state, connect_to_cosmos, 
    write_blob_to_temp_file, run_gpt_summary, fetch_model_prompt_and_schema, 
    split_pdf_into_subsets
)
from ai_ocr.model import Config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MAX_TIMEOUT = 45*60  # Set timeout duration in seconds

# Azure credentials
credential = DefaultAzureCredential()

# Global variables for Azure clients
blob_service_client = None
data_container = None
conf_container = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Azure clients on startup"""
    global blob_service_client, data_container, conf_container
    
    try:
        # Initialize blob service client
        storage_account_url = os.getenv('BLOB_ACCOUNT_URL')
        if not storage_account_url:
            raise ValueError("BLOB_ACCOUNT_URL environment variable is required")
        
        blob_service_client = BlobServiceClient(
            account_url=storage_account_url,
            credential=credential
        )
        
        # Initialize Cosmos DB containers
        data_container, conf_container = connect_to_cosmos()
        
        logger.info("Successfully initialized Azure clients")
        
    except Exception as e:
        logger.error(f"Failed to initialize Azure clients: {e}")
        raise
    
    yield
    
    # Cleanup
    logger.info("Shutting down application")

# Initialize FastAPI app
app = FastAPI(
    title="ARGUS Backend",
    description="Document processing backend using Azure AI services",
    version="1.0.0",
    lifespan=lifespan
)

class EventGridEvent:
    """Event Grid event model"""
    def __init__(self, event_data: Dict[str, Any]):
        self.id = event_data.get('id')
        self.event_type = event_data.get('eventType')
        self.subject = event_data.get('subject')
        self.event_time = event_data.get('eventTime')
        self.data = event_data.get('data', {})
        self.data_version = event_data.get('dataVersion')
        self.metadata_version = event_data.get('metadataVersion')

class BlobInputStream:
    """Mock BlobInputStream to match the original function interface"""
    def __init__(self, blob_name: str, blob_size: int, blob_client):
        self.name = blob_name
        self.length = blob_size
        self._blob_client = blob_client
        self._content = None
    
    def read(self, size: int = -1):
        """Read blob content"""
        if self._content is None:
            blob_data = self._blob_client.download_blob()
            self._content = blob_data.readall()
        
        if size == -1:
            return self._content
        else:
            return self._content[:size]

def create_blob_input_stream(blob_url: str) -> BlobInputStream:
    """Create a BlobInputStream from a blob URL"""
    try:
        # Parse blob URL to get container and blob name
        # Format: https://accountname.blob.core.windows.net/container/blob
        url_parts = blob_url.replace('https://', '').split('/')
        account_name = url_parts[0].split('.')[0]
        container_name = url_parts[1]
        blob_name = '/'.join(url_parts[2:])
        
        # Get blob client
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        # Get blob properties
        blob_properties = blob_client.get_blob_properties()
        blob_size = blob_properties.size
        
        return BlobInputStream(blob_name, blob_size, blob_client)
        
    except Exception as e:
        logger.error(f"Error creating blob input stream: {e}")
        raise

def process_blob_async(blob_input_stream: BlobInputStream, data_container):
    """Process blob asynchronously - same logic as original function"""
    try:
        logger.info(f"Processing blob: {blob_input_stream.name}")
        
        # Your existing blob processing logic here
        # This calls the same process_blob function from your original code
        process_blob(blob_input_stream, data_container)
        
        logger.info(f"Successfully processed blob: {blob_input_stream.name}")
        
    except Exception as e:
        logger.error(f"Error processing blob {blob_input_stream.name}: {e}")
        logger.error(traceback.format_exc())
        raise

def handle_timeout_error_async(blob_input_stream: BlobInputStream, data_container):
    """Handle timeout error - same logic as original function"""
    document_id = blob_input_stream.name.replace('/', '__')
    try:
        document = data_container.read_item(item=document_id, partition_key={})
        # Handle timeout logic here
        logger.warning(f"Timeout occurred for document: {document_id}")
    except Exception as e:
        logger.error(f"Error handling timeout for document {document_id}: {e}")

@app.get("/")
async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ARGUS Backend"}

@app.get("/health")
async def health_check():
    """Detailed health check"""
    try:
        # Check if we can connect to storage
        if blob_service_client:
            account_info = blob_service_client.get_account_information()
        
        # Check if we can connect to Cosmos DB
        if data_container and conf_container:
            # Try to query Cosmos DB
            list(data_container.query_items(
                query="SELECT TOP 1 * FROM c",
                enable_cross_partition_query=True
            ))
        
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "storage": "connected",
                "cosmos_db": "connected"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.post("/api/blob-created")
async def handle_blob_created(request: Request, background_tasks: BackgroundTasks):
    """Handle Event Grid blob created events"""
    try:
        # Parse the Event Grid request
        request_body = await request.json()
        
        # Handle Event Grid subscription validation
        if isinstance(request_body, list) and len(request_body) > 0:
            event = request_body[0]
            
            # Handle subscription validation
            if event.get('eventType') == 'Microsoft.EventGrid.SubscriptionValidationEvent':
                validation_code = event.get('data', {}).get('validationCode')
                if validation_code:
                    return {"validationResponse": validation_code}
        
        # Process blob created events
        events = request_body if isinstance(request_body, list) else [request_body]
        
        for event_data in events:
            event = EventGridEvent(event_data)
            
            if event.event_type == 'Microsoft.Storage.BlobCreated':
                blob_url = event.data.get('url')
                if blob_url and '/datasets/' in blob_url:
                    logger.info(f"Processing blob created event for: {blob_url}")
                    
                    # Add to background tasks for async processing
                    background_tasks.add_task(
                        process_blob_event,
                        blob_url,
                        event.data
                    )
        
        return {"status": "accepted", "message": "Events queued for processing"}
        
    except Exception as e:
        logger.error(f"Error handling blob created event: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

async def process_blob_event(blob_url: str, event_data: Dict[str, Any]):
    """Process a single blob event in the background"""
    try:
        # Create blob input stream
        blob_input_stream = create_blob_input_stream(blob_url)
        
        logger.info(f"Processing blob event for: {blob_input_stream.name}")
        
        # Use ThreadPoolExecutor for CPU-intensive work
        with ThreadPoolExecutor() as executor:
            future = executor.submit(
                process_blob_async,
                blob_input_stream,
                data_container
            )
            
            try:
                # Wait for processing with timeout
                future.result(timeout=MAX_TIMEOUT)
                logger.info(f"Successfully processed blob: {blob_input_stream.name}")
                
            except FuturesTimeoutError:
                logger.error(f"Timeout processing blob: {blob_input_stream.name}")
                handle_timeout_error_async(blob_input_stream, data_container)
                
    except Exception as e:
        logger.error(f"Error in background blob processing: {e}")
        logger.error(traceback.format_exc())

@app.post("/api/process-blob")
async def process_blob_manual(request: Request, background_tasks: BackgroundTasks):
    """Manually trigger blob processing (for testing)"""
    try:
        request_body = await request.json()
        blob_url = request_body.get('blob_url')
        
        if not blob_url:
            raise HTTPException(status_code=400, detail="blob_url is required")
        
        # Add to background tasks
        background_tasks.add_task(
            process_blob_event,
            blob_url,
            {"url": blob_url}
        )
        
        return {"status": "accepted", "message": "Blob queued for processing"}
        
    except Exception as e:
        logger.error(f"Error in manual blob processing: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Helper functions for blob processing
def initialize_document_data(blob_name: str, temp_file_path: str, num_pages: int, file_size: int, data_container):
    """Initialize document data for processing"""
    timer_start = datetime.now()
    
    # Determine dataset type from blob name
    logger.info(f"Processing blob with name: {blob_name}")
    
    # Handle blob path parsing
    blob_parts = blob_name.split('/')
    if len(blob_parts) < 2:
        # If no folder structure, default to 'default-dataset'
        logger.warning(f"Blob name {blob_name} doesn't contain folder structure, defaulting to 'default-dataset'")
        dataset_type = 'default-dataset'
    else:
        dataset_type = blob_parts[0]  # Take the first part as dataset type
    
    logger.info(f"Using dataset type: {dataset_type}")
    
    prompt, json_schema = fetch_model_prompt_and_schema(dataset_type)
    if prompt is None or json_schema is None:
        raise ValueError("Failed to fetch model prompt and schema from configuration.")
    
    document = initialize_document(blob_name, file_size, num_pages, prompt, json_schema, timer_start, dataset_type)
    update_state(document, data_container, 'file_landed', True, (datetime.now() - timer_start).total_seconds())
    return document

def merge_extracted_data(gpt_responses):
    """Merge extracted data from multiple GPT responses"""
    merged_data = {}
    for response in gpt_responses:
        for key, value in response.items():
            if key in merged_data:
                if isinstance(value, list):
                    merged_data[key].extend(value)
                else:
                    # Decide how to handle non-list duplicates - keeping latest value
                    merged_data[key] = value
            else:
                if isinstance(value, list):
                    merged_data[key] = value.copy()
                else:
                    merged_data[key] = value
    return merged_data

def update_final_document(document, gpt_response, ocr_response, evaluation_result, processing_times, data_container):
    """Update the final document with all processing results"""
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    
    document['extracted_data'].update({
        "gpt_extraction_output_with_evaluation": evaluation_result,
        "gpt_extraction_output": gpt_response,
        "ocr_output": '\n'.join(str(result) for result in ocr_response)
    })
    
    document['state']['processing_completed'] = True
    update_state(document, data_container, 'processing_completed', True)

# BlobInputStream class defined earlier in the file

def process_blob(blob_input_stream: BlobInputStream, data_container):
    """Process a blob for OCR and data extraction (adapted for container app)"""
    temp_file_path, num_pages, file_size = write_blob_to_temp_file(blob_input_stream)
    logger.info("processing blob")
    document = initialize_document_data(blob_input_stream.name, temp_file_path, num_pages, file_size, data_container)
    
    processing_times = {}
    file_paths = []
    temp_dirs = []
    
    try:
        # Prepare all file paths
        if num_pages and num_pages > 10:
            file_paths = split_pdf_into_subsets(temp_file_path, max_pages_per_subset=10)
        else:
            file_paths = [temp_file_path]

        # Step 1: Run OCR for all files
        ocr_results = []
        total_ocr_time = 0
        for file_path in file_paths:
            ocr_result, ocr_time = run_ocr_processing(file_path, document, data_container)
            ocr_results.append(ocr_result)
            total_ocr_time += ocr_time
            
        processing_times['ocr_processing_time'] = total_ocr_time
        document['extracted_data']['ocr_output'] = '\n'.join(str(result) for result in ocr_results)
        data_container.upsert_item(document)

        # Step 2: Prepare images and run GPT extraction for all files
        extracted_data_list = []
        total_extraction_time = 0
        for file_path in file_paths:
            temp_dir, imgs = prepare_images(file_path, Config())
            temp_dirs.append(temp_dir)
            
            extracted_data, extraction_time = run_gpt_extraction(
                ocr_results[file_paths.index(file_path)],
                document['model_input']['model_prompt'],
                document['model_input']['example_schema'],
                imgs,
                document,
                data_container
            )
            extracted_data_list.append(extracted_data)
            total_extraction_time += extraction_time

        processing_times['gpt_extraction_time'] = total_extraction_time
        merged_extraction = merge_extracted_data(extracted_data_list)
        document['extracted_data']['gpt_extraction_output'] = merged_extraction
        data_container.upsert_item(document)

        # Step 3: Run GPT evaluation for all files
        evaluation_results = []
        total_evaluation_time = 0
        for i, file_path in enumerate(file_paths):
            temp_dir = temp_dirs[i]
            # Using the same prepare_images function that existed before
            _, imgs = prepare_images(file_path, Config())
            
            enriched_data, evaluation_time = run_gpt_evaluation(
                imgs,
                extracted_data_list[i],
                document['model_input']['example_schema'],
                document,
                data_container
            )
            evaluation_results.append(enriched_data)
            total_evaluation_time += evaluation_time

        processing_times['gpt_evaluation_time'] = total_evaluation_time
        merged_evaluation = merge_extracted_data(evaluation_results)
        document['extracted_data']['gpt_extraction_output_with_evaluation'] = merged_evaluation
        data_container.upsert_item(document)

        # Step 4: Process final summary
        run_gpt_summary(ocr_results, document, data_container)
        
        # Final update
        update_final_document(document, merged_extraction, ocr_results, 
                            merged_evaluation, processing_times, data_container)
        
        return document
        
    except Exception as e:
        document['errors'].append(f"Processing error: {str(e)}")
        document['state']['processing_completed'] = False
        data_container.upsert_item(document)
        raise e

# Additional API endpoints for frontend integration

@app.get("/api/configuration")
async def get_configuration():
    """Get current configuration from Cosmos DB"""
    try:
        if not conf_container:
            raise HTTPException(status_code=503, detail="Configuration container not available")
        
        try:
            # Try to get the main configuration item
            config_item = conf_container.read_item(item='configuration', partition_key='configuration')
            # Remove Cosmos DB specific fields
            clean_config = {k: v for k, v in config_item.items() if not k.startswith('_')}
            return clean_config
        except Exception as e:
            logger.warning(f"Configuration item not found, returning default: {e}")
            # Return default configuration structure
            return {
                "id": "configuration",
                "partitionKey": "configuration", 
                "datasets": {}
            }
        
    except Exception as e:
        logger.error(f"Error fetching configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch configuration")

@app.post("/api/configuration")
async def update_configuration(request: Request):
    """Update configuration in Cosmos DB"""
    try:
        if not conf_container:
            raise HTTPException(status_code=503, detail="Configuration container not available")
        
        config_data = await request.json()
        
        # Ensure the configuration has required fields
        if "id" not in config_data:
            config_data["id"] = "configuration"
        if "partitionKey" not in config_data:
            config_data["partitionKey"] = "configuration"
        
        # Upsert the single configuration item
        conf_container.upsert_item(config_data)
        
        return {"status": "success", "message": "Configuration updated"}
        
    except Exception as e:
        logger.error(f"Error updating configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to update configuration")

@app.delete("/api/documents/{document_id}")
async def delete_document(document_id: str):
    """Delete a document and its associated blob"""
    try:
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # First, get the document to find the blob name
        try:
            document = data_container.read_item(item=document_id, partition_key=document_id)
            blob_name = document.get('properties', {}).get('blob_name', '')
            
            # Delete from Cosmos DB
            data_container.delete_item(item=document_id, partition_key=document_id)
            
            # Delete from blob storage if blob name is available
            if blob_name and blob_service_client:
                blob_client = blob_service_client.get_blob_client(container='datasets', blob=blob_name)
                try:
                    blob_client.delete_blob()
                    logger.info(f"Deleted blob: {blob_name}")
                except Exception as blob_error:
                    logger.warning(f"Failed to delete blob {blob_name}: {blob_error}")
            
            return {"status": "success", "message": f"Document {document_id} deleted"}
            
        except Exception as e:
            if "Not Found" in str(e):
                raise HTTPException(status_code=404, detail="Document not found")
            raise e
            
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")

@app.post("/api/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str, background_tasks: BackgroundTasks):
    """Reprocess a document by triggering the processing pipeline"""
    try:
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Get the document to find blob name
        try:
            document = data_container.read_item(item=document_id, partition_key=document_id)
            blob_name = document.get('properties', {}).get('blob_name', '')
            
            if not blob_name:
                raise HTTPException(status_code=400, detail="Document blob name not found")
            
            # Reset the document state for reprocessing
            document['state'] = {
                'file_landed': False,
                'ocr_completed': False,
                'gpt_extraction_completed': False,
                'gpt_evaluation_completed': False,
                'gpt_summary_completed': False,
                'processing_completed': False
            }
            
            # Update the document in Cosmos DB
            data_container.upsert_item(document)
            
            # Trigger reprocessing by simulating a blob event
            blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/datasets/{blob_name}"
            
            # Create a simulated event for reprocessing
            simulated_event = {
                'id': f'reprocess-{document_id}',
                'eventType': 'Microsoft.Storage.BlobCreated',
                'subject': f'/blobServices/default/containers/datasets/blobs/{blob_name}',
                'eventTime': datetime.now().isoformat(),
                'data': {
                    'api': 'PutBlob',
                    'requestId': f'reprocess-{document_id}',
                    'eTag': 'mock-etag',
                    'contentType': 'application/octet-stream',
                    'contentLength': document.get('properties', {}).get('blob_size', 0),
                    'blobType': 'BlockBlob',
                    'url': blob_url,
                    'sequencer': f'reprocess-{datetime.now().timestamp()}'
                }
            }
            
            # Add the processing task to background
            background_tasks.add_task(process_blob_event, blob_url, simulated_event['data'])
            
            return {"status": "success", "message": f"Document {document_id} queued for reprocessing"}
            
        except Exception as e:
            if "Not Found" in str(e):
                raise HTTPException(status_code=404, detail="Document not found")
            raise e
            
    except Exception as e:
        logger.error(f"Error reprocessing document {document_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to reprocess document")

# ===============================================
# Helper Functions
# ===============================================

def extract_document_info(doc):
    """Extract document information with proper dataset and filename parsing"""
    # Extract filename and dataset from document ID or other fields
    doc_id = doc.get("id", "")
    
    # Initialize defaults
    filename = "unknown"
    dataset = "unknown"
    
    # Method 1: Extract from document ID (format: dataset__filename) - This is the primary method
    if "__" in doc_id:
        parts = doc_id.split("__", 1)
        dataset = parts[0]
        filename = parts[1]
    
    # Method 2: Extract from properties.blob_name (most common in CosmosDB)
    properties = doc.get("properties", {})
    blob_name = properties.get("blob_name", "")
    if blob_name and "/" in blob_name:
        # Format: "dataset/filename.pdf"
        blob_parts = blob_name.split("/")
        if len(blob_parts) >= 2:
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])  # Handle nested paths
    
    # Method 3: Fallback to root-level blob_name if properties.blob_name not found
    elif doc.get("blob_name"):
        blob_name = doc.get("blob_name")
        if "/" in blob_name:
            blob_parts = blob_name.split("/")
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])
        else:
            filename = blob_name
    
    # Method 4: Use direct dataset/filename fields if available (override if they exist)
    if doc.get("dataset"):
        dataset = doc.get("dataset")
    if doc.get("file_name"):
        filename = doc.get("file_name")
    elif doc.get("filename"):
        filename = doc.get("filename")
    
    # Method 5: Extract from other properties fields as fallback
    if filename == "unknown":
        filename = (properties.get("original_filename") or 
                   properties.get("filename") or 
                   "unknown")
    
    # Final fallback for dataset
    if dataset == "unknown":
        dataset = (doc.get("dataset") or 
                  properties.get("dataset") or 
                  "default")
    
    # Remove Cosmos DB specific fields and simplify structure
    cleaned_doc = {
        "id": doc.get("id"),
        "file_name": filename,
        "dataset": dataset,
        "finished": doc.get("state", {}).get("processing_completed", False),
        "error": bool(doc.get("errors", [])),
        "created_at": doc.get("properties", {}).get("request_timestamp"),
        "modified_at": doc.get("_ts"),
        "size": doc.get("properties", {}).get("blob_size"),
        "pages": doc.get("properties", {}).get("num_pages"),
        "total_time": doc.get("properties", {}).get("total_time_seconds", 0),
        "extracted_data": doc.get("extracted_data", {}),
        "state": doc.get("state", {})
    }
    return cleaned_doc

# ===============================================
# API Endpoints  
# ===============================================

@app.get("/api/datasets")
async def get_datasets():
    """Get list of available datasets from blob storage"""
    try:
        if not blob_service_client:
            raise HTTPException(status_code=503, detail="Blob service not available")
        
        # Get the datasets container
        datasets_container_client = blob_service_client.get_container_client("datasets")
        
        # List all "folders" (blob prefixes) in the datasets container
        datasets = set()
        blobs = datasets_container_client.list_blobs()
        
        for blob in blobs:
            # Extract dataset name from blob path (first part before '/')
            if '/' in blob.name:
                dataset_name = blob.name.split('/')[0]
                datasets.add(dataset_name)
        
        return sorted(list(datasets))
        
    except Exception as e:
        logger.error(f"Error fetching datasets: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch datasets")

@app.get("/api/datasets/{dataset_name}/files")
async def get_dataset_files(dataset_name: str):
    """Get files in a specific dataset"""
    try:
        if not blob_service_client:
            raise HTTPException(status_code=503, detail="Blob service not available")
        
        datasets_container_client = blob_service_client.get_container_client("datasets")
        
        # List blobs with the dataset prefix
        blobs = datasets_container_client.list_blobs(name_starts_with=f"{dataset_name}/")
        
        files = []
        for blob in blobs:
            files.append({
                "name": blob.name,
                "size": blob.size,
                "last_modified": blob.last_modified.isoformat() if blob.last_modified else None,
                "content_type": blob.content_settings.content_type if blob.content_settings else None
            })
        
        return files
        
    except Exception as e:
        logger.error(f"Error fetching dataset files: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dataset files")

@app.get("/api/documents")
async def get_documents(dataset: str = None):
    """Get processed documents from Cosmos DB"""
    try:
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Build query based on parameters
        if dataset:
            query = "SELECT * FROM c WHERE c.dataset = @dataset"
            parameters = [{"name": "@dataset", "value": dataset}]
        else:
            query = "SELECT * FROM c"
            parameters = None
        
        # Query documents
        documents = list(data_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))
        
        # Clean up documents for frontend consumption using helper function
        cleaned_docs = []
        for doc in documents:
            cleaned_doc = extract_document_info(doc)
            cleaned_docs.append(cleaned_doc)
        
        return cleaned_docs
        
    except Exception as e:
        logger.error(f"Error fetching documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch documents")

@app.get("/api/documents/{document_id}")
async def get_document_details(document_id: str):
    """Get details for a specific document from Cosmos DB"""
    try:
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Query for the specific document
        try:
            document = data_container.read_item(item=document_id, partition_key={})
            
            # Apply the same extraction logic as in the list endpoint
            cleaned_document = extract_document_info(document)
            return cleaned_document
            
        except Exception as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
            
    except Exception as e:
        logger.error(f"Error fetching document details: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch document details")

from fastapi import UploadFile, File, Form

@app.post("/api/upload")
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    dataset_name: str = Form(...)
):
    """Upload a file to a specific dataset"""
    try:
        if not blob_service_client:
            raise HTTPException(status_code=503, detail="Blob service not available")
        
        # Read file content
        file_content = await file.read()
        
        # Create blob path
        blob_name = f"{dataset_name}/{file.filename}"
        
        # Upload to blob storage
        datasets_container_client = blob_service_client.get_container_client("datasets")
        blob_client = datasets_container_client.get_blob_client(blob_name)
        
        blob_client.upload_blob(
            file_content,
            overwrite=True,
            content_settings=ContentSettings(
                content_type=file.content_type or "application/octet-stream"
            )
        )
        
        # Trigger processing manually since Event Grid is not configured
        blob_url = f"{blob_service_client.url.rstrip('/')}/datasets/{blob_name}"
        logger.info(f"Triggering manual processing for uploaded file: {blob_url}")
        
        # Add to background tasks for async processing
        background_tasks.add_task(
            process_blob_event,
            blob_url,
            {"url": blob_url, "api": blob_name}
        )
        
        return {
            "status": "success",
            "message": f"File {file.filename} uploaded to dataset {dataset_name}",
            "blob_name": blob_name,
            "size": len(file_content)
        }
        
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Failed to upload file")

def extract_document_info(doc):
    """Extract document information with proper dataset and filename parsing"""
    # Extract filename and dataset from document ID or other fields
    doc_id = doc.get("id", "")
    
    # Initialize defaults
    filename = "unknown"
    dataset = "unknown"
    
    # Method 1: Extract from document ID (format: dataset__filename) - This is the primary method
    if "__" in doc_id:
        parts = doc_id.split("__", 1)
        dataset = parts[0]
        filename = parts[1]
    
    # Method 2: Extract from properties.blob_name (most common in CosmosDB)
    properties = doc.get("properties", {})
    blob_name = properties.get("blob_name", "")
    if blob_name and "/" in blob_name:
        # Format: "dataset/filename.pdf"
        blob_parts = blob_name.split("/")
        if len(blob_parts) >= 2:
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])  # Handle nested paths
    
    # Method 3: Fallback to root-level blob_name if properties.blob_name not found
    elif doc.get("blob_name"):
        blob_name = doc.get("blob_name")
        if "/" in blob_name:
            blob_parts = blob_name.split("/")
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])
        else:
            filename = blob_name
    
    # Method 4: Use direct dataset/filename fields if available (override if they exist)
    if doc.get("dataset"):
        dataset = doc.get("dataset")
    if doc.get("file_name"):
        filename = doc.get("file_name")
    elif doc.get("filename"):
        filename = doc.get("filename")
    
    # Method 5: Extract from other properties fields as fallback
    if filename == "unknown":
        filename = (properties.get("original_filename") or 
                   properties.get("filename") or 
                   "unknown")
    
    # Final fallback for dataset
    if dataset == "unknown":
        dataset = (doc.get("dataset") or 
                  properties.get("dataset") or 
                  "default")
    
    # Remove Cosmos DB specific fields and simplify structure
    cleaned_doc = {
        "id": doc.get("id"),
        "file_name": filename,
        "dataset": dataset,
        "finished": doc.get("state", {}).get("processing_completed", False),
        "error": bool(doc.get("errors", [])),
        "created_at": doc.get("properties", {}).get("request_timestamp"),
        "modified_at": doc.get("_ts"),
        "size": doc.get("properties", {}).get("blob_size"),
        "pages": doc.get("properties", {}).get("num_pages"),
        "total_time": doc.get("properties", {}).get("total_time_seconds", 0),
        "extracted_data": doc.get("extracted_data", {}),
        "state": doc.get("state", {})
    }
    return cleaned_doc
