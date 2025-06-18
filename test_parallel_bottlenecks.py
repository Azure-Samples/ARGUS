"""
Test script to diagnose parallel processing bottlenecks
"""
import asyncio
import time
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Thread
import os
import sys

# Add the path to import the modules
sys.path.append(os.path.join(os.path.dirname(__file__), 'src', 'containerapp'))

from ai_ocr.azure.doc_intelligence import get_ocr_results
from ai_ocr.chains import get_structured_data

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(threadName)s - %(message)s')
logger = logging.getLogger(__name__)

def test_doc_intelligence_parallel():
    """Test if Document Intelligence can handle parallel requests"""
    
    # Use a sample PDF file path (you'll need to provide this)
    test_file = "demo/default-dataset/Invoice Sample.pdf"
    
    if not os.path.exists(test_file):
        logger.error(f"Test file not found: {test_file}")
        return
    
    def process_single_file(file_path, task_id):
        start_time = time.time()
        logger.info(f"Task {task_id}: Starting Document Intelligence processing")
        
        try:
            result = get_ocr_results(file_path)
            end_time = time.time()
            logger.info(f"Task {task_id}: Completed in {end_time - start_time:.2f} seconds")
            return f"Task {task_id}: Success - {len(result)} characters"
        except Exception as e:
            end_time = time.time()
            logger.error(f"Task {task_id}: Failed in {end_time - start_time:.2f} seconds - {e}")
            return f"Task {task_id}: Failed - {e}"
    
    # Test with 3 parallel requests
    logger.info("=== Testing Document Intelligence Parallel Processing ===")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            future = executor.submit(process_single_file, test_file, i+1)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            logger.info(f"Completed: {result}")
    
    total_time = time.time() - start_time
    logger.info(f"=== Total time for 3 parallel requests: {total_time:.2f} seconds ===")
    
    return results

def test_openai_parallel():
    """Test if OpenAI can handle parallel requests"""
    
    test_content = "This is a test document for parallel processing."
    test_prompt = "Extract key information from this document."
    test_schema = '{"test": "value"}'
    
    def process_single_openai(content, task_id):
        start_time = time.time()
        logger.info(f"OpenAI Task {task_id}: Starting processing")
        
        try:
            result = get_structured_data(content, test_prompt, test_schema)
            end_time = time.time()
            logger.info(f"OpenAI Task {task_id}: Completed in {end_time - start_time:.2f} seconds")
            return f"OpenAI Task {task_id}: Success"
        except Exception as e:
            end_time = time.time()
            logger.error(f"OpenAI Task {task_id}: Failed in {end_time - start_time:.2f} seconds - {e}")
            return f"OpenAI Task {task_id}: Failed - {e}"
    
    # Test with 3 parallel requests
    logger.info("=== Testing OpenAI Parallel Processing ===")
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = []
        for i in range(3):
            future = executor.submit(process_single_openai, test_content, i+1)
            futures.append(future)
        
        results = []
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            logger.info(f"Completed: {result}")
    
    total_time = time.time() - start_time
    logger.info(f"=== Total time for 3 parallel OpenAI requests: {total_time:.2f} seconds ===")
    
    return results

if __name__ == "__main__":
    logger.info("Starting parallel processing diagnostic tests...")
    
    # Test Document Intelligence
    doc_results = test_doc_intelligence_parallel()
    
    # Test OpenAI
    # openai_results = test_openai_parallel()
    
    logger.info("Diagnostic tests completed.")
