#!/usr/bin/env python3
"""
Script to initialize Cosmos DB with default dataset configurations.
This should be run once to set up initial datasets.
"""

import os
import json
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

def initialize_datasets():
    """Initialize Cosmos DB with default dataset configurations"""
    
    # Read environment variables (these should be set in the deployment)
    cosmos_url = os.getenv('COSMOS_URL')
    cosmos_db_name = os.getenv('COSMOS_DB_NAME')
    cosmos_config_container_name = os.getenv('COSMOS_CONFIG_CONTAINER_NAME')
    
    if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
        print("Missing required environment variables:")
        print(f"COSMOS_URL: {cosmos_url}")
        print(f"COSMOS_DB_NAME: {cosmos_db_name}")
        print(f"COSMOS_CONFIG_CONTAINER_NAME: {cosmos_config_container_name}")
        return False
    
    # Load default dataset configurations
    default_dataset_schema = {}
    default_dataset_prompt = "Extract all data."
    
    medical_dataset_schema = {}
    medical_dataset_prompt = """Extract information about patients, medical conditions, treatments, analysis or appointments/visits they made at hospitals, doctors or laboratories, payments of invoices or purchases of medicaments.
On the field 'categorization' choose one of these: 1) 'invoice' 2) 'medical_report' based on your classification. 
If you cannot determine that the content belongs to one of these categories then apply a classification 'N/A'."""
    
    # Load schema files
    try:
        with open('demo/default-dataset/output_schema.json', 'r') as f:
            default_dataset_schema = json.load(f)
    except FileNotFoundError:
        print("Warning: demo/default-dataset/output_schema.json not found")
        default_dataset_schema = {
            "Customer Name": "",
            "Invoice Number": "",
            "Date": "",
            "Billing info": {
                "Customer": "",
                "Customer ID": "",
                "Address": "",
                "Phone": ""
            }
        }
    
    try:
        with open('demo/medical-dataset/output_schema.json', 'r') as f:
            medical_dataset_schema = json.load(f)
    except FileNotFoundError:
        print("Warning: demo/medical-dataset/output_schema.json not found")
        medical_dataset_schema = {
            "Patient Name": "",
            "Medical Record Number": "",
            "Date of Visit": "",
            "categorization": ""
        }
    
    # Create configuration document
    config_data = {
        "id": "configuration",
        "partitionKey": "configuration",
        "datasets": {
            "default-dataset": {
                "model_prompt": default_dataset_prompt,
                "example_schema": default_dataset_schema
            },
            "medical-dataset": {
                "model_prompt": medical_dataset_prompt,
                "example_schema": medical_dataset_schema
            }
        }
    }
    
    try:
        # Initialize Cosmos client
        credential = DefaultAzureCredential()
        cosmos_client = CosmosClient(cosmos_url, credential=credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Upsert the configuration document
        response = container.upsert_item(config_data)
        print("✅ Successfully initialized Cosmos DB with default datasets!")
        print(f"Configuration document ID: {response['id']}")
        print(f"Available datasets: {list(config_data['datasets'].keys())}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to initialize Cosmos DB: {str(e)}")
        return False

if __name__ == "__main__":
    print("Initializing Cosmos DB with default dataset configurations...")
    success = initialize_datasets()
    exit(0 if success else 1)
