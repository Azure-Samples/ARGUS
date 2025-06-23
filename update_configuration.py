#!/usr/bin/env python3

import requests
import json
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_configuration():
    """Update the configuration in Cosmos DB"""
    
    backend_url = 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io'
    
    # First, get the current configuration
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        if config_response.status_code == 200:
            current_config = config_response.json()
            logger.info("Got current configuration")
        else:
            logger.error(f"Failed to get current configuration: {config_response.status_code}")
            return
    except Exception as e:
        logger.error(f"Failed to get current configuration: {e}")
        return
    
    # Read the system prompt
    with open('src/containerapp/example-datasets/default-dataset/system_prompt.txt', 'r') as f:
        system_prompt = f.read().strip()
    
    # Read the output schema
    with open('src/containerapp/example-datasets/default-dataset/output_schema.json', 'r') as f:
        output_schema = json.load(f)
    
    logger.info(f"System prompt length: {len(system_prompt)} characters")
    logger.info(f"Output schema keys: {list(output_schema.keys())}")
    
    # Update the default-dataset configuration
    if 'datasets' not in current_config:
        current_config['datasets'] = {}
    
    current_config['datasets']['default-dataset'] = {
        "model_prompt": system_prompt,
        "example_schema": output_schema,
        "max_pages_per_chunk": 10,
        "processing_options": {
            "include_ocr": True,
            "include_images": True,
            "enable_summary": True,
            "enable_evaluation": True
        }
    }
    
    # Ensure the configuration has required fields
    current_config["id"] = "configuration"
    current_config["partitionKey"] = "configuration"
    
    # Send the updated configuration
    try:
        response = requests.post(
            f"{backend_url}/api/configuration",
            json=current_config,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        logger.info(f"Update response status: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("Configuration updated successfully!")
            logger.info(f"Response: {response.json()}")
        else:
            logger.error(f"Update failed: {response.text}")
                
    except Exception as e:
        logger.error(f"Update failed with exception: {e}")
    
    # Verify the update by checking the configuration again
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        if config_response.status_code == 200:
            config_data = config_response.json()
            default_config = config_data.get('datasets', {}).get('default-dataset', {})
            
            logger.info("Verification - Updated configuration:")
            logger.info(f"  Model prompt length: {len(default_config.get('model_prompt', ''))} characters")
            logger.info(f"  Schema keys: {list(default_config.get('example_schema', {}).keys())}")
            logger.info(f"  Processing options: {default_config.get('processing_options', {})}")
            
    except Exception as e:
        logger.error(f"Verification failed: {e}")

if __name__ == "__main__":
    update_configuration()
