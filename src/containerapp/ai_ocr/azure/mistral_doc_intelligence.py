"""
Mistral Document AI integration for OCR processing.
Provides an alternative to Azure Document Intelligence using Mistral's Document AI API.
"""
import base64
import json
import logging
import httpx
from typing import Optional
from ai_ocr.azure.config import get_config

logger = logging.getLogger(__name__)


def encode_file_to_base64(file_path: str) -> tuple[str, str]:
    """
    Encode a file to base64 string and determine its type.
    
    Args:
        file_path: Path to the file to encode
        
    Returns:
        Tuple of (base64_string, file_type) where file_type is 'document_url' or 'image_url'
    """
    with open(file_path, "rb") as f:
        file_bytes = f.read()
        base64_encoded = base64.b64encode(file_bytes).decode('utf-8')
    
    # Determine file type and construct data URL
    if file_path.lower().endswith('.pdf'):
        data_url = f"data:application/pdf;base64,{base64_encoded}"
        url_type = "document_url"
    elif file_path.lower().endswith(('.jpg', '.jpeg')):
        data_url = f"data:image/jpeg;base64,{base64_encoded}"
        url_type = "image_url"
    elif file_path.lower().endswith('.png'):
        data_url = f"data:image/png;base64,{base64_encoded}"
        url_type = "image_url"
    else:
        # Default to document
        data_url = f"data:application/pdf;base64,{base64_encoded}"
        url_type = "document_url"
    
    return data_url, url_type


def get_mistral_doc_ai_client(cosmos_config_container=None):
    """
    Get Mistral Document AI configuration from environment.
    
    Args:
        cosmos_config_container: Optional Cosmos config container (kept for compatibility)
        
    Returns:
        Dictionary with endpoint, API key, and model name
    """
    config = get_config(cosmos_config_container)
    
    mistral_endpoint = config.get("mistral_doc_ai_endpoint")
    mistral_api_key = config.get("mistral_doc_ai_key")
    mistral_model = config.get("mistral_doc_ai_model", "mistral-document-ai-2505")
    
    if not mistral_endpoint or not mistral_api_key:
        raise ValueError(
            "Mistral Document AI endpoint and key must be configured. "
            "Set MISTRAL_DOC_AI_ENDPOINT and MISTRAL_DOC_AI_KEY environment variables."
        )
    
    return {
        "endpoint": mistral_endpoint,
        "api_key": mistral_api_key,
        "model": mistral_model
    }


def get_ocr_results(file_path: str, cosmos_config_container=None, json_schema: Optional[dict] = None) -> str:
    """
    Extract text from document using Mistral Document AI.
    
    This function provides the same interface as Azure Document Intelligence
    to allow seamless switching between OCR providers.
    
    Args:
        file_path: Path to the file to process
        cosmos_config_container: Optional Cosmos config container (kept for compatibility)
        json_schema: Optional JSON schema for structured extraction with bbox annotation
        
    Returns:
        Extracted text content from the document
    """
    import threading
    thread_id = threading.current_thread().ident
    
    logger.info(f"[Thread-{thread_id}] Starting Mistral Document AI OCR for: {file_path}")
    
    # Get Mistral configuration
    mistral_config = get_mistral_doc_ai_client(cosmos_config_container)
    endpoint = mistral_config["endpoint"]
    api_key = mistral_config["api_key"]
    model_name = mistral_config["model"]
    
    # Encode file to base64
    logger.info(f"[Thread-{thread_id}] Encoding file to base64")
    data_url, url_type = encode_file_to_base64(file_path)
    
    # Prepare request payload
    payload = {
        "model": model_name,
        "document": {
            "type": url_type,
            url_type: data_url
        },
        "include_image_base64": False  # We don't need images back, just text
    }
    
    # If JSON schema is provided, add bbox annotation format for structured extraction
    if json_schema:
        logger.info(f"[Thread-{thread_id}] Adding bbox annotation format with schema")
        payload["bbox_annotation_format"] = {
            "type": "json_schema",
            "json_schema": {
                "schema": json_schema,
                "name": "document_annotation",
                "strict": True
            }
        }
    
    # Make request to Mistral API
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    logger.info(f"[Thread-{thread_id}] Submitting document to Mistral Document AI API")
    
    try:
        with httpx.Client(timeout=300.0) as client:  # 5 minute timeout for large documents
            response = client.post(endpoint, json=payload, headers=headers)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"[Thread-{thread_id}] Mistral Document AI response received")
            
            # Extract markdown content from response
            # Mistral Document AI returns pages with markdown content
            ocr_text = ""
            
            if "pages" in result and isinstance(result["pages"], list):
                # Concatenate markdown from all pages
                markdown_parts = []
                for page in result["pages"]:
                    if isinstance(page, dict) and "markdown" in page:
                        markdown_parts.append(page["markdown"])
                ocr_text = "\n\n".join(markdown_parts)
                logger.info(f"[Thread-{thread_id}] Extracted markdown from {len(result['pages'])} page(s)")
            elif "content" in result:
                ocr_text = result["content"]
            elif "text" in result:
                ocr_text = result["text"]
            elif "choices" in result and len(result["choices"]) > 0:
                # OpenAI-style response format
                ocr_text = result["choices"][0].get("message", {}).get("content", "")
            else:
                # Fallback: log warning
                logger.warning(f"[Thread-{thread_id}] Unexpected response format, no markdown content found")
                ocr_text = ""
            
            logger.info(f"[Thread-{thread_id}] Mistral Document AI OCR completed, {len(ocr_text)} characters")
            return ocr_text
            
    except httpx.HTTPStatusError as e:
        logger.error(f"[Thread-{thread_id}] Mistral API HTTP error: {e.response.status_code}")
        logger.error(f"[Thread-{thread_id}] Response: {e.response.text}")
        raise Exception(f"Mistral Document AI API error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        logger.error(f"[Thread-{thread_id}] Mistral API request error: {str(e)}")
        raise Exception(f"Mistral Document AI request failed: {str(e)}")
    except Exception as e:
        logger.error(f"[Thread-{thread_id}] Unexpected error during Mistral Document AI processing: {str(e)}")
        raise
