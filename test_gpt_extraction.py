#!/usr/bin/env python3

import requests
import json
import os
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_document_processing():
    """Test document processing to verify GPT extraction works"""
    
    backend_url = 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io'
    
    # Check if sample document exists
    sample_doc = 'sample-invoice.pdf'
    if not os.path.exists(sample_doc):
        logger.error(f"Sample document {sample_doc} not found")
        return
    
    logger.info(f"Testing document processing with {sample_doc}")
    
    # Upload the document for processing
    try:
        with open(sample_doc, 'rb') as f:
            files = {'file': (sample_doc, f, 'application/pdf')}
            data = {
                'dataset': 'default-dataset',
                'processing_options': json.dumps({
                    "include_ocr": True,
                    "include_images": True,
                    "enable_summary": True,
                    "enable_evaluation": True
                })
            }
            
            logger.info("Uploading document for processing...")
            response = requests.post(
                f"{backend_url}/api/process-file",
                files=files,
                data=data,
                timeout=60
            )
            
            logger.info(f"Upload response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.info("Document processing initiated successfully!")
                logger.info(f"Document ID: {result.get('document_id', 'N/A')}")
                
                # Extract useful information for monitoring
                document_id = result.get('document_id')
                
                # Check the processing status
                if document_id:
                    logger.info(f"Monitoring processing for document: {document_id}")
                    
                    # Note: In a real scenario, you'd need to poll for completion or check cosmos DB
                    # For now, let's just show that the upload was successful
                    logger.info("Processing has started. Check the backend logs or Cosmos DB for results.")
                    
                return result
            else:
                logger.error(f"Upload failed: {response.text}")
                return None
                
    except Exception as e:
        logger.error(f"Test failed with exception: {e}")
        return None

def check_recent_documents():
    """Check if there are any recent documents in the system"""
    # This would require access to Cosmos DB, which we don't have directly
    # But we can check if the backend has any endpoints for this
    
    backend_url = 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io'
    
    # Try to get some status information
    try:
        health_response = requests.get(f"{backend_url}/health", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            logger.info(f"Backend status: {health_data}")
    except Exception as e:
        logger.error(f"Health check failed: {e}")

if __name__ == "__main__":
    # First check the configuration is correct
    logger.info("Verifying configuration...")
    
    backend_url = 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io'
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        if config_response.status_code == 200:
            config_data = config_response.json()
            default_config = config_data.get('datasets', {}).get('default-dataset', {})
            
            prompt_length = len(default_config.get('model_prompt', ''))
            schema_keys = list(default_config.get('example_schema', {}).keys())
            processing_options = default_config.get('processing_options', {})
            
            logger.info(f"✅ Model prompt: {prompt_length} characters")
            logger.info(f"✅ Schema fields: {len(schema_keys)} ({', '.join(schema_keys[:5])}{'...' if len(schema_keys) > 5 else ''})")
            logger.info(f"✅ Processing options: OCR={processing_options.get('include_ocr')}, Images={processing_options.get('include_images')}")
            
            if prompt_length > 500 and len(schema_keys) > 5:
                logger.info("Configuration looks good! Proceeding with test...")
                test_document_processing()
            else:
                logger.error("Configuration still has issues!")
        else:
            logger.error(f"Failed to get configuration: {config_response.status_code}")
    except Exception as e:
        logger.error(f"Configuration check failed: {e}")
