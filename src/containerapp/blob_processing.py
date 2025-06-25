"""
Blob processing functionality for ARGUS Container App
"""
import asyncio
import copy
import logging
import os
import shutil
import threading
import traceback
from datetime import datetime
from typing import Dict, Any

from models import BlobInputStream
from dependencies import (
    get_blob_service_client, get_data_container, get_global_executor, 
    get_global_processing_semaphore
)

# Import processing functions
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'functionapp'))
from ai_ocr.process import (
    run_ocr_processing, run_gpt_extraction, run_gpt_evaluation, run_gpt_summary,
    prepare_images, initialize_document, update_state, 
    write_blob_to_temp_file, fetch_model_prompt_and_schema, 
    split_pdf_into_subsets
)
from ai_ocr.model import Config

logger = logging.getLogger(__name__)


def create_blob_input_stream(blob_url: str) -> BlobInputStream:
    """Create a BlobInputStream from a blob URL"""
    try:
        # Parse blob URL to get container and blob name
        # Format: https://accountname.blob.core.windows.net/container/blob
        url_parts = blob_url.replace('https://', '').split('/')
        account_name = url_parts[0].split('.')[0]
        container_name = url_parts[1]
        blob_name = '/'.join(url_parts[2:])
        
        # Get blob client
        blob_service_client = get_blob_service_client()
        blob_client = blob_service_client.get_blob_client(
            container=container_name,
            blob=blob_name
        )
        
        # Get blob properties
        blob_properties = blob_client.get_blob_properties()
        blob_size = blob_properties.size
        
        return BlobInputStream(blob_name, blob_size, blob_client)
        
    except Exception as e:
        logger.error(f"Error creating blob input stream: {e}")
        raise


def process_blob_async(blob_input_stream: BlobInputStream, data_container):
    """Process blob asynchronously - same logic as original function"""
    thread_id = threading.current_thread().ident
    
    try:
        logger.info(f"[Thread-{thread_id}] Starting blob processing: {blob_input_stream.name}")
        
        start_time = datetime.now()
        process_blob(blob_input_stream, data_container)
        end_time = datetime.now()
        
        logger.info(f"[Thread-{thread_id}] Successfully processed blob: {blob_input_stream.name} in {(end_time - start_time).total_seconds():.2f}s")
        
    except Exception as e:
        logger.error(f"[Thread-{thread_id}] Error processing blob {blob_input_stream.name}: {e}")
        logger.error(traceback.format_exc())
        raise


def handle_timeout_error_async(blob_input_stream: BlobInputStream, data_container):
    """Handle timeout error - same logic as original function"""
    document_id = blob_input_stream.name.replace('/', '__')
    try:
        document = data_container.read_item(item=document_id, partition_key={})
        logger.warning(f"Timeout occurred for document: {document_id}")
    except Exception as e:
        logger.error(f"Error handling timeout for document {document_id}: {e}")


async def process_blob_event(blob_url: str, event_data: Dict[str, Any]):
    """Process a single blob event in the background with concurrency control"""
    try:
        # Create blob input stream
        blob_input_stream = create_blob_input_stream(blob_url)
        
        logger.info(f"Processing blob event for: {blob_input_stream.name}")
        
        # Use semaphore to control concurrency
        global_processing_semaphore = get_global_processing_semaphore()
        global_executor = get_global_executor()
        data_container = get_data_container()
        
        if global_processing_semaphore:
            async with global_processing_semaphore:
                logger.info(f"Acquired semaphore for processing: {blob_input_stream.name}")
                
                # Use global ThreadPoolExecutor for processing
                if global_executor:
                    # Run in executor but await the result to maintain semaphore control
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        global_executor,
                        process_blob_async,
                        blob_input_stream,
                        data_container
                    )
                    logger.info(f"Completed processing for: {blob_input_stream.name}")
                else:
                    logger.error("Global executor not available")
        else:
            logger.error("Global processing semaphore not available")
                
    except Exception as e:
        logger.error(f"Error in background blob processing: {e}")
        logger.error(traceback.format_exc())


def initialize_document_data(blob_name: str, temp_file_path: str, num_pages: int, file_size: int, data_container):
    """Initialize document data for processing"""
    timer_start = datetime.now()
    
    # Determine dataset type from blob name
    logger.info(f"Processing blob with name: {blob_name}")
    
    # Handle blob path parsing
    blob_parts = blob_name.split('/')
    if len(blob_parts) < 2:
        # If no folder structure, default to 'default-dataset'
        logger.warning(f"Blob name {blob_name} doesn't contain folder structure, defaulting to 'default-dataset'")
        dataset_type = 'default-dataset'
    else:
        dataset_type = blob_parts[0]  # Take the first part as dataset type
    
    logger.info(f"Using dataset type: {dataset_type}")
    
    prompt, json_schema, max_pages_per_chunk, processing_options = fetch_model_prompt_and_schema(dataset_type)
    if prompt is None or json_schema is None:
        raise ValueError("Failed to fetch model prompt and schema from configuration.")
    
    document = initialize_document(blob_name, file_size, num_pages, prompt, json_schema, timer_start, dataset_type, max_pages_per_chunk, processing_options)
    update_state(document, data_container, 'file_landed', True, (datetime.now() - timer_start).total_seconds())
    return document


def merge_extracted_data(gpt_responses):
    """
    Merges extracted data from multiple GPT responses into a single result.
    
    This function properly handles different data types:
    - Lists: concatenated together
    - Strings: joined with spaces and cleaned up
    - Numbers: summed together
    - Dicts: recursively merged
    """
    if not gpt_responses:
        return {}
    
    # Start with the first response as base
    merged_data = copy.deepcopy(gpt_responses[0]) if gpt_responses else {}
    
    # Merge remaining responses
    for response in gpt_responses[1:]:
        merged_data = _deep_merge_data(merged_data, response)
    
    return merged_data


def _deep_merge_data(base_data, new_data):
    """
    Deep merge two data dictionaries with intelligent type handling.
    """
    if not isinstance(base_data, dict) or not isinstance(new_data, dict):
        return new_data if new_data else base_data
    
    result = copy.deepcopy(base_data)
    
    for key, value in new_data.items():
        if key not in result:
            result[key] = copy.deepcopy(value)
        else:
            existing_value = result[key]
            
            # Handle different data types appropriately
            if isinstance(existing_value, list) and isinstance(value, list):
                # Concatenate lists
                result[key] = existing_value + value
            elif isinstance(existing_value, str) and isinstance(value, str):
                # Join strings with space, clean up multiple spaces
                combined = f"{existing_value} {value}".strip()
                result[key] = " ".join(combined.split())  # Clean up multiple spaces
            elif isinstance(existing_value, (int, float)) and isinstance(value, (int, float)):
                # Sum numbers
                result[key] = existing_value + value
            elif isinstance(existing_value, dict) and isinstance(value, dict):
                # Recursively merge dictionaries
                result[key] = _deep_merge_data(existing_value, value)
            else:
                # For other types or type mismatches, prefer non-empty values
                if value:  # Use new value if it's truthy
                    result[key] = value
                # Otherwise keep existing value
    
    return result


def update_final_document(document, gpt_response, ocr_response, evaluation_result, processing_times, data_container):
    """Update the final document with all processing results"""
    timer_stop = datetime.now()
    document['properties']['total_time_seconds'] = (timer_stop - datetime.fromisoformat(document['properties']['request_timestamp'])).total_seconds()
    
    document['extracted_data'].update({
        "gpt_extraction_output_with_evaluation": evaluation_result,
        "gpt_extraction_output": gpt_response,
        "ocr_output": '\n'.join(str(result) for result in ocr_response)
    })
    
    document['state']['processing_completed'] = True
    update_state(document, data_container, 'processing_completed', True)


def cleanup_temp_resources(temp_dirs, file_paths, temp_file_path):
    """
    Clean up temporary directories and files created during processing.
    Ensures proper resource cleanup even if processing fails.
    """
    
    # Clean up temporary directories
    for temp_dir in temp_dirs:
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
                logger.info(f"Cleaned up temporary directory: {temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory {temp_dir}: {e}")
    
    # Clean up split PDF files (but not the original temp file)
    for file_path in file_paths:
        try:
            if file_path and file_path != temp_file_path and os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up split file: {file_path}")
        except Exception as e:
            logger.warning(f"Failed to clean up split file {file_path}: {e}")
    
    # Clean up the main temporary file
    try:
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)
            logger.info(f"Cleaned up main temp file: {temp_file_path}")
    except Exception as e:
        logger.warning(f"Failed to clean up main temp file {temp_file_path}: {e}")


def process_blob(blob_input_stream: BlobInputStream, data_container):
    """Process a blob for OCR and data extraction (adapted for container app)"""
    overall_start_time = datetime.now()
    temp_file_path, num_pages, file_size = write_blob_to_temp_file(blob_input_stream)
    logger.info("processing blob")
    document = initialize_document_data(blob_input_stream.name, temp_file_path, num_pages, file_size, data_container)
    
    processing_times = {}
    file_paths = []
    temp_dirs = []
    
    try:
        # Get processing options from document
        processing_options = document.get('processing_options', {
            "include_ocr": True,
            "include_images": True,
            "enable_summary": True,
            "enable_evaluation": True
        })
        
        logger.info(f"Processing options: OCR={processing_options.get('include_ocr', True)}, "
                   f"Images={processing_options.get('include_images', True)}, "
                   f"Summary={processing_options.get('enable_summary', True)}, "
                   f"Evaluation={processing_options.get('enable_evaluation', True)}")
        
        max_pages_per_chunk = document['model_input'].get('max_pages_per_chunk', 10)
        
        # Validate chunk size to prevent system overload
        if max_pages_per_chunk < 1:
            logger.warning(f"Invalid max_pages_per_chunk: {max_pages_per_chunk}, using default of 10")
            max_pages_per_chunk = 10
        elif max_pages_per_chunk > 50:  # Reasonable upper limit
            logger.warning(f"Large max_pages_per_chunk: {max_pages_per_chunk}, consider reducing for better performance")
        
        if num_pages and num_pages > max_pages_per_chunk:
            file_paths = split_pdf_into_subsets(temp_file_path, max_pages_per_subset=max_pages_per_chunk)
            logger.info(f"Split {num_pages} pages into {len(file_paths)} chunks of max {max_pages_per_chunk} pages each")
        else:
            file_paths = [temp_file_path]
            logger.info(f"Processing single file with {num_pages} pages (no chunking needed)")

        # Step 1: Run OCR for all files (conditional - only if OCR text will be used)
        ocr_results = []
        total_ocr_time = 0
        
        if processing_options.get('include_ocr', True):
            logger.info(f"Starting OCR processing for {len(file_paths)} chunks")
            for i, file_path in enumerate(file_paths):
                logger.info(f"Processing OCR for chunk {i+1}/{len(file_paths)}")
                ocr_result, ocr_time = run_ocr_processing(file_path, document, data_container, None, update_state=False)
                ocr_results.append(ocr_result)
                total_ocr_time += ocr_time
                
            processing_times['ocr_processing_time'] = total_ocr_time
            document['extracted_data']['ocr_output'] = '\n'.join(str(result) for result in ocr_results)
            update_state(document, data_container, 'ocr_completed', True, total_ocr_time)
            data_container.upsert_item(document)
            logger.info(f"Completed OCR processing for all chunks in {total_ocr_time:.2f}s")
        else:
            logger.info("Skipping OCR processing (OCR text not needed for GPT extraction)")
            ocr_results = [""] * len(file_paths)
            processing_times['ocr_processing_time'] = 0
            document['extracted_data']['ocr_output'] = ""
            update_state(document, data_container, 'ocr_skipped', True, 0)
            data_container.upsert_item(document)

        # Step 2: GPT extraction
        logger.info(f"Starting GPT extraction for {len(file_paths)} chunks")
        extracted_data_list = []
        total_extraction_time = 0
        image_cache = {}
        
        for i, file_path in enumerate(file_paths):
            logger.info(f"Processing GPT extraction for chunk {i+1}/{len(file_paths)}")
            
            if processing_options.get('include_images', True):
                temp_dir, imgs = prepare_images(file_path, Config())
                temp_dirs.append(temp_dir)
                image_cache[i] = imgs
            else:
                imgs = []
                image_cache[i] = []
            
            ocr_text_for_extraction = ocr_results[i] if processing_options.get('include_ocr', True) else ""
            
            if not ocr_text_for_extraction and not imgs:
                logger.error("No input provided to GPT extraction - both OCR text and images are empty!")
                raise ValueError("Cannot perform GPT extraction without either OCR text or images")
            
            extracted_data, extraction_time = run_gpt_extraction(
                ocr_text_for_extraction,
                document['model_input']['model_prompt'],
                document['model_input']['example_schema'],
                imgs,
                document,
                data_container,
                None,
                update_state=False
            )
            extracted_data_list.append(extracted_data)
            total_extraction_time += extraction_time

        processing_times['gpt_extraction_time'] = total_extraction_time
        
        # Create page range structure instead of merging
        if len(extracted_data_list) > 1:
            structured_extraction = create_page_range_structure(
                extracted_data_list, file_paths, max_pages_per_chunk
            )
        else:
            structured_extraction = extracted_data_list[0] if extracted_data_list else {}
            
        document['extracted_data']['gpt_extraction_output'] = structured_extraction
        update_state(document, data_container, 'gpt_extraction_completed', True, total_extraction_time)
        data_container.upsert_item(document)

        # Step 3: GPT evaluation (conditional)
        total_evaluation_time = 0
        if processing_options.get('enable_evaluation', True):
            logger.info(f"Starting GPT evaluation for {len(file_paths)} chunks")
            evaluation_results = []
            for i, file_path in enumerate(file_paths):
                imgs = image_cache.get(i, [])
                
                enriched_data, evaluation_time = run_gpt_evaluation(
                    imgs,
                    extracted_data_list[i],
                    document['model_input']['example_schema'],
                    document,
                    data_container,
                    None,
                    update_state=False
                )
                evaluation_results.append(enriched_data)
                total_evaluation_time += evaluation_time

            processing_times['gpt_evaluation_time'] = total_evaluation_time
            
            if len(evaluation_results) > 1:
                structured_evaluation = create_page_range_evaluations(
                    evaluation_results, file_paths, max_pages_per_chunk
                )
            else:
                structured_evaluation = evaluation_results[0] if evaluation_results else {}
                
            document['extracted_data']['gpt_extraction_output_with_evaluation'] = structured_evaluation
            update_state(document, data_container, 'gpt_evaluation_completed', True, total_evaluation_time)
        else:
            structured_evaluation = {}
            document['extracted_data']['gpt_extraction_output_with_evaluation'] = structured_evaluation
            update_state(document, data_container, 'gpt_evaluation_skipped', True, 0)
            processing_times['gpt_evaluation_time'] = 0

        # Step 4: Summary (conditional)
        summary_time = 0
        if processing_options.get('enable_summary', True):
            logger.info("Starting GPT summary processing")
            combined_ocr_text = '\n'.join(str(result) for result in ocr_results)
            summary_data, summary_time = run_gpt_summary(combined_ocr_text, document, data_container, None, update_state=False)
            
            document['extracted_data']['classification'] = summary_data['classification']
            document['extracted_data']['gpt_summary_output'] = summary_data['gpt_summary_output']
            update_state(document, data_container, 'gpt_summary_completed', True, summary_time)
        else:
            document['extracted_data']['classification'] = ""
            document['extracted_data']['gpt_summary_output'] = ""
            update_state(document, data_container, 'gpt_summary_skipped', True, 0)
        
        # Final update
        overall_end_time = datetime.now()
        total_processing_time = (overall_end_time - overall_start_time).total_seconds()
        
        logger.info(f"Processing completed for {blob_input_stream.name}")
        logger.info(f"Total time: {total_processing_time:.2f}s | OCR: {processing_times['ocr_processing_time']:.2f}s | "
                   f"Extraction: {processing_times['gpt_extraction_time']:.2f}s | "
                   f"Evaluation: {processing_times.get('gpt_evaluation_time', 0):.2f}s | Summary: {summary_time:.2f}s")
        
        update_final_document(document, document['extracted_data']['gpt_extraction_output'], ocr_results, 
                            document['extracted_data']['gpt_extraction_output_with_evaluation'], processing_times, data_container)
        
        return document
        
    except Exception as e:
        logger.error(f"Processing error in process_blob: {str(e)}")
        document['errors'].append(f"Processing error: {str(e)}")
        document['state']['processing_completed'] = False
        
        # Mark incomplete steps as failed
        if processing_options.get('include_ocr', True) and 'ocr_processing_time' not in processing_times:
            update_state(document, data_container, 'ocr_completed', False)
        if 'gpt_extraction_time' not in processing_times:
            update_state(document, data_container, 'gpt_extraction_completed', False)
        if processing_options.get('enable_evaluation', True) and 'gpt_evaluation_time' not in processing_times:
            update_state(document, data_container, 'gpt_evaluation_completed', False)
        if processing_options.get('enable_summary', True) and summary_time == 0:
            update_state(document, data_container, 'gpt_summary_completed', False)
        
        data_container.upsert_item(document)
        raise e
    finally:
        cleanup_temp_resources(temp_dirs, file_paths, temp_file_path)


def create_page_range_structure(data_list, file_paths, max_pages_per_chunk):
    """
    Create a structured JSON with page ranges instead of merging chunks.
    
    Args:
        data_list: List of extracted data from each chunk
        file_paths: List of file paths for each chunk
        max_pages_per_chunk: Maximum pages per chunk setting
    
    Returns:
        Dict with page range keys like {"pages_1-10": {chunk_data}, "pages_11-20": {chunk_data}, ...}
    """
    if not data_list:
        return {}
    
    # If there's only one chunk, return it with a single page range
    if len(data_list) == 1:
        return {"pages_1-all": data_list[0]}
    
    # Multiple chunks - create page range structure
    structured_data = {}
    
    for i, (data, file_path) in enumerate(zip(data_list, file_paths)):
        # Parse page range from file_path if it contains subset information
        if "_subset_" in file_path:
            # Format: originalfile_subset_0_9.pdf -> pages_1-10
            parts = file_path.split("_subset_")
            if len(parts) == 2:
                page_part = parts[1].replace(".pdf", "")
                start_end = page_part.split("_")
                if len(start_end) == 2:
                    try:
                        start_page = int(start_end[0]) + 1  # Convert to 1-indexed
                        end_page = int(start_end[1]) + 1    # Convert to 1-indexed
                        page_key = f"pages_{start_page}-{end_page}"
                        structured_data[page_key] = data
                        continue
                    except ValueError:
                        pass
        
        # Fallback: calculate page range from chunk index and max_pages_per_chunk
        chunk_start = i * max_pages_per_chunk + 1
        chunk_end = (i + 1) * max_pages_per_chunk
        page_key = f"pages_{chunk_start}-{chunk_end}"
        structured_data[page_key] = data
    
    return structured_data


def create_page_range_evaluations(evaluation_list, file_paths, max_pages_per_chunk):
    """
    Create a structured JSON with page ranges for evaluations.
    Uses the same logic as create_page_range_structure but for evaluation data.
    
    Returns:
        Dict with page range keys like {"pages_1-10": {evaluation_data}, ...}
    """
    # Use the same logic as create_page_range_structure
    return create_page_range_structure(evaluation_list, file_paths, max_pages_per_chunk)
