import logging, os, json, traceback
import azure.functions as func
from azure.functions.decorators import FunctionApp
from datetime import datetime
from ai_ocr.process import (
    run_ocr_and_gpt, initialize_document, update_state, connect_to_cosmos, write_blob_to_temp_file, process_gpt_summary
)

app = FunctionApp()

@app.blob_trigger(arg_name="myblob", path="myblobcontainer/{name}", connection="AzureWebJobsStorage")
def main(myblob: func.InputStream):
    logging.info(f"Python blob trigger function processed blob \n"
                 f"Name: {myblob.name}\n"
                 f"Blob Size: {myblob.length} bytes")
    try:
        client, container = connect_to_cosmos()
        process_blob(myblob, container)
        logging.info("Item updated in Database.")
    except Exception as e:
        logging.error("Error occurred in blob trigger function")
        logging.error(traceback.format_exc())

def process_blob(myblob: func.InputStream, container):
    temp_file_path = write_blob_to_temp_file(myblob)
    document = initialize_document_data(myblob, temp_file_path, container)
    ocr_response, gpt_response, processing_times = run_ocr_and_gpt_processing(temp_file_path, document, container)
    process_gpt_summary(ocr_response, document, container)
    update_final_document(document, gpt_response, ocr_response, processing_times, container)
    return document

def initialize_document_data(myblob, temp_file_path, container):
    timer_start = datetime.now()
    prompt = "Extract all data."
    json_schema = {}  # Define your JSON schema here
    document = initialize_document(myblob.name, myblob.length, prompt, json_schema, timer_start)
    update_state(document, container, 'file_landed', True, (datetime.now() - timer_start).total_seconds())
    return document

def run_ocr_and_gpt_processing(temp_file_path, document, container):
    try:
        return run_ocr_and_gpt(temp_file_path, document['model_input']['model_prompt'], document['model_input']['example_schema'], document, container)
    except Exception as e:
        document['errors'].append(f"OCR/GPT processing error: {str(e)}")
        update_state(document, container, 'ocr_completed', False)
        raise

def update_final_document(document, gpt_response, ocr_response, processing_times, container):
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    document['extracted_data'].update({
        "gpt_extraction_output": json.loads(gpt_response),
        "ocr_output": ocr_response
    })
    document['state']['processing_completed'] = True
    update_state(document, container, 'processing_completed', True)
