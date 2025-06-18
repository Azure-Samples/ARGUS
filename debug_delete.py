#!/usr/bin/env python3
"""
Debug script to test Cosmos DB delete functionality directly
"""

import os
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

def main():
    # Initialize Azure clients
    try:
        credential = DefaultAzureCredential()
        
        # Cosmos DB setup
        cosmos_account_url = os.environ.get("COSMOS_URL")
        container_name = os.environ.get("COSMOS_DOCUMENTS_CONTAINER_NAME", "documents")
        database_name = os.environ.get("COSMOS_DB_NAME", "ARGUS")
        
        print(f"Cosmos Account URL: {cosmos_account_url}")
        print(f"Database Name: {database_name}")
        print(f"Container Name: {container_name}")
        
        if not cosmos_account_url:
            print("Error: COSMOS_URL not found in environment")
            return
            
        cosmos_client = CosmosClient(cosmos_account_url, credential)
        database = cosmos_client.get_database_client(database_name)
        container = database.get_container_client(container_name)
        
        # List some documents first
        print("\n=== Checking database and container existence ===")
        
        # Check if database exists
        try:
            db_info = database.read()
            print(f"Database '{database_name}' exists: {db_info['id']}")
        except Exception as e:
            print(f"Database error: {str(e)}")
            
        # Check if container exists
        try:
            container_info = container.read()
            print(f"Container '{container_name}' exists: {container_info['id']}")
        except Exception as e:
            print(f"Container error: {str(e)}")
            
        # Try to list all containers in the database
        try:
            print("\n=== Containers in database ===")
            for container_props in database.list_containers():
                print(f"Container: {container_props['id']}")
        except Exception as e:
            print(f"Error listing containers: {str(e)}")
        
        print("\n=== Listing documents in container ===")
        try:
            # Try different queries
            queries = [
                "SELECT c.id, c.dataset_name, c.filename FROM c",
                "SELECT * FROM c"
            ]
            
            items = []
            for query in queries:
                print(f"\nTrying query: {query}")
                try:
                    query_items = list(container.query_items(query=query, enable_cross_partition_query=True, max_item_count=10))
                    print(f"Found {len(query_items)} items")
                    if query_items and not items:  # Use first successful query
                        items = query_items
                    for item in query_items[:3]:  # Show first 3 items
                        print(f"  Item ID: {item.get('id')}, Dataset: {item.get('dataset_name')}, Filename: {item.get('filename')}")
                except Exception as e:
                    print(f"  Query failed: {str(e)}")
                    
        except Exception as e:
            print(f"Query error: {str(e)}")
            
        if not items:
            print("No documents found - cannot test delete")
            return
            
        # Test delete operation on the first item
        test_item = items[0]
        document_id = test_item['id']
        
        print(f"\n=== Testing delete operation ===")
        print(f"Attempting to delete document ID: {document_id}")
        
        try:
            # Try different partition key strategies
            partition_keys_to_try = [
                {},  # Empty dict (what we determined was correct)
                test_item.get('dataset_name'),  # Dataset name
                document_id,  # Document ID itself
            ]
            
            for i, pk in enumerate(partition_keys_to_try):
                try:
                    print(f"\nAttempt {i+1}: Using partition key: {pk}")
                    response = container.delete_item(item=document_id, partition_key=pk)
                    print(f"SUCCESS! Deleted with partition key: {pk}")
                    print(f"Response: {response}")
                    
                    # Verify deletion
                    print("Verifying deletion...")
                    remaining_items = list(container.query_items(
                        query="SELECT c.id FROM c", 
                        enable_cross_partition_query=True
                    ))
                    print(f"Remaining documents: {len(remaining_items)}")
                    break
                except Exception as e:
                    print(f"Failed with partition key {pk}: {str(e)}")
                    continue
            else:
                print("All partition key attempts failed!")
                
        except Exception as e:
            print(f"Delete operation failed: {str(e)}")
            
        # Test delete operation on the first item
        test_item = items[0]
        document_id = test_item['id']
        
        print(f"\n=== Testing delete operation ===")
        print(f"Attempting to delete document ID: {document_id}")
        
        try:
            # Try different partition key strategies
            partition_keys_to_try = [
                {},  # Empty dict (what we determined was correct)
                test_item.get('dataset_name'),  # Dataset name
                document_id,  # Document ID itself
            ]
            
            for i, pk in enumerate(partition_keys_to_try):
                try:
                    print(f"\nAttempt {i+1}: Using partition key: {pk}")
                    response = container.delete_item(item=document_id, partition_key=pk)
                    print(f"SUCCESS! Deleted with partition key: {pk}")
                    print(f"Response: {response}")
                    break
                except Exception as e:
                    print(f"Failed with partition key {pk}: {str(e)}")
                    continue
            else:
                print("All partition key attempts failed!")
                
        except Exception as e:
            print(f"Delete operation failed: {str(e)}")
            
    except Exception as e:
        print(f"Error initializing clients: {str(e)}")

if __name__ == "__main__":
    main()
