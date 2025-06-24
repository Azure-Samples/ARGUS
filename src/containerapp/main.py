"""
Container App version of the ARGUS backend
Handles HTTP requests from Event Grid instead of blob triggers
"""
import logging
import os
import json
import traceback
import sys
import copy
import shutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Dict, Any
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from azure.storage.blob import BlobServiceClient, ContentSettings
from azure.identity import DefaultAzureCredential
from azure.mgmt.logic import LogicManagementClient
from azure.mgmt.resource import ResourceManagementClient
from openai import AzureOpenAI
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
from ai_ocr.azure.config import get_config

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
logic_app_manager = None

# Global thread pool executor for parallel processing
global_executor = None

# Global semaphore for concurrency control based on Logic App settings
global_processing_semaphore = None

class LogicAppManager:
    """Manages Logic App concurrency settings via Azure Management API"""
    
    def __init__(self):
        self.credential = DefaultAzureCredential()
        self.subscription_id = os.getenv('AZURE_SUBSCRIPTION_ID')
        self.resource_group_name = os.getenv('AZURE_RESOURCE_GROUP_NAME')
        self.logic_app_name = os.getenv('LOGIC_APP_NAME')
        
        if not all([self.subscription_id, self.resource_group_name, self.logic_app_name]):
            logger.warning("Logic App management requires AZURE_SUBSCRIPTION_ID, AZURE_RESOURCE_GROUP_NAME, and LOGIC_APP_NAME environment variables")
            self.enabled = False
        else:
            self.enabled = True
            logger.info(f"Logic App Manager initialized for {self.logic_app_name} in {self.resource_group_name}")
    
    def get_logic_management_client(self):
        """Create a Logic Management client"""
        if not self.enabled:
            raise ValueError("Logic App Manager is not properly configured")
        return LogicManagementClient(self.credential, self.subscription_id)
    
    async def get_concurrency_settings(self) -> Dict[str, Any]:
        """Get current Logic App concurrency settings"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "enabled": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the Logic App workflow
            workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Extract concurrency settings from workflow definition
            definition = workflow.definition or {}
            triggers = definition.get('triggers', {})
            
            # Get concurrency from the first trigger (most common case)
            runs_on = 1  # Default value
            trigger_name = None
            for name, trigger_config in triggers.items():
                trigger_name = name
                runtime_config = trigger_config.get('runtimeConfiguration', {})
                concurrency = runtime_config.get('concurrency', {})
                runs_on = concurrency.get('runs', 1)
                break  # Use the first trigger found
            
            return {
                "enabled": True,
                "logic_app_name": self.logic_app_name,
                "resource_group": self.resource_group_name,
                "current_max_runs": runs_on,
                "trigger_name": trigger_name,
                "workflow_state": workflow.state,
                "last_modified": workflow.changed_time.isoformat() if workflow.changed_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting Logic App concurrency settings: {e}")
            return {"error": str(e), "enabled": False}
    
    async def update_concurrency_settings(self, max_runs: int) -> Dict[str, Any]:
        """Update Logic App concurrency settings"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "success": False}
            
            if max_runs < 1 or max_runs > 100:
                return {"error": "Max runs must be between 1 and 100", "success": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the current workflow
            current_workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Update the workflow definition with new concurrency settings
            updated_definition = current_workflow.definition.copy() if current_workflow.definition else {}
            
            # Find the trigger and update its concurrency settings using runtimeConfiguration
            triggers = updated_definition.get('triggers', {})
            for trigger_name, trigger_config in triggers.items():
                # Set runtime configuration for concurrency control
                if 'runtimeConfiguration' not in trigger_config:
                    trigger_config['runtimeConfiguration'] = {}
                if 'concurrency' not in trigger_config['runtimeConfiguration']:
                    trigger_config['runtimeConfiguration']['concurrency'] = {}
                trigger_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                logger.info(f"Updated concurrency for trigger {trigger_name} to {max_runs}")
            
            # Create the workflow update request using the proper Workflow object
            from azure.mgmt.logic.models import Workflow
            
            workflow_update = Workflow(
                location=current_workflow.location,
                definition=updated_definition,
                state=current_workflow.state,
                parameters=current_workflow.parameters,
                tags=current_workflow.tags  # Include tags to maintain existing metadata
            )
            
            # Update the workflow
            updated_workflow = logic_client.workflows.create_or_update(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name,
                workflow=workflow_update
            )
            
            logger.info(f"Successfully updated Logic App {self.logic_app_name} max concurrent runs to {max_runs}")
            
            return {
                "success": True,
                "logic_app_name": self.logic_app_name,
                "new_max_runs": max_runs,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating Logic App concurrency settings: {e}")
            return {"error": str(e), "success": False}

    async def get_workflow_definition(self) -> Dict[str, Any]:
        """Get the complete Logic App workflow definition for inspection"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "enabled": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the Logic App workflow
            workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            return {
                "enabled": True,
                "logic_app_name": self.logic_app_name,
                "resource_group": self.resource_group_name,
                "workflow_state": workflow.state,
                "definition": workflow.definition,
                "last_modified": workflow.changed_time.isoformat() if workflow.changed_time else None
            }
            
        except Exception as e:
            logger.error(f"Error getting Logic App workflow definition: {e}")
            return {"error": str(e), "enabled": False}

    async def update_action_concurrency_settings(self, max_runs: int) -> Dict[str, Any]:
        """Update Logic App action-level concurrency settings for HTTP actions"""
        try:
            if not self.enabled:
                return {"error": "Logic App Manager not configured", "success": False}
            
            if max_runs < 1 or max_runs > 100:
                return {"error": "Max runs must be between 1 and 100", "success": False}
            
            logic_client = self.get_logic_management_client()
            
            # Get the current workflow
            current_workflow = logic_client.workflows.get(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name
            )
            
            # Update the workflow definition with new concurrency settings
            updated_definition = current_workflow.definition.copy() if current_workflow.definition else {}
            
            # Update trigger-level concurrency
            triggers = updated_definition.get('triggers', {})
            for trigger_name, trigger_config in triggers.items():
                if 'runtimeConfiguration' not in trigger_config:
                    trigger_config['runtimeConfiguration'] = {}
                if 'concurrency' not in trigger_config['runtimeConfiguration']:
                    trigger_config['runtimeConfiguration']['concurrency'] = {}
                trigger_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                logger.info(f"Updated trigger concurrency for {trigger_name} to {max_runs}")
            
            # Update action-level concurrency for HTTP actions and loops
            actions = updated_definition.get('actions', {})
            updated_actions = 0
            
            def update_action_concurrency(actions_dict):
                nonlocal updated_actions
                for action_name, action_config in actions_dict.items():
                    # Set concurrency for HTTP actions
                    if action_config.get('type') in ['Http', 'ApiConnection']:
                        if 'runtimeConfiguration' not in action_config:
                            action_config['runtimeConfiguration'] = {}
                        if 'concurrency' not in action_config['runtimeConfiguration']:
                            action_config['runtimeConfiguration']['concurrency'] = {}
                        action_config['runtimeConfiguration']['concurrency']['runs'] = max_runs
                        logger.info(f"Updated action concurrency for {action_name} to {max_runs}")
                        updated_actions += 1
                    
                    # Handle nested actions in conditionals and loops
                    if 'actions' in action_config:
                        update_action_concurrency(action_config['actions'])
                    if 'else' in action_config and 'actions' in action_config['else']:
                        update_action_concurrency(action_config['else']['actions'])
                    
                    # Handle foreach loops specifically
                    if action_config.get('type') == 'Foreach':
                        if 'runtimeConfiguration' not in action_config:
                            action_config['runtimeConfiguration'] = {}
                        if 'concurrency' not in action_config['runtimeConfiguration']:
                            action_config['runtimeConfiguration']['concurrency'] = {}
                        action_config['runtimeConfiguration']['concurrency']['repetitions'] = max_runs
                        logger.info(f"Updated foreach concurrency for {action_name} to {max_runs}")
                        updated_actions += 1
                        
                        # Also update nested actions
                        if 'actions' in action_config:
                            update_action_concurrency(action_config['actions'])
            
            update_action_concurrency(actions)
            
            # Create the workflow update request
            from azure.mgmt.logic.models import Workflow
            
            workflow_update = Workflow(
                location=current_workflow.location,
                definition=updated_definition,
                state=current_workflow.state,
                parameters=current_workflow.parameters,
                tags=current_workflow.tags
            )
            
            # Update the workflow
            updated_workflow = logic_client.workflows.create_or_update(
                resource_group_name=self.resource_group_name,
                workflow_name=self.logic_app_name,
                workflow=workflow_update
            )
            
            logger.info(f"Successfully updated Logic App {self.logic_app_name} concurrency: trigger and {updated_actions} actions to {max_runs}")
            
            return {
                "success": True,
                "logic_app_name": self.logic_app_name,
                "new_max_runs": max_runs,
                "updated_triggers": len(triggers),
                "updated_actions": updated_actions,
                "updated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error updating Logic App action concurrency settings: {e}")
            return {"error": str(e), "success": False}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize Azure clients on startup"""
    global blob_service_client, data_container, conf_container, global_executor, logic_app_manager, global_processing_semaphore
    
    try:
        # Initialize global thread pool executor
        global_executor = ThreadPoolExecutor(max_workers=10)
        logger.info("Initialized global ThreadPoolExecutor with 10 workers")
        
        # Initialize processing semaphore with default concurrency of 1
        # This will be updated when Logic App concurrency settings are retrieved
        global_processing_semaphore = asyncio.Semaphore(1)
        logger.info("Initialized global processing semaphore with 1 permit")
        
        # Initialize Logic App Manager
        logic_app_manager = LogicAppManager()
        
        # Try to get current Logic App concurrency to set proper semaphore value
        if logic_app_manager.enabled:
            try:
                settings = await logic_app_manager.get_concurrency_settings()
                if settings.get('enabled'):
                    max_runs = settings.get('current_max_runs', 1)
                    global_processing_semaphore = asyncio.Semaphore(max_runs)
                    logger.info(f"Updated processing semaphore to {max_runs} permits based on Logic App settings")
            except Exception as e:
                logger.warning(f"Could not retrieve Logic App concurrency settings on startup: {e}")
        
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
    if global_executor:
        logger.info("Shutting down global ThreadPoolExecutor")
        global_executor.shutdown(wait=True)
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
    import threading
    thread_id = threading.current_thread().ident
    
    try:
        logger.info(f"[Thread-{thread_id}] Starting blob processing: {blob_input_stream.name}")
        
        # Your existing blob processing logic here
        # This calls the same process_blob function from your original code
        start_time = datetime.now()
        process_blob(blob_input_stream, data_container)
        end_time = datetime.now()
        
        logger.info(f"[Thread-{thread_id}] Successfully processed blob: {blob_input_stream.name} in {(end_time - start_time).total_seconds():.2f}s")
        
    except Exception as e:
        logger.error(f"[Thread-{thread_id}] Error processing blob {blob_input_stream.name}: {e}")
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
    """Process a single blob event in the background with concurrency control"""
    try:
        # Create blob input stream
        blob_input_stream = create_blob_input_stream(blob_url)
        
        logger.info(f"Processing blob event for: {blob_input_stream.name}")
        
        # Use semaphore to control concurrency
        if global_processing_semaphore:
            async with global_processing_semaphore:
                logger.info(f"Acquired semaphore for processing: {blob_input_stream.name}")
                
                # Use global ThreadPoolExecutor for processing
                if global_executor:
                    # Run in executor but await the result to maintain semaphore control
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        global_executor,
                        process_blob_async,
                        blob_input_stream,
                        data_container
                    )
                    logger.info(f"Completed processing for: {blob_input_stream.name}")
                else:
                    logger.error("Global executor not available")
        else:
            logger.error("Global processing semaphore not available")
                
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
    
    prompt, json_schema, max_pages_per_chunk, processing_options = fetch_model_prompt_and_schema(dataset_type)
    if prompt is None or json_schema is None:
        raise ValueError("Failed to fetch model prompt and schema from configuration.")
    
    document = initialize_document(blob_name, file_size, num_pages, prompt, json_schema, timer_start, dataset_type, max_pages_per_chunk, processing_options)
    update_state(document, data_container, 'file_landed', True, (datetime.now() - timer_start).total_seconds())
    return document

def merge_extracted_data(gpt_responses):
    """
    Merges extracted data from multiple GPT responses into a single result.
    
    This function properly handles different data types:
    - Lists: concatenated together
    - Strings: joined with spaces and cleaned up
    - Numbers: summed together
    - Dicts: recursively merged
    """
    if not gpt_responses:
        return {}
    
    # Start with the first response as base
    merged_data = copy.deepcopy(gpt_responses[0]) if gpt_responses else {}
    
    # Merge remaining responses
    for response in gpt_responses[1:]:
        merged_data = _deep_merge_data(merged_data, response)
    
    return merged_data


def _deep_merge_data(base_data, new_data):
    """
    Deep merge two data dictionaries with intelligent type handling.
    """
    if not isinstance(base_data, dict) or not isinstance(new_data, dict):
        return new_data if new_data else base_data
    
    result = copy.deepcopy(base_data)
    
    for key, value in new_data.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        else:
            existing_value = result[key]
            
            # Handle different data types appropriately
            if isinstance(existing_value, list) and isinstance(value, list):
                # Concatenate lists
                result[key] = existing_value + value
            elif isinstance(existing_value, str) and isinstance(value, str):
                # Join strings with space, clean up multiple spaces
                combined = f"{existing_value} {value}".strip()
                result[key] = " ".join(combined.split())  # Clean up multiple spaces
            elif isinstance(existing_value, (int, float)) and isinstance(value, (int, float)):
                # Sum numbers
                result[key] = existing_value + value
            elif isinstance(existing_value, dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = _deep_merge_data(existing_value, value)
            else:
                # For other types or type mismatches, prefer non-empty values
                if value:  # Use new value if it's truthy
                    result[key] = value
                # Otherwise keep existing value
    
    return result

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

def cleanup_temp_resources(temp_dirs, file_paths, temp_file_path):
    """
    Clean up temporary directories and files created during processing.
    Ensures proper resource cleanup even if processing fails.
    """
    import shutil
    
    # Clean up temporary directories
    for temp_dir in temp_dirs:
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
    
    # Clean up split PDF files (but not the original temp file)
    for file_path in file_paths:
        try:
            if file_path and file_path != temp_file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up split file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up split file {file_path}: {e}")
    
    # Clean up the main temporary file
    try:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up main temp file: {temp_file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up main temp file {temp_file_path}: {e}")


def process_blob(blob_input_stream: BlobInputStream, data_container):
    """Process a blob for OCR and data extraction (adapted for container app)"""
    overall_start_time = datetime.now()
    temp_file_path, num_pages, file_size = write_blob_to_temp_file(blob_input_stream)
    logger.info("processing blob")
    document = initialize_document_data(blob_input_stream.name, temp_file_path, num_pages, file_size, data_container)
    
    processing_times = {}
    file_paths = []
    temp_dirs = []
    
    try:
        # Prepare all file paths
        # Get processing options from document
        processing_options = document.get('processing_options', {
            "include_ocr": True,
            "include_images": True,
            "enable_summary": True,
            "enable_evaluation": True
        })
        
        logger.info(f"Processing options: OCR={processing_options.get('include_ocr', True)}, "
                   f"Images={processing_options.get('include_images', True)}, "
                   f"Summary={processing_options.get('enable_summary', True)}, "
                   f"Evaluation={processing_options.get('enable_evaluation', True)}")
        
        max_pages_per_chunk = document['model_input'].get('max_pages_per_chunk', 10)
        
        # Validate chunk size to prevent system overload
        if max_pages_per_chunk < 1:
            logger.warning(f"Invalid max_pages_per_chunk: {max_pages_per_chunk}, using default of 10")
            max_pages_per_chunk = 10
        elif max_pages_per_chunk > 50:  # Reasonable upper limit
            logger.warning(f"Large max_pages_per_chunk: {max_pages_per_chunk}, consider reducing for better performance")
        
        if num_pages and num_pages > max_pages_per_chunk:
            file_paths = split_pdf_into_subsets(temp_file_path, max_pages_per_subset=max_pages_per_chunk)
            logger.info(f"Split {num_pages} pages into {len(file_paths)} chunks of max {max_pages_per_chunk} pages each")
        else:
            file_paths = [temp_file_path]
            logger.info(f"Processing single file with {num_pages} pages (no chunking needed)")

        # Step 1: Run OCR for all files (conditional - only if OCR text will be used)
        ocr_results = []
        total_ocr_time = 0
        
        if processing_options.get('include_ocr', True):
            logger.info(f"Starting OCR processing for {len(file_paths)} chunks")
            ocr_start_time = datetime.now()
            for i, file_path in enumerate(file_paths):
                logger.info(f"Processing OCR for chunk {i+1}/{len(file_paths)}")
                ocr_result, ocr_time = run_ocr_processing(file_path, document, data_container, None, update_state=False)
                ocr_results.append(ocr_result)
                total_ocr_time += ocr_time
                
            # Only mark OCR as completed when ALL chunks are processed
            processing_times['ocr_processing_time'] = total_ocr_time
            document['extracted_data']['ocr_output'] = '\n'.join(str(result) for result in ocr_results)
            update_state(document, data_container, 'ocr_completed', True, total_ocr_time)
            data_container.upsert_item(document)
            logger.info(f"Completed OCR processing for all chunks in {total_ocr_time:.2f}s")
        else:
            logger.info("Skipping OCR processing (OCR text not needed for GPT extraction)")
            # Create empty OCR results for each chunk
            ocr_results = [""] * len(file_paths)
            processing_times['ocr_processing_time'] = 0
            document['extracted_data']['ocr_output'] = ""
            # Mark OCR as skipped, not completed
            update_state(document, data_container, 'ocr_skipped', True, 0)
            data_container.upsert_item(document)
            logger.info("OCR processing skipped - no OCR text will be extracted")

        # Step 2: Prepare images and run GPT extraction for all files
        logger.info(f"Starting GPT extraction for {len(file_paths)} chunks")
        extraction_start_time = datetime.now()
        extracted_data_list = []
        total_extraction_time = 0
        image_cache = {}  # Cache images to reuse between extraction and evaluation
        
        for i, file_path in enumerate(file_paths):
            logger.info(f"Processing GPT extraction for chunk {i+1}/{len(file_paths)}")
            
            # Prepare images only if image processing is enabled
            if processing_options.get('include_images', True):
                temp_dir, imgs = prepare_images(file_path, Config())
                temp_dirs.append(temp_dir)
                image_cache[i] = imgs  # Cache images for reuse
            else:
                imgs = []  # No images
                image_cache[i] = []
            
            # Use OCR text only if OCR inclusion is enabled
            ocr_text_for_extraction = ocr_results[i] if processing_options.get('include_ocr', True) else ""
            
            # Debug logging
            logger.info(f"GPT Extraction Debug - Chunk {i+1}:")
            logger.info(f"  - OCR text length: {len(ocr_text_for_extraction)} chars")
            logger.info(f"  - Number of images: {len(imgs)}")
            logger.info(f"  - OCR enabled: {processing_options.get('include_ocr', True)}")
            logger.info(f"  - Images enabled: {processing_options.get('include_images', True)}")
            
            # Check if we have any input at all
            if not ocr_text_for_extraction and not imgs:
                logger.error("No input provided to GPT extraction - both OCR text and images are empty!")
                raise ValueError("Cannot perform GPT extraction without either OCR text or images")
            
            extracted_data, extraction_time = run_gpt_extraction(
                ocr_text_for_extraction,
                document['model_input']['model_prompt'],
                document['model_input']['example_schema'],
                imgs,
                document,
                data_container,
                None,
                update_state=False  # Don't update state for individual chunks
            )
            extracted_data_list.append(extracted_data)
            total_extraction_time += extraction_time

        # Only mark extraction as completed when ALL chunks are processed
        processing_times['gpt_extraction_time'] = total_extraction_time
        # Create page range structure instead of merging
        page_range_extraction = create_page_range_structure(extracted_data_list, file_paths, max_pages_per_chunk)
        document['extracted_data']['gpt_extraction_output'] = page_range_extraction
        update_state(document, data_container, 'gpt_extraction_completed', True, total_extraction_time)
        data_container.upsert_item(document)
        logger.info(f"Completed GPT extraction for all chunks in {total_extraction_time:.2f}s with page range structure")

        # Initialize variables for conditional processing
        total_evaluation_time = 0
        summary_time = 0
        page_range_extraction = {}  # Initialize extraction result
        page_range_evaluation = {}  # Initialize evaluation result
        
        # Step 3: Run GPT evaluation for all files (conditional)
        if processing_options.get('enable_evaluation', True):
            logger.info(f"Starting GPT evaluation for {len(file_paths)} chunks")
            evaluation_start_time = datetime.now()
            evaluation_results = []
            for i, file_path in enumerate(file_paths):
                logger.info(f"Processing GPT evaluation for chunk {i+1}/{len(file_paths)}")
                # Use cached images instead of re-processing, but only if images were processed
                imgs = image_cache.get(i, [])
                
                enriched_data, evaluation_time = run_gpt_evaluation(
                    imgs,
                    extracted_data_list[i],
                    document['model_input']['example_schema'],
                    document,
                    data_container,
                    None,
                    update_state=False  # Don't update state for individual chunks
                )
                evaluation_results.append(enriched_data)
                total_evaluation_time += evaluation_time

            # Only mark evaluation as completed when ALL chunks are processed
            processing_times['gpt_evaluation_time'] = total_evaluation_time
            # Create page range structure for evaluations instead of merging
            page_range_evaluation = create_page_range_evaluations(evaluation_results, file_paths, max_pages_per_chunk)
            document['extracted_data']['gpt_extraction_output_with_evaluation'] = page_range_evaluation
            update_state(document, data_container, 'gpt_evaluation_completed', True, total_evaluation_time)
            data_container.upsert_item(document)
            logger.info(f"Completed GPT evaluation for all chunks in {total_evaluation_time:.2f}s with page range structure")
        else:
            logger.info("Skipping GPT evaluation (disabled in processing options)")
            # Set empty evaluation result when disabled
            page_range_evaluation = {}  # Empty dictionary instead of reusing extraction
            document['extracted_data']['gpt_extraction_output_with_evaluation'] = page_range_evaluation
            # Mark evaluation as skipped, not completed
            update_state(document, data_container, 'gpt_evaluation_skipped', True, 0)
            processing_times['gpt_evaluation_time'] = 0
            logger.info("GPT evaluation skipped - evaluation results will be empty")

        # Step 4: Process final summary (conditional)
        if processing_options.get('enable_summary', True):
            logger.info("Starting GPT summary processing")
            summary_start_time = datetime.now()
            # Combine OCR results into a single string for summary
            combined_ocr_text = '\n'.join(str(result) for result in ocr_results)
            summary_data, summary_time = run_gpt_summary(combined_ocr_text, document, data_container, None, update_state=False)
            
            # Update summary data in document
            document['extracted_data']['classification'] = summary_data['classification']
            document['extracted_data']['gpt_summary_output'] = summary_data['gpt_summary_output']
            update_state(document, data_container, 'gpt_summary_completed', True, summary_time)
            logger.info(f"Completed GPT summary processing in {summary_time:.2f}s")
        else:
            logger.info("Skipping GPT summary (disabled in processing options)")
            # Set empty values when disabled
            document['extracted_data']['classification'] = ""
            document['extracted_data']['gpt_summary_output'] = ""
            # Mark summary as failed, not completed
            update_state(document, data_container, 'gpt_summary_skipped', True, 0)
            summary_time = 0
            logger.info("GPT summary skipped - classification and summary will be empty")
        
        # Final update with accurate total processing time
        overall_end_time = datetime.now()
        total_processing_time = (overall_end_time - overall_start_time).total_seconds()
        
        logger.info(f"Processing completed for {blob_input_stream.name}")
        logger.info(f"Total time: {total_processing_time:.2f}s | OCR: {processing_times['ocr_processing_time']:.2f}s | "
                   f"Extraction: {processing_times['gpt_extraction_time']:.2f}s | "
                   f"Evaluation: {processing_times.get('gpt_evaluation_time', 0):.2f}s | Summary: {summary_time:.2f}s")
        
        # Log which steps were enabled/disabled
        logger.info(f"Processing options applied - OCR: {processing_options.get('include_ocr', True)}, "
                   f"Images: {processing_options.get('include_images', True)}, "
                   f"Summary: {processing_options.get('enable_summary', True)}, "
                   f"Evaluation: {processing_options.get('enable_evaluation', True)}")
        
        update_final_document(document, page_range_extraction, ocr_results, 
                            page_range_evaluation, processing_times, data_container)
        
        return document
        
    except Exception as e:
        logger.error(f"Processing error in process_blob: {str(e)}")
        document['errors'].append(f"Processing error: {str(e)}")
        document['state']['processing_completed'] = False
        
        # Mark any incomplete steps as failed for proper state tracking
        # Only mark OCR as failed if it was supposed to run
        if processing_options.get('include_ocr', True) and 'ocr_processing_time' not in processing_times:
            update_state(document, data_container, 'ocr_completed', False)
        if 'gpt_extraction_time' not in processing_times:
            update_state(document, data_container, 'gpt_extraction_completed', False)
        # Only mark evaluation as failed if it was supposed to run
        if processing_options.get('enable_evaluation', True) and 'gpt_evaluation_time' not in processing_times:
            update_state(document, data_container, 'gpt_evaluation_completed', False)
        # Only mark summary as failed if it was supposed to run  
        if processing_options.get('enable_summary', True) and summary_time == 0:
            update_state(document, data_container, 'gpt_summary_completed', False)
        
        data_container.upsert_item(document)
        raise e
    finally:
        # Clean up temporary directories and files
        cleanup_temp_resources(temp_dirs, file_paths, temp_file_path)

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

@app.post("/api/configuration/refresh")
async def refresh_configuration():
    """Force refresh configuration by reloading demo datasets"""
    try:
        if not conf_container:
            raise HTTPException(status_code=503, detail="Configuration container not available")
        
        logger.info("Forcing configuration refresh from demo files")
        
        # Force reload configuration by calling fetch function
        # This will trigger the configuration loading logic in process.py
        from ai_ocr.process import fetch_model_prompt_and_schema
        
        try:
            # This will force reload the configuration from demo files
            prompt, schema, max_pages, options = fetch_model_prompt_and_schema("default-dataset", force_refresh=True)
            logger.info(f"Configuration refreshed successfully - prompt length: {len(prompt)}, schema size: {len(str(schema))}")
            
            return {
                "status": "success", 
                "message": "Configuration refreshed successfully",
                "prompt_length": len(prompt),
                "schema_size": len(str(schema)),
                "schema_empty": not bool(schema)
            }
        except Exception as inner_e:
            logger.error(f"Error during configuration refresh: {inner_e}")
            return {
                "status": "error",
                "message": f"Failed to refresh configuration: {str(inner_e)}"
            }
        
    except Exception as e:
        logger.error(f"Error refreshing configuration: {e}")
        raise HTTPException(status_code=500, detail="Failed to refresh configuration")

# Logic App Concurrency Management Endpoints

@app.get("/api/concurrency")
async def get_concurrency_settings():
    """Get current Logic App concurrency settings"""
    try:
        if not logic_app_manager:
            raise HTTPException(status_code=503, detail="Logic App Manager not initialized")
        
        settings = await logic_app_manager.get_concurrency_settings()
        
        if "error" in settings:
            if not settings.get("enabled", False):
                raise HTTPException(status_code=503, detail=settings["error"])
            else:
                raise HTTPException(status_code=500, detail=settings["error"])
        
        return settings
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting concurrency settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to get concurrency settings")

@app.put("/api/concurrency")
async def update_concurrency_settings(request: Request):
    """Update Logic App concurrency settings"""
    global global_processing_semaphore
    
    try:
        if not logic_app_manager:
            raise HTTPException(status_code=503, detail="Logic App Manager not initialized")
        
        request_body = await request.json()
        max_runs = request_body.get('max_runs')
        
        if max_runs is None:
            raise HTTPException(status_code=400, detail="max_runs is required")
        
        if not isinstance(max_runs, int):
            raise HTTPException(status_code=400, detail="max_runs must be an integer")
        
        result = await logic_app_manager.update_concurrency_settings(max_runs)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error occurred")
            raise HTTPException(status_code=400, detail=error_msg)
        
        # Update the global semaphore to match the new concurrency setting
        global_processing_semaphore = asyncio.Semaphore(max_runs)
        logger.info(f"Updated global processing semaphore to allow {max_runs} concurrent operations")
        
        # Add semaphore info to the result
        result["backend_semaphore_updated"] = True
        result["backend_max_concurrent"] = max_runs
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating concurrency settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update concurrency settings")

@app.get("/api/workflow-definition")
async def get_workflow_definition():
    """Get the complete Logic App workflow definition for inspection"""
    try:
        if not logic_app_manager:
            raise HTTPException(status_code=503, detail="Logic App Manager not initialized")
        
        definition = await logic_app_manager.get_workflow_definition()
        
        if not definition.get("enabled", False):
            error_msg = definition.get("error", "Unknown error occurred")
            raise HTTPException(status_code=400, detail=error_msg)
        
        return definition
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting workflow definition: {e}")
        raise HTTPException(status_code=500, detail="Failed to get workflow definition")

@app.put("/api/concurrency-full")
async def update_full_concurrency_settings(request: Request):
    """Update Logic App concurrency settings for both triggers and actions"""
    try:
        if not logic_app_manager:
            raise HTTPException(status_code=503, detail="Logic App Manager not initialized")
        
        request_body = await request.json()
        max_runs = request_body.get('max_runs')
        
        if max_runs is None:
            raise HTTPException(status_code=400, detail="max_runs is required")
        
        if not isinstance(max_runs, int):
            raise HTTPException(status_code=400, detail="max_runs must be an integer")
        
        result = await logic_app_manager.update_action_concurrency_settings(max_runs)
        
        if not result.get("success", False):
            error_msg = result.get("error", "Unknown error occurred")
            raise HTTPException(status_code=400, detail=error_msg)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating full concurrency settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to update full concurrency settings")

@app.post("/api/process-file")
async def process_file(request: Request, background_tasks: BackgroundTasks):
    """Process file endpoint called by Logic App"""
    try:
        request_body = await request.json()
        logger.info(f"Received process-file request: {request_body}")
        
        # Extract parameters from Logic App request
        filename = request_body.get('filename')
        dataset = request_body.get('dataset')
        blob_path = request_body.get('blob_path')
        trigger_source = request_body.get('trigger_source', 'logic_app')
        
        if not all([filename, dataset, blob_path]):
            logger.error(f"Missing required parameters. filename: {filename}, dataset: {dataset}, blob_path: {blob_path}")
            raise HTTPException(status_code=400, detail="Missing required parameters: filename, dataset, blob_path")
        
        # Convert to blob URL format expected by our processing function
        # The blob_path should be in format: /datasets/dataset-name/filename
        # We need to construct the full blob URL
        storage_account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        if not storage_account_name:
            raise HTTPException(status_code=500, detail="Storage account name not configured")
        
        # Parse the blob_path to extract container and blob name
        # blob_path format: /datasets/dataset-name/filename.pdf
        path_parts = blob_path.strip('/').split('/', 1)  # Split into at most 2 parts
        if len(path_parts) != 2:
            raise HTTPException(status_code=400, detail="Invalid blob_path format. Expected: /container/blob-name")
        
        container_name, blob_name = path_parts
        blob_url = f"https://{storage_account_name}.blob.core.windows.net/{container_name}/{blob_name}"
        
        logger.info(f"Processing file: {filename} from dataset: {dataset}")
        logger.info(f"Blob path: {blob_path}")
        logger.info(f"Constructed blob URL: {blob_url}")
        
        # Add to background tasks using our existing processing function
        background_tasks.add_task(
            process_blob_event,
            blob_url,
            {
                "url": blob_url,
                "filename": filename,
                "dataset": dataset,
                "trigger_source": trigger_source
            }
        )
        
        return {
            "status": "accepted", 
            "message": f"File {filename} queued for processing",
            "filename": filename,
            "dataset": dataset,
            "blob_url": blob_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in process-file endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

# OpenAI Configuration Management Endpoints

@app.get("/api/openai-settings")
async def get_openai_settings():
    """Get current OpenAI configuration from environment variables (read-only)"""
    try:
        # Return current environment variable values (for display purposes only)
        return {
            "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "openai_key": "***HIDDEN***" if os.getenv("AZURE_OPENAI_KEY") else "",
            "deployment_name": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", ""),
            "note": "Configuration is read from environment variables only. Update via deployment/infrastructure."
        }
        
    except Exception as e:
        logger.error(f"Error fetching OpenAI settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch OpenAI settings")

@app.put("/api/openai-settings")
async def update_openai_settings(request: Request):
    """Update OpenAI settings by modifying environment variables"""
    try:
        data = await request.json()
        
        # Update environment variables
        if "openai_endpoint" in data:
            os.environ["AZURE_OPENAI_ENDPOINT"] = data["openai_endpoint"]
        if "openai_key" in data:
            os.environ["AZURE_OPENAI_KEY"] = data["openai_key"]
        if "openai_deployment_name" in data:
            os.environ["AZURE_OPENAI_MODEL_DEPLOYMENT_NAME"] = data["openai_deployment_name"]
        
        # Return success response with updated config (hide key)
        updated_config = {
            "openai_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            "openai_key": "***hidden***" if os.environ.get("AZURE_OPENAI_KEY") else "",
            "openai_deployment_name": os.environ.get("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", ""),
            "env_var_only": True
        }
        
        return {"message": "Environment variables updated successfully", "config": updated_config}
        
    except Exception as e:
        logger.error(f"Error updating OpenAI settings: {e}")
        raise HTTPException(status_code=400, detail=f"Error updating settings: {str(e)}")

def merge_evaluation_results(evaluation_results):
    """
    Specialized merge function for GPT evaluation results.
    Handles confidence scores, error messages, and image descriptions intelligently.
    """
    if not evaluation_results:
        return {}
    
    if len(evaluation_results) == 1:
        return evaluation_results[0]
    
    merged_result = {}
    all_errors = []
    
    # Collect all error messages
    for result in evaluation_results:
        if isinstance(result, dict) and "error" in result:
            all_errors.append(result["error"])
    
    # If we have errors, create a comprehensive error summary
    if all_errors:
        merged_result["error"] = "Multiple evaluation errors: " + " | ".join(all_errors)
        return merged_result
    
    # Process successful evaluation results
    for i, result in enumerate(evaluation_results):
        if not isinstance(result, dict):
            continue
            
        for key, value in result.items():
            if key == "original_data":
                # Special handling for original_data which contains image descriptions
                if key not in merged_result:
                    merged_result[key] = {}
                
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        if sub_key == "image_description":
                            # Collect all image descriptions
                            if sub_key not in merged_result[key]:
                                merged_result[key][sub_key] = []
                            if isinstance(sub_value, str) and sub_value.strip():
                                merged_result[key][sub_key].append(f"Chunk {i+1}: {sub_value}")
                        else:
                            # For other fields in original_data, use the merging logic
                            if sub_key not in merged_result[key]:
                                merged_result[key][sub_key] = sub_value
                            else:
                                merged_result[key][sub_key] = _merge_values_with_confidence(
                                    merged_result[key][sub_key], sub_value
                                )
                
            elif key == "content" or key == "image_description":
                # Handle content and top-level image descriptions with confidence aggregation
                if key not in merged_result:
                    merged_result[key] = value
                else:
                    merged_result[key] = _merge_values_with_confidence(merged_result[key], value)
            
            else:
                # For other keys, use standard merging
                if key not in merged_result:
                    merged_result[key] = copy.deepcopy(value)
                else:
                    merged_result[key] = _deep_merge_data(merged_result[key], value)
    
    # Post-process image descriptions to create a comprehensive summary
    if "original_data" in merged_result and "image_description" in merged_result["original_data"]:
        if isinstance(merged_result["original_data"]["image_description"], list):
            # Join all chunk descriptions into a comprehensive description
            merged_result["original_data"]["image_description"] = " ".join(
                merged_result["original_data"]["image_description"]
            )
    
    return merged_result


def _merge_values_with_confidence(existing_value, new_value):
    """
    Merge values that may contain confidence scores.
    Prefers higher confidence values or combines information intelligently.
    """
    # If either value is not a dict, fall back to simple merging
    if not isinstance(existing_value, dict) or not isinstance(new_value, dict):
        if isinstance(existing_value, str) and isinstance(new_value, str):
            return f"{existing_value} {new_value}".strip()
        return new_value if new_value else existing_value
    
    result = copy.deepcopy(existing_value)
    
    for key, value in new_value.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        elif key == "confidence":
            # For confidence scores, take the average or use the higher value
            if isinstance(result[key], (int, float)) and isinstance(value, (int, float)):
                # Use weighted average, giving slight preference to higher confidence
                result[key] = max(result[key], value)
        elif key == "value":
            # For value fields, combine intelligently
            if isinstance(result[key], str) and isinstance(value, str):
                if result[key] != value:
                    # If values are different, combine them
                    result[key] = f"{result[key]} {value}".strip()
                    result[key] = " ".join(result[key].split())  # Clean up spaces
        else:
            # Recursively merge other nested objects
            if isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = _merge_values_with_confidence(result[key], value)
            else:
                result[key] = value
    
    return result

@app.post("/api/chat")
async def chat_with_document(request: Request):
    """
    Chat endpoint for asking questions about a specific document.
    Uses the GPT extraction as context for answering questions.
    """
    try:
        data = await request.json()
        document_id = data.get("document_id")
        message = data.get("message", "").strip()
        chat_history = data.get("chat_history", [])
        
        if not document_id or not message:
            raise HTTPException(status_code=400, detail="document_id and message are required")
        
        # Get the document from Cosmos DB
        cosmos_container, cosmos_config_container = connect_to_cosmos()
        if not cosmos_container:
            raise HTTPException(status_code=500, detail="Unable to connect to Cosmos DB")
        
        try:
            # Fetch the document using a query (similar to frontend approach)
            query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
            items = list(cosmos_container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                raise HTTPException(status_code=404, detail="Document not found")
            
            document = items[0]
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error fetching document {document_id}: {e}")
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Extract GPT extraction data to use as context
        extracted_data = document.get('extracted_data', {})
        gpt_extraction = extracted_data.get('gpt_extraction_output')
        ocr_data = extracted_data.get('ocr_output', '')
        
        if not gpt_extraction and not ocr_data:
            raise HTTPException(status_code=400, detail="No extracted data available for this document")
        
        # Prepare context for the chat
        context_parts = []
        
        if gpt_extraction:
            if isinstance(gpt_extraction, dict):
                context_parts.append("GPT EXTRACTED DATA:")
                context_parts.append(json.dumps(gpt_extraction, indent=2))
            else:
                context_parts.append("GPT EXTRACTED DATA:")
                context_parts.append(str(gpt_extraction))
        
        if ocr_data and len(context_parts) == 0:
            # Only include OCR if no GPT extraction available
            context_parts.append("DOCUMENT TEXT (OCR):")
            # Limit OCR data to prevent token overflow
            ocr_snippet = ocr_data[:3000] + "..." if len(ocr_data) > 3000 else ocr_data
            context_parts.append(ocr_snippet)
        
        document_context = "\n\n".join(context_parts)
        
        # Build chat history for context
        conversation_context = ""
        if chat_history:
            conversation_context = "\n\nPREVIOUS CONVERSATION:\n"
            for i, chat_item in enumerate(chat_history[-5:]):  # Last 5 messages only
                role = chat_item.get('role', 'user')
                content = chat_item.get('content', '')
                conversation_context += f"{role.upper()}: {content}\n"
        
        # Create the system prompt
        system_prompt = f"""You are an AI assistant helping users understand and analyze document content. 
        
The user has uploaded a document that has been processed and analyzed. You have access to the extracted data from this document.

Your role is to:
- Answer questions about the document content accurately
- Help users understand specific details from the document
- Provide insights based on the extracted information
- Be concise but thorough in your responses
- If information is not available in the extracted data, clearly state that

DOCUMENT CONTEXT:
{document_context}
{conversation_context}

Please answer the user's question based on this document context."""

        # Get Azure OpenAI configuration
        _, cosmos_config_container = connect_to_cosmos()
        config = get_config(cosmos_config_container)
        
        # Initialize OpenAI client
        client = AzureOpenAI(
            api_key=config["openai_api_key"],
            api_version=config["openai_api_version"],
            azure_endpoint=config["openai_api_endpoint"]
        )
        
        # Prepare messages for the chat
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message}
        ]
        
        # Make the API call
        response = client.chat.completions.create(
            model=config["openai_model_deployment"],
            messages=messages,
            max_tokens=1000,
            temperature=0.3,
            top_p=0.9
        )
        
        # Extract the response
        assistant_message = response.choices[0].message.content
        
        # Check for truncation
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            assistant_message += "\n\n[Note: Response was truncated due to length limits. Please ask for more specific details if needed.]"
        
        return {
            "response": assistant_message,
            "finish_reason": finish_reason,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Chat processing failed: {str(e)}")

def create_page_range_structure(data_list, file_paths, max_pages_per_chunk):
    """
    Create a structured JSON with page ranges instead of merging chunks.
    
    Args:
        data_list: List of extracted data from each chunk
        file_paths: List of file paths for each chunk
        max_pages_per_chunk: Maximum pages per chunk setting
    
    Returns:
        Dict with page range keys like {"pages_1-10": {chunk_data}, "pages_11-20": {chunk_data}, ...}
    """
    if not data_list:
        return {}
    
    # If there's only one chunk, return it with a single page range
    if len(data_list) == 1:
        return {"pages_1-all": data_list[0]}
    
    # Multiple chunks - create page range structure
    structured_data = {}
    
    for i, (data, file_path) in enumerate(zip(data_list, file_paths)):
        # Parse page range from file_path if it contains subset information
        if "_subset_" in file_path:
            # Format: originalfile_subset_0_9.pdf -> pages_1-10
            parts = file_path.split("_subset_")
            if len(parts) == 2:
                page_part = parts[1].replace(".pdf", "")
                start_end = page_part.split("_")
                if len(start_end) == 2:
                    try:
                        start_page = int(start_end[0]) + 1  # Convert to 1-indexed
                        end_page = int(start_end[1]) + 1    # Convert to 1-indexed
                        page_key = f"pages_{start_page}-{end_page}"
                        structured_data[page_key] = data
                        continue
                    except ValueError:
                        pass
        
        # Fallback: calculate page range from chunk index and max_pages_per_chunk
        chunk_start = i * max_pages_per_chunk + 1
        chunk_end = (i + 1) * max_pages_per_chunk
        page_key = f"pages_{chunk_start}-{chunk_end}"
        structured_data[page_key] = data
    
    return structured_data

def create_page_range_evaluations(evaluation_list, file_paths, max_pages_per_chunk):
    """
    Create a structured JSON with page ranges for evaluations similar to extraction data.
    Uses the same logic as create_page_range_structure but for evaluation data.
    
    Returns:
        Dict with page range keys like {"pages_1-10": {evaluation_data}, ...}
    """
    # Use the same logic as create_page_range_structure
    return create_page_range_structure(evaluation_list, file_paths, max_pages_per_chunk)
