#!/usr/bin/env python3

import requests
import json
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_backend_debug():
    """Test the backend to understand the GPT extraction issue"""
    
    # Get the backend URL from environment or use default
    backend_url = os.getenv('BACKEND_URL', 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io')
    
    # Test 1: Check backend health
    try:
        health_response = requests.get(f"{backend_url}/health", timeout=10)
        logger.info(f"Backend health status: {health_response.status_code}")
        if health_response.status_code == 200:
            logger.info(f"Backend health response: {health_response.json()}")
    except Exception as e:
        logger.error(f"Backend health check failed: {e}")
        return
    
    # Test 2: Get configuration
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        logger.info(f"Configuration status: {config_response.status_code}")
        if config_response.status_code == 200:
            config_data = config_response.json()
            logger.info(f"Available datasets: {list(config_data.get('datasets', {}).keys())}")
            
            # Check default dataset configuration
            default_config = config_data.get('datasets', {}).get('default-dataset', {})
            logger.info(f"Default dataset config keys: {list(default_config.keys())}")
            
            if 'processing_options' in default_config:
                processing_options = default_config['processing_options']
                logger.info(f"Processing options: {processing_options}")
            else:
                logger.warning("No processing_options found in default dataset config")
            
            # Check the model prompt and schema
            model_prompt = default_config.get('model_prompt', '')
            example_schema = default_config.get('example_schema', {})
            
            logger.info(f"Model prompt length: {len(model_prompt)} characters")
            logger.info(f"Model prompt preview: {model_prompt[:200]}...")
            logger.info(f"Example schema: {example_schema}")
            logger.info(f"Schema is empty: {not bool(example_schema)}")
            
    except Exception as e:
        logger.error(f"Configuration check failed: {e}")
    
    # Test 3: Check processing options endpoint
    try:
        options_response = requests.get(f"{backend_url}/api/processing-options/default-dataset", timeout=10)
        logger.info(f"Processing options status: {options_response.status_code}")
        if options_response.status_code == 200:
            options_data = options_response.json()
            logger.info(f"Processing options response: {options_data}")
        else:
            logger.error(f"Processing options response: {options_response.text}")
    except Exception as e:
        logger.error(f"Processing options check failed: {e}")

if __name__ == "__main__":
    test_backend_debug()
