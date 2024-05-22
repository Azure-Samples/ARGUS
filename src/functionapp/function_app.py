import logging
import os
import uuid
import azure.functions as func
from azure.functions.decorators import FunctionApp
from azure.cosmos import CosmosClient

app = FunctionApp()

@app.blob_trigger(arg_name="myblob", path="myblobcontainer/{name}", connection="AzureWebJobsStorage")
def main(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Blob Size: {myblob.length} bytes")

    # Connect to Cosmos DB
    endpoint = os.environ['COSMOS_DB_ENDPOINT']
    key = os.environ['COSMOS_DB_KEY']
    database_name = os.environ['COSMOS_DB_DATABASE_NAME']
    container_name = os.environ['COSMOS_DB_CONTAINER_NAME']

    client = CosmosClient(endpoint, key)

    # Select the database and container
    database = client.get_database_client(database_name)
    container = database.get_container_client(container_name)

    # Create a document in Cosmos DB
    document = {
        "id": str(uuid.uuid4()),
        "blob_name": myblob.name,
        "blob_size": myblob.length
    }
    container.create_item(document)
    logging.info(f"Item created in Database.")
