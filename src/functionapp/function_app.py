import logging
import os
import azure.functions as func
from azure.functions.decorators import FunctionApp
from azure.cosmos import CosmosClient
import traceback
import json
import tempfile
from datetime import datetime
from ai_ocr.chains import get_summary_with_gpt
from ai_ocr.process import run_ocr_and_gpt, initialize_document, update_state

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

        # Initialize the document
        document = initialize_document(file_name, myblob.length, timer_start)

        # Update state when file lands
        document['state']['file_landed'] = True
        document['state']['file_landed_time_seconds'] = (datetime.now() - timer_start).total_seconds()
        container.upsert_item(document)

        try:
            # Start OCR and GPT processing
            prompt = "Extract all data."
            json_schema = {}  # Define your JSON schema here
            ocr_response, gpt_response, processing_times = run_ocr_and_gpt(file_to_ocr=temp_file_path,
                                                             prompt=prompt,
                                                             json_schema=json_schema,
                                                             document=document,
                                                             container=container)
        except Exception as e:
            document['errors'].append(f"OCR/GPT processing error: {str(e)}")
            container.upsert_item(document)
            raise

        try:
            classification = 'N/A'  
            try:  
                classification = ocr_response.categorization  
            except AttributeError:  
                logging.warning("Cannot find 'categorization' in output schema! Logging it as N/A...")  
            
            summary_start_time = datetime.now()
            gpt_summary = get_summary_with_gpt(ocr_response)
            summary_processing_time = (datetime.now() - summary_start_time).total_seconds()
            # Update state after NL processing
            document['state']['gpt_summary_completed'] = True
            document['state']['gpt_summary_time_seconds'] = summary_processing_time
            container.upsert_item(document)
        except Exception as e:
            document['errors'].append(f"NL processing error: {str(e)}")
            container.upsert_item(document)
            raise

        timer_stop = datetime.now()

        # Save final document with complete state
        document['properties'].update({
            "total_time_seconds": (timer_stop - timer_start).total_seconds()
        })
        document['extracted_data'].update({
            "classification": classification,
            "gpt_extraction_output": json.loads(gpt_response),
            "ocr_output": ocr_response,
            "gpt_summary_output": gpt_summary.content
        })
        document['state'].update({
            "processing_completed": True
        })
        container.upsert_item(document)

        logging.info("Item updated in Database.")
    except Exception as e:
        document['errors'].append(f"General error: {str(e)}")
        container.upsert_item(document)
        logging.error("Error occurred in blob trigger function")
        logging.error(traceback.format_exc())
        return None  # Explicitly return None to avoid RuntimeError
