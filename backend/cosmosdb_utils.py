from azure.cosmos import CosmosClient, PartitionKey
import os
import json
import logging

from dotenv import load_dotenv

load_dotenv()

class CosmosDBManager:
    def __init__(self):
        # Initialize the Cosmos schema
        endpoint = os.environ["COSMOSDB_ENDPOINT"]
        key = os.environ["COSMOSDB_KEY"]
        self.schema = CosmosClient(endpoint, key)

        # Database and container settings
        database_name = os.getenv("COSMOSDB_DATABASE_NAME")
        schema_container_name =  os.getenv("COSMOSDB_CONTAINER_SCHEMA_NAME")
        schema_partition_key = PartitionKey(path="/schemaId")
        system_container_name =  os.getenv("COSMOSDB_CONTAINER_SYSTEM_NAME")
        system_partition_key = PartitionKey(path="/requestId")

        # Create the database if it does not exist
        self.db = self.schema.create_database_if_not_exists(id=database_name)

        # Create the schema container if it does not exist
        self.schema_container = self.db.create_container_if_not_exists(
            id=schema_container_name, 
            partition_key=schema_partition_key
        )
        # Create the system container if it does not exist
        self.system_container = self.db.create_container_if_not_exists(
            id=system_container_name, 
            partition_key=system_partition_key
        )


    
    def create_schema(self, schemaId, schema_data):
        try:
            # Create a new document in the container
            created_schema = self.schema_container.upsert_item(body=schema_data)
            logging.info(f"Created new schema with id: {schemaId}")
            return 
        except Exception as e:
            logging.error(f"An error occurred in create_schema: {e}")
            return None


    def read_schema(self, schemaId):
        query = "SELECT * FROM c WHERE c.id=@schemaId"
        parameters = [{"name": "@schemaId", "value": schemaId}]
        items = list(self.schema_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        if items:
            item_dict = items[0]
            # values_dict = {key : value for key, value in item_dict.items() if not key.startswith('_')}
            return item_dict
        else:
            return None

    def list_all_schema(self):

        return list(self.schema_container.read_all_items())


    def delete_all_schema(self):

        container_schema_name = os.getenv("COSMOSDB_CONTAINER_SCHEMA_NAME")
        schema_partition_key = PartitionKey(path="/schemaId")

        # Delete the schema container        
        self.db.delete_container(container_schema_name)
        
        # Create the schema container if it does not exist
        self.schema_container = self.db.create_container_if_not_exists(
            id=container_schema_name, 
            partition_key=schema_partition_key
        )


    def create_system_request(self, request_id, request_data):
        
        try:
            # Create a new document in the container
            created_request = self.system_container.create_item(body=request_data)
            logging.info(f"Created new system request with id: {request_id}")
            return 
        except Exception as e:
            logging.error(f"An error occurred in create_system_request: {e}")
            return None


    def read_request_info(self, request_id):
        query = "SELECT * FROM c WHERE c.id=@requestId"
        parameters = [{"name": "@requestId", "value": request_id}]
        items = list(self.system_container.query_items(
            query=query,
            parameters=parameters,
            enable_cross_partition_query=True
        ))

        if items:
            item_dict = items[0]
            # values_dict = {key : value for key, value in item_dict.items() if not key.startswith('_')}
            return item_dict
        else:
            return None

        
    def list_all_requests(self, max_size):

       return list(self.system_container.read_all_items(max_item_count=max_size))

       