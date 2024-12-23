import logging, shutil
import os
import json
import traceback
import sys
import azure.functions as func
from azure.functions.decorators import FunctionApp
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from ai_ocr.process import (
    run_ocr_processing, run_gpt_extraction, run_gpt_evaluation, run_gpt_summary,
    prepare_images, initialize_document, update_state, connect_to_cosmos, 
    write_blob_to_temp_file, run_gpt_summary, fetch_model_prompt_and_schema, 
    split_pdf_into_subsets
)
from ai_ocr.model import Config

MAX_TIMEOUT = 45*60  # Set timeout duration in seconds

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
                sys.exit(1)
    except Exception as e:
        logging.error("Error occurred in blob trigger function")
        logging.error(traceback.format_exc())
        sys.exit(1)
    print("Function completed successfully.")
    return

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
    
    processing_times = {}
    file_paths = []
    temp_dirs = []
    
    try:
        # Prepare all file paths
        if num_pages and num_pages > 10:
            file_paths = split_pdf_into_subsets(temp_file_path, max_pages_per_subset=10)
        else:
            file_paths = [temp_file_path]

        # Step 1: Run OCR for all files
        ocr_results = []
        total_ocr_time = 0
        for file_path in file_paths:
            ocr_result, ocr_time = run_ocr_processing(file_path, document, data_container)
            ocr_results.append(ocr_result)
            total_ocr_time += ocr_time
            
        processing_times['ocr_processing_time'] = total_ocr_time
        document['extracted_data']['ocr_output'] = '\n'.join(str(result) for result in ocr_results)
        data_container.upsert_item(document)

        # Step 2: Prepare images and run GPT extraction for all files
        extracted_data_list = []
        total_extraction_time = 0
        for file_path in file_paths:
            temp_dir, imgs = prepare_images(file_path, Config())
            temp_dirs.append(temp_dir)
            
            extracted_data, extraction_time = run_gpt_extraction(
                ocr_results[file_paths.index(file_path)],
                document['model_input']['model_prompt'],
                document['model_input']['example_schema'],
                imgs,
                document,
                data_container
            )
            extracted_data_list.append(extracted_data)
            total_extraction_time += extraction_time

        processing_times['gpt_extraction_time'] = total_extraction_time
        merged_extraction = merge_extracted_data(extracted_data_list)
        document['extracted_data']['gpt_extraction_output'] = merged_extraction
        data_container.upsert_item(document)


        # Step 3: Run GPT evaluation for all files
        evaluation_results = []
        total_evaluation_time = 0
        for i, file_path in enumerate(file_paths):
            temp_dir = temp_dirs[i]
            # Using the same prepare_images function that existed before
            _, imgs = prepare_images(file_path, Config())
            
            enriched_data, evaluation_time = run_gpt_evaluation(
                imgs,
                extracted_data_list[i],
                document['model_input']['example_schema'],
                document,
                data_container
            )
            evaluation_results.append(enriched_data)
            total_evaluation_time += evaluation_time

        processing_times['gpt_evaluation_time'] = total_evaluation_time
        merged_evaluation = merge_extracted_data(evaluation_results)
        document['extracted_data']['gpt_extraction_output_with_evaluation'] = merged_evaluation
        data_container.upsert_item(document)

        # Step 4: Process final summary
        run_gpt_summary(ocr_results, document, data_container)
        
        # Final update
        update_final_document(document, merged_extraction, ocr_results, 
                            merged_evaluation, processing_times, data_container)
        
        return document
        
    except Exception as e:
        document['errors'].append(f"Processing error: {str(e)}")
        document['state']['processing_completed'] = False
        data_container.upsert_item(document)
        raise e
    
    finally:
        # Clean up temporary directories and files
        for temp_dir in temp_dirs:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                print(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                print(f"Error cleaning up temporary directory {temp_dir}: {e}")
        
        # Clean up split PDF files if they were created
        if num_pages and num_pages > 10:
            for file_path in file_paths:
                try:
                    os.remove(file_path)
                    print(f"Cleaned up split PDF: {file_path}")
                except Exception as e:
                    print(f"Error cleaning up split PDF {file_path}: {e}")

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

def merge_extracted_data(gpt_responses):
    merged_data = {}
    for response in gpt_responses:
        for key, value in response.items():
            if key in merged_data:
                if isinstance(value, list):
                    merged_data[key].extend(value)
                else:
                    # Decide how to handle non-list duplicates - keeping latest value
                    merged_data[key] = value
            else:
                if isinstance(value, list):
                    merged_data[key] = value.copy()
                else:
                    merged_data[key] = value
    return merged_data

def update_final_document(document, gpt_response, ocr_response, evaluation_result, processing_times, data_container):
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    
    document['extracted_data'].update({
        "gpt_extraction_output_with_evaluation": evaluation_result,
        "gpt_extraction_output": gpt_response,
        "ocr_output": '\n'.join(str(result) for result in ocr_response)
    })
    
    document['state']['processing_completed'] = True
    update_state(document, data_container, 'processing_completed', True)