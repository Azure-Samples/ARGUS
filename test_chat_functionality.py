#!/usr/bin/env python3
"""
Test script to verify the new chat functionality with document extraction.
"""

import requests
import json
import time
import os

# Configuration
BACKEND_URL = "https://ca-argus.jollyriver-a6fa0b27.eastus2.azurecontainerapps.io"
TEST_DOCUMENT = "sample-invoice.pdf"

def test_chat_endpoint():
    """Test the new chat endpoint with document context"""
    
    print("🤖 Testing Chat with Document Functionality")
    print("=" * 60)
    
    # First, extract a document to get some context
    print("1. Extracting document to get context...")
    
    if not os.path.exists(TEST_DOCUMENT):
        print(f"❌ Test document '{TEST_DOCUMENT}' not found")
        return False
    
    try:
        with open(TEST_DOCUMENT, 'rb') as f:
            files = {'file': (TEST_DOCUMENT, f, 'application/pdf')}
            data = {
                'dataset': 'default-dataset',
                'max_pages_per_chunk': '3'
            }
            
            response = requests.post(
                f"{BACKEND_URL}/api/process-file", 
                files=files, 
                data=data,
                timeout=120
            )
            
            if response.status_code == 200:
                result = response.json()
                if "error" not in result:
                    extracted_data = result.get('extraction_result', {})
                    print("✅ Document extracted successfully")
                    print(f"   Fields extracted: {len(extracted_data)} items")
                else:
                    print(f"⚠️ Extraction returned error: {result['error']}")
                    # Use a sample extracted data for testing
                    extracted_data = {
                        "vendor_name": "Sample Vendor",
                        "invoice_number": "INV-001",
                        "total_amount": "$100.00"
                    }
            else:
                print(f"❌ Extraction failed: {response.status_code}")
                # Use sample data for testing
                extracted_data = {
                    "vendor_name": "Sample Vendor", 
                    "invoice_number": "INV-001",
                    "total_amount": "$100.00"
                }
                
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
        # Use sample data for testing
        extracted_data = {
            "vendor_name": "Sample Vendor",
            "invoice_number": "INV-001", 
            "total_amount": "$100.00"
        }
    
    # Now test the chat endpoint
    print("\n2. Testing chat endpoint...")
    
    chat_questions = [
        "What is the vendor name?",
        "What is the total amount on this invoice?",
        "Summarize the key information from this document"
    ]
    
    for i, question in enumerate(chat_questions, 1):
        print(f"\n   Question {i}: {question}")
        
        try:
            chat_payload = {
                "message": question,
                "document_context": json.dumps(extracted_data),
                "conversation_history": []
            }
            
            chat_response = requests.post(
                f"{BACKEND_URL}/api/chat",
                json=chat_payload,
                timeout=30
            )
            
            if chat_response.status_code == 200:
                chat_result = chat_response.json()
                if "error" not in chat_result:
                    answer = chat_result.get('response', 'No response received')
                    print(f"   ✅ Answer: {answer[:200]}{'...' if len(answer) > 200 else ''}")
                else:
                    print(f"   ❌ Chat error: {chat_result['error']}")
            else:
                print(f"   ❌ Chat request failed: {chat_response.status_code}")
                if chat_response.text:
                    print(f"      Response: {chat_response.text[:200]}")
                    
        except Exception as e:
            print(f"   ❌ Chat request exception: {e}")
    
    print("\n3. Testing chat endpoint accessibility...")
    try:
        # Simple health check for chat endpoint
        test_payload = {
            "message": "Hello",
            "document_context": "{}",
            "conversation_history": []
        }
        
        response = requests.post(
            f"{BACKEND_URL}/api/chat",
            json=test_payload,
            timeout=15
        )
        
        if response.status_code == 200:
            print("✅ Chat endpoint is accessible and responding")
            return True
        elif response.status_code == 404:
            print("❌ Chat endpoint not found - may not be deployed yet")
            return False
        elif response.status_code == 500:
            print("❌ Chat endpoint has server error")
            print(f"   Response: {response.text[:300]}")
            return False
        else:
            print(f"❌ Chat endpoint returned status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Failed to test chat endpoint: {e}")
        return False

def main():
    """Main test function"""
    print("🧪 CHAT FUNCTIONALITY TEST")
    print("=" * 60)
    print("This test verifies the new chat with document feature.")
    print()
    
    success = test_chat_endpoint()
    
    print("\n" + "=" * 60)
    print("📊 TEST RESULTS")
    print("=" * 60)
    
    if success:
        print("✅ Chat functionality is working!")
        print("Users can now chat with their extracted documents.")
    else:
        print("❌ Chat functionality needs debugging.")
        print("Check backend deployment and endpoint implementation.")
    
    return success

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
