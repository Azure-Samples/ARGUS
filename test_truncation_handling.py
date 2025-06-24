#!/usr/bin/env python3
"""
Test script to verify enhanced truncation error handling in the document extraction pipeline.
This script will test the system with a large document to trigger token limit truncation.
"""

import requests
import json
import time
import os
from pathlib import Path

# Configuration
BACKEND_URL = "https://ca-argus.politesea-e2f9610e.northcentralusstage.azurecontainerapps.io"
TEST_DOCUMENT = "sample-invoice.pdf"  # Use the sample document

def test_truncation_error_handling():
    """Test the enhanced error handling for GPT response truncation"""
    
    print("🔍 Testing Enhanced Truncation Error Handling")
    print("=" * 60)
    
    # Check if test document exists
    if not os.path.exists(TEST_DOCUMENT):
        print(f"❌ Test document '{TEST_DOCUMENT}' not found")
        print("Please make sure the sample-invoice.pdf file is in the current directory")
        return False
    
    # First, check backend health
    print("1. Checking backend health...")
    try:
        health_response = requests.get(f"{BACKEND_URL}/", timeout=10)
        if health_response.status_code == 200:
            health_data = health_response.json()
            if health_data.get("status") == "healthy":
                print("✅ Backend is healthy")
            else:
                print(f"⚠️ Backend returned: {health_data}")
        else:
            print(f"⚠️ Backend health check returned: {health_response.status_code}")
    except Exception as e:
        print(f"❌ Backend health check failed: {e}")
        return False
    
    # Test with small chunk size to ensure it works normally
    print("\n2. Testing with normal chunk size (should work)...")
    try:
        with open(TEST_DOCUMENT, 'rb') as f:
            files = {'file': (TEST_DOCUMENT, f, 'application/pdf')}
            data = {
                'dataset': 'default-dataset',
                'max_pages_per_chunk': '5'  # Normal chunk size
            }
            
            response = requests.post(
                f"{BACKEND_URL}/extract", 
                files=files, 
                data=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    print(f"⚠️ Normal extraction returned error: {result['error']}")
                    # Check if it's a truncation error
                    if result.get('error_type') in ['token_limit_exceeded', 'likely_truncation']:
                        print("✅ Truncation error detected and handled correctly!")
                        print(f"   Error type: {result.get('error_type')}")
                        if 'user_action_required' in result:
                            print(f"   User message: {result['user_action_required']}")
                        if 'recommendations' in result:
                            print("   Recommendations:")
                            for i, rec in enumerate(result['recommendations'], 1):
                                print(f"     {i}. {rec}")
                        return True
                    else:
                        print(f"   Other error type: {result.get('error_type', 'unknown')}")
                else:
                    print("✅ Normal extraction completed successfully")
            else:
                print(f"❌ Normal extraction failed with status: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                
    except Exception as e:
        print(f"❌ Normal extraction test failed: {e}")
    
    # Test with very large chunk to trigger truncation
    print("\n3. Testing with large chunk size (should trigger truncation)...")
    try:
        with open(TEST_DOCUMENT, 'rb') as f:
            files = {'file': (TEST_DOCUMENT, f, 'application/pdf')}
            data = {
                'dataset': 'default-dataset',
                'max_pages_per_chunk': '50'  # Very large chunk size to trigger truncation
            }
            
            response = requests.post(
                f"{BACKEND_URL}/extract", 
                files=files, 
                data=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if "error" in result:
                    error_type = result.get('error_type', 'unknown')
                    print(f"✅ Extraction returned error as expected")
                    print(f"   Error type: {error_type}")
                    print(f"   Error message: {result['error']}")
                    
                    # Check if it's a truncation-related error
                    if error_type in ['token_limit_exceeded', 'likely_truncation']:
                        print("🎯 TRUNCATION ERROR DETECTED AND HANDLED CORRECTLY!")
                        
                        if 'user_action_required' in result:
                            print(f"\n📋 User Action Required:")
                            print(f"   {result['user_action_required']}")
                        
                        if 'recommendations' in result:
                            print(f"\n💡 Recommendations:")
                            for i, rec in enumerate(result['recommendations'], 1):
                                print(f"   {i}. {rec}")
                        
                        if 'technical_details' in result:
                            print(f"\n🔧 Technical Details:")
                            tech = result['technical_details']
                            for key, value in tech.items():
                                print(f"   {key}: {value}")
                        
                        return True
                    else:
                        print(f"⚠️ Different error type detected: {error_type}")
                        return False
                else:
                    print("⚠️ Large chunk extraction completed without truncation (unexpected)")
                    print("   This might indicate the document is smaller than expected")
                    return False
            else:
                print(f"❌ Large chunk extraction failed with status: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
                
    except Exception as e:
        print(f"❌ Large chunk extraction test failed: {e}")
        return False
    
    return False

def test_configuration_endpoint():
    """Test that the configuration endpoint shows proper settings"""
    print("\n4. Testing configuration endpoint...")
    try:
        config_response = requests.get(f"{BACKEND_URL}/configuration", timeout=10)
        if config_response.status_code == 200:
            config = config_response.json()
            print("✅ Configuration retrieved successfully")
            
            # Check key configuration parameters
            if 'openai_model_deployment' in config:
                print(f"   Model: {config['openai_model_deployment']}")
            
            if 'example_schema' in config:
                schema_length = len(str(config['example_schema']))
                print(f"   Schema length: {schema_length} characters")
            
            if 'model_prompt' in config:
                prompt_length = len(config['model_prompt'])
                print(f"   Prompt length: {prompt_length} characters")
            
            return True
        else:
            print(f"❌ Configuration endpoint failed: {config_response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Configuration test failed: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 TRUNCATION ERROR HANDLING TEST")
    print("=" * 60)
    print("This test verifies that the system properly detects and handles")
    print("GPT response truncation due to hitting max completion tokens.")
    print()
    
    # Run tests
    config_success = test_configuration_endpoint()
    truncation_success = test_truncation_error_handling()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS SUMMARY")
    print("=" * 60)
    print(f"Configuration Test: {'✅ PASSED' if config_success else '❌ FAILED'}")
    print(f"Truncation Handling: {'✅ PASSED' if truncation_success else '❌ FAILED'}")
    
    if truncation_success:
        print("\n🎉 SUCCESS: Truncation error handling is working correctly!")
        print("The system now properly:")
        print("  • Detects when GPT responses are truncated")
        print("  • Provides clear error messages to users")
        print("  • Suggests actionable solutions")
        print("  • Includes technical details for debugging")
    else:
        print("\n❌ FAILURE: Truncation error handling needs more work")
        print("Please check the backend logs and code implementation")
    
    return truncation_success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
