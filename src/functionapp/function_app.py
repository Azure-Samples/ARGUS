import logging  
import os  
import azure.functions as func  
from azure.functions.decorators import FunctionApp  
from azure.cosmos import CosmosClient  
import traceback  
import json  
import tempfile  
from datetime import datetime  
from pathlib import Path  
from ai_ocr.chains import get_structured_data, get_final_reasoning_from_markdown  
from ai_ocr.process import process_pdf  
  
app = FunctionApp()  
  
@app.blob_trigger(arg_name="myblob", path="myblobcontainer/{name}", connection="AzureWebJobsStorage")  
def main(myblob: func.InputStream):  
    logging.info(f"Python blob trigger function processed blob \n"  
                 f"Name: {myblob.name}\n"  
                 f"Blob Size: {myblob.length} bytes")  
    try:  
        # Connect to Cosmos DB  
        endpoint = os.environ['COSMOS_DB_ENDPOINT']  
        key = os.environ['COSMOS_DB_KEY']  
        database_name = os.environ['COSMOS_DB_DATABASE_NAME']  
        container_name = os.environ['COSMOS_DB_CONTAINER_NAME']  
        client = CosmosClient(endpoint, key)  
        database = client.get_database_client(database_name)  
        container = database.get_container_client(container_name)  

        # Write the blob content to a temp file  
        file_content = myblob.read()  
        file_name = myblob.name  
        temp_file_path = os.path.join(tempfile.gettempdir(), file_name)  
          
        # Ensure the directory exists  
        os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)  
  
        with open(temp_file_path, 'wb') as file_to_write:  
            file_to_write.write(file_content)  
        
        timer_start = datetime.now()  
  
        prompt = "Extract all data."  # Define your prompt  
        json_schema = {}  # Define your JSON schema here  
        ocr_response = process_pdf(file_to_ocr=temp_file_path,  
                                   prompt=prompt,  
                                   json_schema=json_schema)  
        nl_response = get_final_reasoning_from_markdown(ocr_response)  
        classification = 'N/A'  
        try:  
            classification = ocr_response.get('categorization', 'N/A')
        except AttributeError:  
            logging.warning("Cannot find 'categorization' in output schema! Logging it as N/A...")  
        timer_stop = datetime.now()  
        
        # Save in CosmosDB (system requests history)
        logging.info("URI: " + myblob.uri)
        document = {  
            "id": file_name.replace('/', '_').replace('\\', '_').replace('?', '_').replace('#', '_'),  
            "blob_name": file_name,  
            "blob_size": myblob.length,  
            "request_timestamp": timer_start.isoformat(),  
            "total_time_seconds": (timer_stop - timer_start).total_seconds(),  
            "classification": classification,  
            "accuracy": 0,  # Placeholder for accuracy, add actual logic if needed  
            "model_output": nl_response.content,  
            "ocr_response": ocr_response,  
            "nl_response": nl_response.content  
        }  
        container.upsert_item(document)  
        logging.info("Item created in Database.")  
    except Exception as e:  
        logging.error("Error occurred in blob trigger function")  
        logging.error(traceback.format_exc())  
        return None  # Explicitly return None to avoid RuntimeError  
