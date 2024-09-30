import logging, os, json, traceback, sys
import azure.functions as func
from azure.functions.decorators import FunctionApp
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from ai_ocr.process import (
    run_ocr_and_gpt, initialize_document, update_state, connect_to_cosmos, write_blob_to_temp_file, process_gpt_summary, fetch_model_prompt_and_schema, split_pdf_into_subsets
)

MAX_TIMEOUT = 15*60  # Set your desired timeout duration here(in seconds)

app = FunctionApp()

@app.blob_trigger(arg_name="myblob", path="datasets/{name}", connection="AzureWebJobsStorage__accountName")
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
    print("processing blob")
    document = initialize_document_data(myblob, temp_file_path, num_pages, file_size, data_container)
    if num_pages and num_pages > 10:
        # Split the PDF into subsets
        subset_paths = split_pdf_into_subsets(temp_file_path, max_pages_per_subset=10)
        # Initialize empty results
        combined_ocr_response = []
        combined_gpt_response = []
        combined_evaluation_result = []
        processing_times = {}
        # Process each subset
        for subset_path in subset_paths:
            ocr_response, gpt_response, evaluation_result, subset_processing_times = run_ocr_and_gpt_processing(subset_path, document, data_container)
            # Append results
            combined_ocr_response.append(ocr_response)
            combined_gpt_response.append(json.loads(gpt_response))
            combined_evaluation_result.append(json.loads(evaluation_result))
            # Sum up processing times
            for key, value in subset_processing_times.items():
                processing_times[key] = processing_times.get(key, 0) + value
            # Delete the subset file after processing
            os.remove(subset_path)
        # Combine results
        ocr_response = combined_ocr_response
        gpt_response = combined_gpt_response
        evaluation_result = combined_evaluation_result
    else:
        ocr_response, gpt_response, evaluation_result, processing_times = run_ocr_and_gpt_processing(temp_file_path, document, data_container)
    process_gpt_summary(ocr_response, document, data_container)
    update_final_document(document, gpt_response, ocr_response, evaluation_result, processing_times, data_container)
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


def merge_extracted_data(gpt_responses):
    merged_data = {}
    for response in gpt_responses:
        for key, value in response.items():
            if key in merged_data:
                if isinstance(value, list):
                    merged_data[key].extend(value)
                else:
                    # Decide how to handle non-list duplicates
                    merged_data[key] = value  # Overwrite or append as needed
            else:
                if isinstance(value, list):
                    merged_data[key] = value.copy()
                else:
                    merged_data[key] = value
    return merged_data


def update_final_document(document, gpt_response, ocr_response, evaluation_result, processing_times, data_container):
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    if isinstance(gpt_response, list):
        merged_gpt_response = merge_extracted_data(gpt_response)
        merged_evaluation_result = merge_extracted_data(evaluation_result)
    else:
        merged_gpt_response = gpt_response
        merged_evaluation_result = evaluation_result
    document['extracted_data'].update({
        "gpt_extraction_output_with_evaluation": merged_evaluation_result,
        "gpt_extraction_output": merged_gpt_response,
        "ocr_output": ocr_response
    })
    document['state']['processing_completed'] = True
    update_state(document, data_container, 'processing_completed', True)

