import os
import asyncio
import json
import base64
from datetime import datetime
from dotenv import load_dotenv
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
from mcp.server.fastmcp import FastMCP, Context

# Load environment variables
load_dotenv()

# Initialize Azure credentials
credential = DefaultAzureCredential()

# Create an MCP server
mcp = FastMCP("ARGUS")

@mcp.tool()
async def upload_file_to_blob(file_content: str, file_name: str, dataset_name: str, ctx: Context) -> str:
    """
    Upload a file to Azure Blob Storage
    
    Args:
        file_content: The content of the file encoded as a base64 string
        file_name: The name of the file
        dataset_name: The dataset folder to upload the file to
    
    Returns:
        A message indicating success or failure
    """
    try:
        # Get blob storage connection details from environment variables
        blob_url = os.getenv("BLOB_ACCOUNT_URL")
        container_name = os.getenv("CONTAINER_NAME")
        
        if not blob_url or not container_name:
            return "Error: Missing blob storage configuration"
        
        # Connect to the Blob storage account
        blob_service_client = BlobServiceClient(account_url=blob_url, credential=credential)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Report progress
        ctx.info(f"Uploading file {file_name} to {dataset_name} folder...")
        
        # Upload file to the specified dataset folder in Blob storage
        blob_client = container_client.get_blob_client(f"{dataset_name}/{file_name}")
        
        # Decode base64 content and upload
        decoded_content = base64.b64decode(file_content)
        blob_client.upload_blob(decoded_content, overwrite=True)
        
        return f"File {file_name} uploaded successfully to {dataset_name} folder!"
    
    except Exception as e:
        ctx.error(f"Error uploading file: {str(e)}")
        return f"Error uploading file: {str(e)}"

@mcp.tool()
async def list_datasets() -> list:
    """
    List all available datasets in the system
    
    Returns:
        A list of dataset names
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_config_container_name = os.getenv("COSMOS_CONFIG_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
            # Fallback to hardcoded datasets if configuration is not available
            return ["default-dataset", "medical-dataset"]
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Get the configuration item
        configuration = container.read_item(item="configuration", partition_key={})
        
        # Extract dataset names from configuration
        dataset_names = [key for key in configuration.keys() 
                        if key != 'id' and isinstance(configuration[key], dict) 
                        and 'model_prompt' in configuration[key]
                        and 'example_schema' in configuration[key]]
        
        return dataset_names
    except Exception as e:
        # print exception
        print(f"Error listing datasets: {str(e)}")
        # Fallback to hardcoded datasets if there was an error
        return ["default-dataset", "medical-dataset"]

@mcp.tool()
async def get_dataset_details(dataset_name: str) -> dict:
    """
    Get details about a specific dataset including model prompt and schema
    
    Args:
        dataset_name: The name of the dataset to get details for
    
    Returns:
        A dictionary containing the model prompt and schema for the dataset
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_config_container_name = os.getenv("COSMOS_CONFIG_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
            return {"error": "Missing CosmosDB configuration"}
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Get the configuration item
        configuration = container.read_item(item="configuration", partition_key={})
        
        # Get the model prompt and schema for the dataset
        if dataset_name in configuration:
            return {
                "model_prompt": configuration[dataset_name].get("model_prompt", ""),
                "example_schema": configuration[dataset_name].get("example_schema", {})
            }
        else:
            return {"error": f"Dataset {dataset_name} not found"}
    except Exception as e:
        return {"error": f"Error getting dataset details: {str(e)}"}

@mcp.tool()
async def update_dataset(dataset_name: str, model_prompt: str, example_schema: str, ctx: Context) -> dict:
    """
    Update or create a dataset with the specified model prompt and schema
    
    Args:
        dataset_name: The name of the dataset to update or create
        model_prompt: The model prompt for the dataset
        example_schema: The example schema for the dataset as a JSON string
    
    Returns:
        A dictionary indicating success or failure
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_config_container_name = os.getenv("COSMOS_CONFIG_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
            return {"success": False, "message": "Missing CosmosDB configuration"}
        
        # Try to parse the example schema as JSON
        try:
            example_schema_dict = json.loads(example_schema)
        except json.JSONDecodeError as e:
            return {"success": False, "message": f"Invalid JSON in example schema: {str(e)}"}
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Get the configuration item
        try:
            configuration = container.read_item(item="configuration", partition_key={})
        except Exception:
            # If the configuration item doesn't exist, create it
            configuration = {"id": "configuration"}
        
        # Report progress
        ctx.info(f"Updating dataset {dataset_name}...")
        
        # Update the dataset in the configuration
        configuration[dataset_name] = {
            "model_prompt": model_prompt,
            "example_schema": example_schema_dict
        }
        
        # Update the configuration item
        container.upsert_item(configuration)
        
        return {"success": True, "message": f"Dataset {dataset_name} updated successfully"}
    except Exception as e:
        ctx.error(f"Error updating dataset: {str(e)}")
        return {"success": False, "message": f"Error updating dataset: {str(e)}"}

@mcp.tool()
async def get_processed_files(filter_dataset: list = None, filter_status: str = "All", ctx: Context = None) -> list:
    """
    Get a list of processed files from CosmosDB
    
    Args:
        filter_dataset: Optional list of dataset names to filter by
        filter_status: Optional status to filter by (All, Finished, or Not Finished)
    
    Returns:
        A list of dictionaries containing file information
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_documents_container_name = os.getenv("COSMOS_DOCUMENTS_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_documents_container_name]):
            if ctx:
                ctx.error("Missing CosmosDB configuration")
            return []
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_documents_container_name)
        
        # Query for all items
        items = list(container.query_items(
            query="SELECT * FROM c",
            enable_cross_partition_query=True
        ))
        
        # Process the items
        results = []
        for item in items:
            blob_name = item.get('properties', {}).get('blob_name', '')
            dataset_name = blob_name.split('/')[1] if len(blob_name.split('/')) > 1 else ''
            file_name = '/'.join(blob_name.split('/')[2:]) if len(blob_name.split('/')) > 2 else ''
            
            # Skip if not in the filtered datasets
            if filter_dataset and dataset_name not in filter_dataset:
                continue
                
            # Get the processing status
            errors = item.get('errors', '')
            is_finished = item.get('state', {}).get('processing_completed', False)
            
            # Filter by status
            if filter_status == "Finished" and not is_finished:
                continue
            elif filter_status == "Not Finished" and is_finished:
                continue
                
            # Format the item
            result = {
                'id': item.get('id', ''),
                'dataset': dataset_name,
                'file_name': file_name,
                'request_timestamp': item.get('properties', {}).get('request_timestamp', ''),
                'total_time': item.get('properties', {}).get('total_time_seconds', 0),
                'num_pages': item.get('properties', {}).get('num_pages', 0),
                'blob_size': item.get('properties', {}).get('blob_size', 0),
                'is_finished': is_finished,
                'has_errors': bool(errors),
                'state': item.get('state', {}),
                'errors': errors
            }
            results.append(result)
            
        return results
    except Exception as e:
        if ctx:
            ctx.error(f"Error getting processed files: {str(e)}")
        return []

@mcp.tool()
async def get_file_details(file_id: str, ctx: Context) -> dict:
    """
    Get detailed information about a processed file
    
    Args:
        file_id: The ID of the file to get details for
    
    Returns:
        A dictionary containing the file details and extracted data
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_documents_container_name = os.getenv("COSMOS_DOCUMENTS_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_documents_container_name]):
            return {"error": "Missing CosmosDB configuration"}
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_documents_container_name)
        
        # Get the file details
        file_data = container.read_item(item=file_id, partition_key={})
        
        # Get the file blob
        blob_name = file_data.get('properties', {}).get('blob_name', '')
        if blob_name:
            try:
                # Get blob storage connection details from environment variables
                blob_url = os.getenv("BLOB_ACCOUNT_URL")
                container_name = os.getenv("CONTAINER_NAME")
                
                if blob_url and container_name:
                    # Connect to the Blob storage account
                    blob_service_client = BlobServiceClient(account_url=blob_url, credential=credential)
                    blob_container_client = blob_service_client.get_container_client(container_name)
                    blob_client = blob_container_client.get_blob_client(blob_name)
                    
                    # Get the blob data
                    blob_data = blob_client.download_blob().readall()
                    file_data['blob_data_base64'] = base64.b64encode(blob_data).decode('utf-8')
            except Exception as e:
                ctx.warning(f"Could not fetch blob data: {str(e)}")
        
        return file_data
    except Exception as e:
        ctx.error(f"Error getting file details: {str(e)}")
        return {"error": f"Error getting file details: {str(e)}"}

@mcp.tool()
async def delete_file(file_id: str, dataset_name: str, file_name: str, ctx: Context) -> dict:
    """
    Delete a processed file from CosmosDB and optionally Blob storage
    
    Args:
        file_id: The ID of the file to delete
        dataset_name: The dataset name for the file
        file_name: The name of the file
    
    Returns:
        A dictionary indicating success or failure
    """
    try:
        # Get cosmos DB connection details from environment variables
        cosmos_url = os.getenv("COSMOS_URL")
        cosmos_db_name = os.getenv("COSMOS_DB_NAME")
        cosmos_documents_container_name = os.getenv("COSMOS_DOCUMENTS_CONTAINER_NAME")
        
        if not all([cosmos_url, cosmos_db_name, cosmos_documents_container_name]):
            return {"success": False, "message": "Missing CosmosDB configuration"}
        
        # Connect to the CosmosDB
        cosmos_client = CosmosClient(cosmos_url, credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_documents_container_name)
        
        # Report progress
        ctx.info(f"Deleting file {file_name} from dataset {dataset_name}...")
        
        # Delete the file from CosmosDB
        container.delete_item(item=file_id, partition_key={})
        
        # Try to delete the file from Blob storage as well
        blob_url = os.getenv("BLOB_ACCOUNT_URL")
        blob_container_name = os.getenv("CONTAINER_NAME")
        
        if blob_url and blob_container_name:
            try:
                # Connect to the Blob storage account
                blob_service_client = BlobServiceClient(account_url=blob_url, credential=credential)
                blob_container_client = blob_service_client.get_container_client(blob_container_name)
                blob_client = blob_container_client.get_blob_client(f"{dataset_name}/{file_name}")
                
                # Delete the blob
                blob_client.delete_blob()
            except Exception as e:
                # Don't fail if blob deletion fails, just log it
                ctx.warning(f"Could not delete blob: {str(e)}")
        
        return {"success": True, "message": f"File {file_name} deleted successfully"}
    except Exception as e:
        ctx.error(f"Error deleting file: {str(e)}")
        return {"success": False, "message": f"Error deleting file: {str(e)}"}

@mcp.tool()
async def reprocess_file(dataset_name: str, file_name: str, ctx: Context) -> dict:
    """
    Trigger reprocessing of a file by copying it in Blob storage
    
    Args:
        dataset_name: The dataset name for the file
        file_name: The name of the file
    
    Returns:
        A dictionary indicating success or failure
    """
    try:
        # Get blob storage connection details from environment variables
        blob_url = os.getenv("BLOB_ACCOUNT_URL")
        container_name = os.getenv("CONTAINER_NAME")
        
        if not blob_url or not container_name:
            return {"success": False, "message": "Missing blob storage configuration"}
        
        # Connect to the Blob storage account
        blob_service_client = BlobServiceClient(account_url=blob_url, credential=credential)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Report progress
        ctx.info(f"Triggering reprocessing for file {file_name} in dataset {dataset_name}...")
        
        # Define the source blob path
        blob_path = f"{dataset_name}/{file_name}"
        
        # Get the source blob client
        source_blob_client = container_client.get_blob_client(blob_path)
        
        # Copy the blob to itself to trigger reprocessing
        copy_blob_client = container_client.get_blob_client(blob_path)
        copy_blob_client.start_copy_from_url(source_blob_client.url)
        
        return {"success": True, "message": f"Reprocessing triggered for {file_name}"}
    except Exception as e:
        ctx.error(f"Error triggering reprocessing: {str(e)}")
        return {"success": False, "message": f"Error triggering reprocessing: {str(e)}"}

@mcp.tool()
async def get_system_info() -> dict:
    """
    Get information about the ARGUS system and its capabilities
    
    Returns:
        A dictionary containing system information
    """
    return {
        "name": "ARGUS: Automated Retrieval and GPT Understanding System",
        "version": "1.0.0",
        "description": "The ARGUS System is designed to process PDF files to extract data using Azure Document Intelligence and Azure OpenAI.",
        "capabilities": [
            "Process PDF files using Azure Document Intelligence OCR and Vision-enabled GPT-4",
            "Manage datasets with custom model prompts and example schemas",
            "View processed files and their extracted data",
            "Reprocess and delete files",
            "Visualize data analytics"
        ],
        "instructions": {
            "upload_files": "Use the upload_file_to_blob tool to upload files to a dataset",
            "manage_datasets": "Use the list_datasets, get_dataset_details, and update_dataset tools to manage datasets",
            "view_files": "Use the get_processed_files tool to view processed files",
            "get_details": "Use the get_file_details tool to get detailed information about a processed file",
            "delete_files": "Use the delete_file tool to delete processed files",
            "reprocess_files": "Use the reprocess_file tool to trigger reprocessing of files"
        }
    }

if __name__ == "__main__":
    print("starting mcp server")
    asyncio.run(mcp.run_sse_async())

