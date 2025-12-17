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
            messages=messages
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


# ============================================================================
# Document Management Endpoints
# ============================================================================

async def list_documents(dataset: str = None):
    """List all documents, optionally filtered by dataset"""
    try:
        data_container = get_data_container()
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        if dataset:
            query = f"SELECT * FROM c WHERE c.dataset = '{dataset}'"
        else:
            query = "SELECT * FROM c"
        
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        # Transform documents to expected format
        documents = []
        for item in items:
            doc = {
                "id": item.get("id"),
                "filename": item.get("file_name") or item.get("filename") or item.get("id", "").split("/")[-1],
                "dataset": item.get("dataset", "default-dataset"),
                "status": _get_document_status(item),
                "created_at": item.get("request_timestamp") or item.get("created_at"),
                "updated_at": item.get("updated_at") or item.get("request_timestamp"),
                "processing_time": item.get("processing_time") or item.get("processing_times", {}).get("total"),
                "model": item.get("model"),
                "ocr_text": item.get("ocr_response") or item.get("ocr_text"),
                "gpt_extraction": item.get("extracted_data", {}).get("gpt_extraction_output"),
                "evaluation": item.get("evaluation_results") or item.get("evaluation"),
                "summary": item.get("summary"),
                "errors": item.get("errors"),
                "num_pages": item.get("num_pages"),
                "properties": item.get("properties", {}),
                "state": item.get("state", {}),
                "extracted_data": item.get("extracted_data", {})
            }
            documents.append(doc)
        
        return {"documents": documents, "count": len(documents)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


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


async def get_document(document_id: str):
    """Get a specific document by ID"""
    try:
        data_container = get_data_container()
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Query for the document
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            raise HTTPException(status_code=404, detail="Document not found")
        
        item = items[0]
        
        # Transform to expected format
        doc = {
            "id": item.get("id"),
            "filename": item.get("file_name") or item.get("filename") or item.get("id", "").split("/")[-1],
            "dataset": item.get("dataset", "default-dataset"),
            "status": _get_document_status(item),
            "created_at": item.get("request_timestamp") or item.get("created_at"),
            "updated_at": item.get("updated_at") or item.get("request_timestamp"),
            "processing_time": item.get("processing_time") or item.get("processing_times", {}).get("total"),
            "model": item.get("model"),
            "ocr_text": item.get("ocr_response") or item.get("ocr_text"),
            "gpt_extraction": item.get("extracted_data", {}).get("gpt_extraction_output"),
            "evaluation": item.get("evaluation_results") or item.get("evaluation"),
            "summary": item.get("summary"),
            "errors": item.get("errors"),
            "num_pages": item.get("num_pages"),
            "properties": item.get("properties", {}),
            "state": item.get("state", {}),
            "extracted_data": item.get("extracted_data", {}),
            "model_input": item.get("model_input", {}),
            "processing_options": item.get("processing_options", {}),
            "blob_url": item.get("blob_url"),
            "human_corrected": item.get("human_corrected", False),
            "corrections": item.get("corrections", [])
        }
        
        return doc
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document: {str(e)}")


async def delete_document(document_id: str):
    """Delete a document by ID"""
    try:
        data_container = get_data_container()
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # First find the document to get its info
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Delete the document using empty partition key (matches container config)
        data_container.delete_item(item=document_id, partition_key={})
        
        # Also try to delete from blob storage
        item = items[0]
        blob_name = item.get("properties", {}).get("blob_name") or item.get("file_name")
        if blob_name:
            try:
                blob_service_client = get_blob_service_client()
                if blob_service_client:
                    container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
                    container_client = blob_service_client.get_container_client(container_name)
                    blob_client = container_client.get_blob_client(blob_name)
                    if blob_client.exists():
                        blob_client.delete_blob()
                        logger.info(f"Deleted blob: {blob_name}")
            except Exception as blob_error:
                logger.warning(f"Could not delete blob {blob_name}: {blob_error}")
        
        return {"status": "success", "message": f"Document {document_id} deleted"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete document: {str(e)}")


async def reprocess_document(document_id: str, background_tasks: BackgroundTasks):
    """Reprocess a document by ID"""
    try:
        data_container = get_data_container()
        blob_service_client = get_blob_service_client()
        
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Find the document
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            raise HTTPException(status_code=404, detail="Document not found")
        
        item = items[0]
        
        # Get blob name from document properties
        blob_name = item.get("properties", {}).get("blob_name") or item.get("file_name")
        
        if not blob_name:
            raise HTTPException(status_code=400, detail="Document does not have a blob reference for reprocessing")
        
        # Construct the blob URL
        if blob_service_client:
            storage_account = os.getenv('STORAGE_ACCOUNT_NAME', '')
            container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
            blob_url = f"https://{storage_account}.blob.core.windows.net/{container_name}/{blob_name}"
        else:
            raise HTTPException(status_code=503, detail="Blob storage not available for reprocessing")
        
        # Reset document state
        item["state"] = {
            "file_landed": True,
            "ocr_completed": False,
            "gpt_extraction": False,
            "gpt_extraction_completed": False,
            "gpt_evaluation": False,
            "gpt_evaluation_completed": False,
            "gpt_summary": False,
            "gpt_summary_completed": False,
            "processing_completed": False,
            "finished": False,
            "error": False
        }
        item["errors"] = []
        data_container.upsert_item(item)
        
        # Queue for reprocessing
        background_tasks.add_task(
            process_blob_event,
            blob_url,
            {"url": blob_url}
        )
        
        return {"status": "success", "message": f"Document {document_id} queued for reprocessing"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reprocessing document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reprocess document: {str(e)}")


# ============================================================================
# Dataset Management Endpoints
# ============================================================================

async def list_datasets():
    """List all available datasets"""
    try:
        conf_container = get_conf_container()
        blob_service_client = get_blob_service_client()
        
        datasets = []
        
        # Get datasets from configuration
        if conf_container:
            try:
                config_item = conf_container.read_item(item='configuration', partition_key='configuration')
                config_datasets = config_item.get('datasets', {})
                for name, config in config_datasets.items():
                    datasets.append({
                        "name": name,
                        "has_system_prompt": bool(config.get('system_prompt')),
                        "has_output_schema": bool(config.get('output_schema')),
                        "has_ground_truth": bool(config.get('ground_truth')),
                        "description": config.get('description', '')
                    })
            except Exception as e:
                logger.warning(f"Could not read configuration: {e}")
        
        # Also check blob storage for dataset folders
        if blob_service_client:
            try:
                storage_account = os.getenv('STORAGE_ACCOUNT_NAME', '')
                container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
                container_client = blob_service_client.get_container_client(container_name)
                
                # List blobs to find dataset folders - the structure is {dataset-name}/{file.pdf}
                blob_list = container_client.list_blobs()
                seen_datasets = set()
                for blob in blob_list:
                    # Extract dataset name from path like "dataset-name/file.pdf"
                    parts = blob.name.split('/')
                    if len(parts) >= 2:
                        dataset_name = parts[0]
                        if dataset_name and dataset_name not in seen_datasets:
                            seen_datasets.add(dataset_name)
                            # Add if not already in list from config
                            if not any(d['name'] == dataset_name for d in datasets):
                                datasets.append({
                                    "name": dataset_name,
                                    "has_system_prompt": False,
                                    "has_output_schema": False,
                                    "has_ground_truth": False,
                                    "description": ""
                                })
            except Exception as e:
                logger.warning(f"Could not list blob datasets: {e}")
        
        # Add default dataset if no datasets found
        if not datasets:
            datasets.append({
                "name": "default-dataset",
                "has_system_prompt": False,
                "has_output_schema": False,
                "has_ground_truth": False,
                "description": "Default dataset"
            })
        
        return {"datasets": datasets}
        
    except Exception as e:
        logger.error(f"Error listing datasets: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list datasets: {str(e)}")


async def get_dataset_documents(dataset_name: str):
    """Get all documents for a specific dataset"""
    return await list_documents(dataset=dataset_name)


async def upload_file(dataset_name: str, request: Request, background_tasks: BackgroundTasks):
    """Upload a file to a dataset"""
    try:
        blob_service_client = get_blob_service_client()
        if not blob_service_client:
            raise HTTPException(status_code=503, detail="Blob storage not available")
        
        # Get form data
        form = await request.form()
        file = form.get('file')
        
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Get processing options from query params
        run_ocr = request.query_params.get('run_ocr', 'true').lower() == 'true'
        run_gpt_vision = request.query_params.get('run_gpt_vision', 'true').lower() == 'true'
        run_summary = request.query_params.get('run_summary', 'true').lower() == 'true'
        run_evaluation = request.query_params.get('run_evaluation', 'true').lower() == 'true'
        
        # Read file content
        content = await file.read()
        filename = file.filename
        
        # Upload to blob storage - use 'datasets' container which is the actual container name
        container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
        blob_path = f"{dataset_name}/{filename}"
        
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_path)
        
        blob_client.upload_blob(content, overwrite=True)
        
        # Get the blob URL
        blob_url = blob_client.url
        
        # Queue for processing if any processing options are enabled
        if run_ocr or run_gpt_vision or run_summary or run_evaluation:
            background_tasks.add_task(
                process_blob_event,
                blob_url,
                {
                    "url": blob_url,
                    "processing_options": {
                        "run_ocr": run_ocr,
                        "run_gpt_vision": run_gpt_vision,
                        "run_summary": run_summary,
                        "run_evaluation": run_evaluation
                    }
                }
            )
        
        return {"message": "File uploaded successfully", "filename": filename, "blob_url": blob_url}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload file: {str(e)}")


async def get_document_file(document_id: str):
    """Get the file/blob for a document to serve as preview"""
    from fastapi.responses import StreamingResponse
    import io
    
    try:
        data_container = get_data_container()
        blob_service_client = get_blob_service_client()
        
        if not data_container:
            raise HTTPException(status_code=503, detail="Data container not available")
        
        # Find the document
        query = f"SELECT * FROM c WHERE c.id = '{document_id}'"
        items = list(data_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        
        if not items:
            raise HTTPException(status_code=404, detail="Document not found")
        
        item = items[0]
        
        # Get blob name from document properties
        blob_name = item.get("properties", {}).get("blob_name") or item.get("file_name")
        
        if not blob_name:
            raise HTTPException(status_code=404, detail="Document does not have a blob reference")
        
        if not blob_service_client:
            raise HTTPException(status_code=503, detail="Blob storage not available")
        
        # Get the blob content - use 'datasets' container
        container_name = os.getenv('STORAGE_CONTAINER_NAME', 'datasets')
        container_client = blob_service_client.get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        
        if not blob_client.exists():
            raise HTTPException(status_code=404, detail="File not found in storage")
        
        # Download blob content
        blob_data = blob_client.download_blob().readall()
        
        # Determine content type
        filename = blob_name.split('/')[-1].lower()
        if filename.endswith('.pdf'):
            content_type = "application/pdf"
        elif filename.endswith('.png'):
            content_type = "image/png"
        elif filename.endswith(('.jpg', '.jpeg')):
            content_type = "image/jpeg"
        elif filename.endswith('.tiff'):
            content_type = "image/tiff"
        elif filename.endswith('.docx'):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.endswith('.xlsx'):
            content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        elif filename.endswith('.pptx'):
            content_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        else:
            content_type = "application/octet-stream"
        
        return StreamingResponse(
            io.BytesIO(blob_data),
            media_type=content_type,
            headers={
                "Content-Disposition": f"inline; filename=\"{filename}\"",
                "Cache-Control": "public, max-age=3600"
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting document file {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get document file: {str(e)}")
