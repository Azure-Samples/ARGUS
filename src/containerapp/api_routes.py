"""
API route handlers for ARGUS Container App
"""
import asyncio
import copy
import json
import logging
import os
import traceback
from datetime import datetime
from typing import Dict, Any

from fastapi import Request, BackgroundTasks, HTTPException
from azure.identity import DefaultAzureCredential
from openai import AzureOpenAI

from models import EventGridEvent
from blob_processing import process_blob_event
from dependencies import (
    get_blob_service_client, get_data_container, get_conf_container,
    get_logic_app_manager, set_global_processing_semaphore
)

# Import processing functions
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functionapp'))
from ai_ocr.process import connect_to_cosmos, fetch_model_prompt_and_schema
from ai_ocr.azure.config import get_config

logger = logging.getLogger(__name__)


async def root():
    """Health check endpoint"""
    return {"status": "healthy", "service": "ARGUS Backend"}


async def health_check():
    """Detailed health check"""
    try:
        blob_service_client = get_blob_service_client()
        data_container = get_data_container()
        conf_container = get_conf_container()
        
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


async def get_configuration():
    """Get current configuration from Cosmos DB"""
    try:
        conf_container = get_conf_container()
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


async def update_configuration(request: Request):
    """Update configuration in Cosmos DB"""
    try:
        conf_container = get_conf_container()
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


async def refresh_configuration():
    """Force refresh configuration by reloading demo datasets"""
    try:
        conf_container = get_conf_container()
        if not conf_container:
            raise HTTPException(status_code=503, detail="Configuration container not available")
        
        logger.info("Forcing configuration refresh from demo files")
        
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


async def get_concurrency_settings():
    """Get current Logic App concurrency settings"""
    try:
        logic_app_manager = get_logic_app_manager()
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


async def update_concurrency_settings(request: Request):
    """Update Logic App concurrency settings"""
    try:
        logic_app_manager = get_logic_app_manager()
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
        set_global_processing_semaphore(global_processing_semaphore)
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


async def get_workflow_definition():
    """Get the complete Logic App workflow definition for inspection"""
    try:
        logic_app_manager = get_logic_app_manager()
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


async def update_full_concurrency_settings(request: Request):
    """Update Logic App concurrency settings for both triggers and actions"""
    try:
        logic_app_manager = get_logic_app_manager()
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
        storage_account_name = os.getenv('AZURE_STORAGE_ACCOUNT_NAME')
        if not storage_account_name:
            raise HTTPException(status_code=500, detail="Storage account name not configured")
        
        # Parse the blob_path to extract container and blob name
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


async def get_openai_settings():
    """Get current OpenAI configuration from environment variables (read-only)"""
    try:
        # Return current environment variable values (for display purposes only)
        return {
            "openai_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            "openai_key": "***HIDDEN***" if os.getenv("AZURE_OPENAI_KEY") else "",
            "deployment_name": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", ""),
            "ocr_provider": os.getenv("OCR_PROVIDER", "azure"),
            "mistral_endpoint": os.getenv("MISTRAL_DOC_AI_ENDPOINT", ""),
            "mistral_key": "***HIDDEN***" if os.getenv("MISTRAL_DOC_AI_KEY") else "",
            "mistral_model": os.getenv("MISTRAL_DOC_AI_MODEL", "mistral-document-ai-2505"),
            "note": "Configuration is read from environment variables only. Update via deployment/infrastructure."
        }
        
    except Exception as e:
        logger.error(f"Error fetching OpenAI settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch OpenAI settings")


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
        if "ocr_provider" in data:
            os.environ["OCR_PROVIDER"] = data["ocr_provider"]
        if "mistral_endpoint" in data:
            os.environ["MISTRAL_DOC_AI_ENDPOINT"] = data["mistral_endpoint"]
        if "mistral_key" in data:
            os.environ["MISTRAL_DOC_AI_KEY"] = data["mistral_key"]
        if "mistral_model" in data:
            os.environ["MISTRAL_DOC_AI_MODEL"] = data["mistral_model"]
        
        # Return success response with updated config (hide keys)
        updated_config = {
            "openai_endpoint": os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            "openai_key": "***hidden***" if os.environ.get("AZURE_OPENAI_KEY") else "",
            "openai_deployment_name": os.environ.get("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", ""),
            "ocr_provider": os.environ.get("OCR_PROVIDER", "azure"),
            "mistral_endpoint": os.environ.get("MISTRAL_DOC_AI_ENDPOINT", ""),
            "mistral_key": "***hidden***" if os.environ.get("MISTRAL_DOC_AI_KEY") else "",
            "mistral_model": os.environ.get("MISTRAL_DOC_AI_MODEL", "mistral-document-ai-2505"),
            "env_var_only": True
        }
        
        return {"message": "Environment variables updated successfully", "config": updated_config}
        
    except Exception as e:
        logger.error(f"Error updating OpenAI settings: {e}")
        raise HTTPException(status_code=400, detail=f"Error updating settings: {str(e)}")


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


async def submit_correction(document_id: str, request: Request):
    """
    Submit a human correction for a document's extraction.
    Stores the correction alongside the original extraction for audit trail.
    """
    try:
        data = await request.json()
        corrected_data = data.get("corrected_data")
        correction_notes = data.get("notes", "")
        corrector_id = data.get("corrector_id", "anonymous")
        
        if corrected_data is None:
            raise HTTPException(status_code=400, detail="corrected_data is required")
        
        # Get the document from Cosmos DB
        data_container = get_data_container()
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        try:
            # Fetch the document using a query
            query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
            items = list(data_container.query_items(
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
        
        # Get the original GPT extraction
        extracted_data = document.get('extracted_data', {})
        original_extraction = extracted_data.get('gpt_extraction_output')
        
        # Initialize corrections history if not present
        if 'corrections' not in document:
            document['corrections'] = []
        
        # Create correction record
        correction_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "corrector_id": corrector_id,
            "notes": correction_notes,
            "original_data": copy.deepcopy(original_extraction) if original_extraction else None,
            "corrected_data": corrected_data,
            "correction_number": len(document['corrections']) + 1
        }
        
        # Append to corrections history
        document['corrections'].append(correction_record)
        
        # Update the current extraction with the corrected data
        if 'extracted_data' not in document:
            document['extracted_data'] = {}
        document['extracted_data']['gpt_extraction_output'] = corrected_data
        
        # Mark that this document has been human-corrected
        document['human_corrected'] = True
        document['last_correction_timestamp'] = datetime.utcnow().isoformat()
        
        # Upsert the document back to Cosmos DB
        data_container.upsert_item(document)
        
        logger.info(f"Correction submitted for document {document_id} by {corrector_id}")
        
        return {
            "status": "success",
            "message": "Correction submitted successfully",
            "document_id": document_id,
            "correction_number": correction_record["correction_number"],
            "timestamp": correction_record["timestamp"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error submitting correction for document {document_id}: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Failed to submit correction: {str(e)}")


async def get_correction_history(document_id: str):
    """
    Get the correction history for a document.
    Returns all corrections made to the document along with the original extraction.
    """
    try:
        # Get the document from Cosmos DB
        data_container = get_data_container()
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        try:
            # Fetch the document using a query
            query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
            items = list(data_container.query_items(
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
        
        # Get current extraction and corrections
        extracted_data = document.get('extracted_data', {})
        current_extraction = extracted_data.get('gpt_extraction_output')
        corrections = document.get('corrections', [])
        
        return {
            "document_id": document_id,
            "human_corrected": document.get('human_corrected', False),
            "last_correction_timestamp": document.get('last_correction_timestamp'),
            "current_extraction": current_extraction,
            "corrections_count": len(corrections),
            "corrections": corrections
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting correction history for document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get correction history: {str(e)}")


async def get_concurrency_diagnostics():
    """Get diagnostic information about Logic App Manager setup"""
    try:
        logic_app_manager = get_logic_app_manager()
        
        diagnostics = {
            "timestamp": datetime.utcnow().isoformat(),
            "logic_app_manager_initialized": logic_app_manager is not None,
            "environment_variables": {
                "AZURE_SUBSCRIPTION_ID": bool(os.getenv('AZURE_SUBSCRIPTION_ID')),
                "AZURE_RESOURCE_GROUP_NAME": bool(os.getenv('AZURE_RESOURCE_GROUP_NAME')),
                "LOGIC_APP_NAME": bool(os.getenv('LOGIC_APP_NAME'))
            },
            "environment_values": {
                "AZURE_SUBSCRIPTION_ID": os.getenv('AZURE_SUBSCRIPTION_ID', 'NOT_SET')[:8] + "..." if os.getenv('AZURE_SUBSCRIPTION_ID') else 'NOT_SET',
                "AZURE_RESOURCE_GROUP_NAME": os.getenv('AZURE_RESOURCE_GROUP_NAME', 'NOT_SET'),
                "LOGIC_APP_NAME": os.getenv('LOGIC_APP_NAME', 'NOT_SET')
            }
        }
        
        if logic_app_manager:
            diagnostics["logic_app_manager_enabled"] = logic_app_manager.enabled
            diagnostics["subscription_id_configured"] = bool(logic_app_manager.subscription_id)
            diagnostics["resource_group_configured"] = bool(logic_app_manager.resource_group_name)
            diagnostics["logic_app_name_configured"] = bool(logic_app_manager.logic_app_name)
            
            # Try to test Azure credentials
            try:
                diagnostics["azure_credentials_test"] = "Testing..."
                # Simple credential test
                credential_test = DefaultAzureCredential()
                # This will fail if credentials are not working, but won't actually call Azure
                diagnostics["azure_credentials_available"] = True
            except Exception as e:
                diagnostics["azure_credentials_test"] = f"Failed: {str(e)}"
                diagnostics["azure_credentials_available"] = False
        else:
            diagnostics["logic_app_manager_enabled"] = False
            diagnostics["reason"] = "LogicAppManager not initialized"
            
        return diagnostics
        
    except Exception as e:
        logger.error(f"Error getting concurrency diagnostics: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
            "logic_app_manager_initialized": False
        }
