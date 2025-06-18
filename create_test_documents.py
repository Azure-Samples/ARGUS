#!/usr/bin/env python3
"""
Create test documents in Cosmos DB for testing delete functionality
"""

import os
import json
from datetime import datetime
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

# Load environment variables from .azure config
env_file = "/Users/konstantinos/Code/argus-testing/ARGUS/.azure/argus-4/.env"
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                value = value.strip('"')
                os.environ[key] = value

def create_test_documents():
    """Create test documents in Cosmos DB"""
    try:
        credential = DefaultAzureCredential()
        
        # Cosmos DB setup
        cosmos_url = os.environ.get("COSMOS_URL")
        database_name = os.environ.get("COSMOS_DB_NAME", "doc-extracts")
        container_name = os.environ.get("COSMOS_DOCUMENTS_CONTAINER_NAME", "documents")
        
        print(f"Creating test documents...")
        print(f"Cosmos URL: {cosmos_url}")
        print(f"Database: {database_name}")
        print(f"Container: {container_name}")
        
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        
        # Create test documents with the expected structure
        test_documents = [
            {
                "id": "default-dataset__test_invoice_1.pdf",
                "dataset_name": "default-dataset",
                "filename": "test_invoice_1.pdf",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "extracted_data": {
                    "Customer Name": "Test Customer 1",
                    "Invoice Number": "INV-001",
                    "Date": "2025-01-01",
                    "Total": "$100.00"
                },
                "processing_time": 2.5,
                "file_size": 1024,
                "blob_url": "https://example.com/blob/test_invoice_1.pdf"
            },
            {
                "id": "default-dataset__test_invoice_2.pdf",
                "dataset_name": "default-dataset", 
                "filename": "test_invoice_2.pdf",
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "extracted_data": {
                    "Customer Name": "Test Customer 2",
                    "Invoice Number": "INV-002",
                    "Date": "2025-01-02",
                    "Total": "$250.00"
                },
                "processing_time": 3.1,
                "file_size": 2048,
                "blob_url": "https://example.com/blob/test_invoice_2.pdf"
            },
            {
                "id": "medical-dataset__patient_report_1.pdf",
                "dataset_name": "medical-dataset",
                "filename": "patient_report_1.pdf", 
                "status": "completed",
                "timestamp": datetime.utcnow().isoformat(),
                "extracted_data": {
                    "Patient Name": "John Doe",
                    "Report Date": "2025-01-01",
                    "Diagnosis": "Routine checkup"
                },
                "processing_time": 1.8,
                "file_size": 512,
                "blob_url": "https://example.com/blob/patient_report_1.pdf"
            }
        ]
        
        print(f"\nCreating {len(test_documents)} test documents...")
        
        for doc in test_documents:
            try:
                # Try to create the document
                result = container.create_item(body=doc)
                print(f"✅ Created document: {doc['id']}")
            except Exception as e:
                if "Conflict" in str(e):
                    print(f"📝 Document already exists: {doc['id']}")
                else:
                    print(f"❌ Failed to create document {doc['id']}: {str(e)}")
        
        # Verify documents were created
        print(f"\n=== Verifying created documents ===")
        query = "SELECT c.id, c.dataset_name, c.filename, c.status FROM c"
        items = list(container.query_items(query=query, enable_cross_partition_query=True))
        
        print(f"Found {len(items)} documents in container:")
        for item in items:
            print(f"  - {item['id']} ({item['dataset_name']}/{item['filename']}) - {item['status']}")
        
        return True
        
    except Exception as e:
        print(f"Error creating test documents: {str(e)}")
        return False

if __name__ == "__main__":
    success = create_test_documents()
    if success:
        print("\n✅ Test documents created successfully!")
        print("You can now test the delete functionality in the web app.")
    else:
        print("\n❌ Failed to create test documents.")
