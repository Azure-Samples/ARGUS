import logging, os, json, traceback, sys
import azure.functions as func
from azure.functions.decorators import FunctionApp
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from ai_ocr.process import (
    run_ocr_and_gpt, initialize_document, update_state, connect_to_cosmos, write_blob_to_temp_file, process_gpt_summary, fetch_model_prompt_and_schema
)

MAX_TIMEOUT = 15*60  # Set your desired timeout duration here(in seconds)

app = FunctionApp()

@app.blob_trigger(arg_name="myblob", path="datasets/{name}", connection="AzureWebJobsStorage")
def main(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Blob Size: {myblob.length} bytes")
    try:
        data_container, conf_container = connect_to_cosmos()
        with ThreadPoolExecutor() as executor:
            future = executor.submit(process_blob, myblob, data_container)
            try:
                future.result(timeout=MAX_TIMEOUT) 
                logging.info("Item updated in Database.")
            except FuturesTimeoutError:
                logging.error("Function ran out of time.")
                handle_timeout_error(myblob, data_container)
                sys.exit(1)  # Exit with error
    except Exception as e:
        logging.error("Error occurred in blob trigger function")
        logging.error(traceback.format_exc())
        sys.exit(1)  # Exit with error

def handle_timeout_error(myblob, data_container):
    document_id = myblob.name.replace('/', '__')
    try:
        document = data_container.read_item(item=document_id, partition_key={})
    except Exception as e:
        logging.error(f"Failed to read item from Cosmos DB: {str(e)}")
        document = initialize_document(myblob.name, myblob.length, "", "", datetime.now())
    
    document['errors'].append("Function ran out of time")
    document['state']['processing_completed'] = False
    update_state(document, data_container, 'processing_completed', False)
    try:
        data_container.upsert_item(document)
        logging.info(f"Updated document {document_id} with timeout error.")
    except Exception as e:
        logging.error(f"Failed to upsert item to Cosmos DB: {str(e)}")
        

def process_blob(myblob: func.InputStream, data_container):
    temp_file_path, num_pages, file_size = write_blob_to_temp_file(myblob)
    document = initialize_document_data(myblob, temp_file_path, num_pages, file_size, data_container)
    ocr_response, gpt_response, processing_times = run_ocr_and_gpt_processing(temp_file_path, document, data_container)
    process_gpt_summary(ocr_response, document, data_container)
    update_final_document(document, gpt_response, ocr_response, processing_times, data_container)
    return document


def initialize_document_data(myblob, temp_file_path, num_pages, file_size, data_container):
    timer_start = datetime.now()
    
    # Determine dataset type from blob name
    dataset_type = myblob.name.split('/')[1]
    
    prompt, json_schema = fetch_model_prompt_and_schema(dataset_type)
    if prompt is None or json_schema is None:
        raise ValueError("Failed to fetch model prompt and schema from configuration.")
    
    document = initialize_document(myblob.name, file_size, num_pages, prompt, json_schema, timer_start)
    update_state(document, data_container, 'file_landed', True, (datetime.now() - timer_start).total_seconds())
    return document

def run_ocr_and_gpt_processing(temp_file_path, document, data_container):
    try:
        return run_ocr_and_gpt(temp_file_path, document['model_input']['model_prompt'], 
                               document['model_input']['example_schema'], document, data_container)
    except Exception as e:
        document['errors'].append(f"OCR/GPT processing error: {str(e)}")
        update_state(document, data_container, 'ocr_completed', False)
        sys.exit(1) 
        raise

def update_final_document(document, gpt_response, ocr_response, processing_times, data_container):
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    document['extracted_data'].update({
        "gpt_extraction_output": json.loads(gpt_response),
        "ocr_output": ocr_response
    })
    document['state']['processing_completed'] = True
    update_state(document, data_container, 'processing_completed', True)
