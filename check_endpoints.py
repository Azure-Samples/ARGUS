#!/usr/bin/env python3

import requests
import json
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_backend_endpoints():
    """Check what endpoints are available on the backend"""
    
    backend_url = 'https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io'
    
    # Common endpoints to test
    endpoints = [
        '/health',
        '/docs',
        '/api/configuration',
        '/api/processing-options/default-dataset',
        '/api/docs',
        '/configuration',
        '/processing-options/default-dataset',
        '/openapi.json'
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{backend_url}{endpoint}", timeout=10)
            logger.info(f"Endpoint {endpoint}: Status {response.status_code}")
            if response.status_code == 200:
                content_type = response.headers.get('content-type', '')
                if 'application/json' in content_type:
                    try:
                        json_data = response.json()
                        if len(str(json_data)) < 500:
                            logger.info(f"  Response: {json_data}")
                        else:
                            logger.info(f"  Response: Large JSON ({len(str(json_data))} chars)")
                    except:
                        logger.info(f"  Response: Not valid JSON")
                else:
                    logger.info(f"  Content-Type: {content_type}")
            elif response.status_code == 404:
                logger.debug(f"  404 Not Found")
            else:
                logger.info(f"  Response: {response.text[:100]}...")
        except Exception as e:
            logger.error(f"Endpoint {endpoint}: Error - {e}")

if __name__ == "__main__":
    check_backend_endpoints()
