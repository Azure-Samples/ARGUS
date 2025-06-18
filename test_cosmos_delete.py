#!/usr/bin/env python3
"""
Test script to debug Cosmos DB document deletion
"""
import os
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

def test_cosmos_delete():
    # Initialize Azure credential
    credential = DefaultAzureCredential()
    
    # Cosmos DB details from environment
    cosmos_url = "https://cbqs4kagoswakeg.documents.azure.com:443/"
    cosmos_db_name = "doc-extracts"
    cosmos_documents_container = "documents"
    
    # Initialize Cosmos client
    cosmos_client = CosmosClient(cosmos_url, credential=credential)
    cosmos_database = cosmos_client.get_database_client(cosmos_db_name)
    cosmos_container = cosmos_database.get_container_client(cosmos_documents_container)
    
    print("=== UNDERSTANDING DOCUMENT STRUCTURE ===")
    
    # Let's query all documents to understand the structure
    try:
        query = "SELECT * FROM c"
        items = list(cosmos_container.query_items(
            query=query,
            enable_cross_partition_query=True
        ))
        print(f"Found {len(items)} main documents:")
        
        for i, item in enumerate(items):
            print(f"\nMain Document {i+1}:")
            print(f"  - id: {item.get('id', 'N/A')}")
            print(f"  - dataset: {item.get('dataset', 'N/A')}")
            
            doc_id = item.get('id')
            dataset = item.get('dataset')
            
            if doc_id:
                print(f"\n=== TESTING READ/DELETE FOR {doc_id} ===")
                
                # Based on backend code analysis, test these approaches:
                test_cases = [
                    ("empty dict partition key (from backend line 166, 776)", doc_id, {}),
                    ("document ID as partition key (from backend line 511, 546)", doc_id, doc_id),
                    ("dataset as partition key", doc_id, dataset),
                ]
                
                for desc, item_id, partition_key in test_cases:
                    try:
                        print(f"\nTrying to read with {desc}:")
                        print(f"  item={item_id}, partition_key={partition_key}")
                        read_doc = cosmos_container.read_item(item=item_id, partition_key=partition_key)
                        print(f"  ✅ Successfully read document!")
                        print(f"  ✅ Document ID: {read_doc.get('id')}")
                        print(f"  ✅ Dataset: {read_doc.get('dataset')}")
                        
                        # Now try to delete it with this working combination
                        print(f"\n  🗑️  Attempting to delete with same parameters...")
                        cosmos_container.delete_item(item=item_id, partition_key=partition_key)
                        print(f"  ✅ Document deleted successfully!")
                        
                        # Verify deletion
                        try:
                            cosmos_container.read_item(item=item_id, partition_key=partition_key)
                            print(f"  ❌ Document still exists after deletion!")
                        except Exception as verify_e:
                            print(f"  ✅ Confirmed: Document no longer exists ({type(verify_e).__name__})")
                        
                        print(f"\n🎉 SUCCESS! The working approach is: {desc}")
                        print(f"   Use: delete_item(item='{item_id}', partition_key={partition_key})")
                        
                        # Since we found the working approach, break out
                        return True
                        
                    except Exception as e:
                        print(f"  ❌ Failed: {type(e).__name__}: {str(e)[:100]}...")
                        continue
    
    except Exception as e:
        print(f"❌ Query error: {e}")
        return False
    
    print("\n❌ No working approach found!")
    return False

if __name__ == "__main__":
    test_cosmos_delete()
