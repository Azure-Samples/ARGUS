#!/usr/bin/env python3
"""
Debug script to test GPT extraction with different processing options
"""

import os
import json
import requests
import time
from datetime import datetime

def test_processing_options():
    """Test different combinations of processing options"""
    
    # Backend URL - update this to match your deployment
    backend_url = "https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io"
    
    print("=" * 80)
    print("ARGUS Processing Options Debug Test")
    print("=" * 80)
    
    # Test 1: Both OCR and Images enabled
    print("\n1. Testing: OCR=True, Images=True")
    print("-" * 40)
    
    # We'll need to upload a test file and monitor the processing
    # For now, let's check the health endpoint
    try:
        health_response = requests.get(f"{backend_url}/health", timeout=10)
        print(f"Backend health: {health_response.status_code}")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"Backend services: {health_data.get('services', {})}")
        else:
            print(f"Health check failed: {health_response.text}")
    except Exception as e:
        print(f"Failed to connect to backend: {e}")
        return
    
    # Test configuration endpoint
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        print(f"Configuration endpoint: {config_response.status_code}")
        if config_response.status_code == 200:
            config_data = config_response.json()
            datasets = config_data.get('datasets', {})
            print(f"Available datasets: {list(datasets.keys())}")
            
            # Check default dataset configuration
            if 'default-dataset' in datasets:
                default_config = datasets['default-dataset']
                processing_options = default_config.get('processing_options', {})
                print(f"Default dataset processing options: {processing_options}")
            else:
                print("No default-dataset found in configuration")
        else:
            print(f"Configuration request failed: {config_response.text}")
    except Exception as e:
        print(f"Failed to get configuration: {e}")

    print("\n" + "=" * 80)
    print("DEBUG RECOMMENDATIONS:")
    print("=" * 80)
    print("1. Check the backend logs for GPT extraction debugging info")
    print("2. Verify the processing options are being saved correctly")
    print("3. Test with a small PDF to isolate the issue")
    print("4. Check if the issue occurs with OCR-only or Images-only")
    print("\nTo check logs, run:")
    print("az logs --resource-group <your-rg> --name <your-container-app>")

if __name__ == "__main__":
    test_processing_options()
