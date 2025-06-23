#!/usr/bin/env python3
"""
Fix the default dataset configuration to enable both OCR and Images
"""

import requests
import json

def fix_configuration():
    """Fix the default dataset configuration"""
    
    backend_url = "https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io"
    
    print("Fixing default dataset configuration...")
    
    # Get current configuration
    try:
        config_response = requests.get(f"{backend_url}/api/configuration", timeout=10)
        if config_response.status_code != 200:
            print(f"Failed to get configuration: {config_response.text}")
            return
        
        config_data = config_response.json()
        print(f"Current configuration retrieved")
        
        # Update default dataset to enable both OCR and Images
        if 'datasets' not in config_data:
            config_data['datasets'] = {}
        
        if 'default-dataset' not in config_data['datasets']:
            print("No default-dataset found, creating one...")
            config_data['datasets']['default-dataset'] = {
                "model_prompt": "Extract all data from the document in a comprehensive and structured manner.",
                "example_schema": {},
                "max_pages_per_chunk": 10
            }
        
        # Update processing options to enable both OCR and Images
        config_data['datasets']['default-dataset']['processing_options'] = {
            "include_ocr": True,
            "include_images": True, 
            "enable_summary": True,
            "enable_evaluation": True
        }
        
        print("Updated default-dataset processing options:")
        print(json.dumps(config_data['datasets']['default-dataset']['processing_options'], indent=2))
        
        # Save the updated configuration
        update_response = requests.post(
            f"{backend_url}/api/configuration",
            json=config_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        if update_response.status_code == 200:
            print("✅ Configuration updated successfully!")
        else:
            print(f"❌ Failed to update configuration: {update_response.text}")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fix_configuration()
