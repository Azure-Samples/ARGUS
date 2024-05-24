import glob
import json
import os
from datetime import datetime

from langchain_core.output_parsers.json import parse_json_markdown

from ai_ocr.azure.doc_intelligence import get_ocr_results
from ai_ocr.azure.openai_ops import load_image, get_size_of_base64_images
from ai_ocr.chains import get_structured_data
from ai_ocr.model import Config
from ai_ocr.azure.images import extract_images_from_pdf

def initialize_document(file_name: str, file_size: int, request_timestamp: datetime) -> dict:
    return {
        "id": file_name.replace('/', '__'),
        "properties": {
            "blob_name": file_name,
            "blob_size": file_size,
            "request_timestamp": request_timestamp.isoformat()
        },
        "state": {
            "file_landed": False,
            "ocr_completed": False,
            "gpt_extraction_completed": False,
            "gpt_summary_completed": False,
            "processing_completed": False
        },
        "extracted_data": {
            "classification": 'N/A',
            "accuracy": 0,  # Placeholder for accuracy, add actual logic if needed
            "ocr_output": '',
            "gpt_extraction_output": {},
            "gpt_summary_output": ''
        },
        "errors": []
    }

def update_state(document: dict, container: any, state_name: str, state: bool, processing_time: float = None):
    document['state'][state_name] = state
    if processing_time is not None:
        document['state'][f"{state_name}_time_seconds"] = processing_time
    container.upsert_item(document)

def run_ocr_and_gpt(file_to_ocr: str, prompt: str, json_schema: str, document: dict, container: any, config: Config = Config()) -> (any, dict):
    processing_times = {}

    # Get OCR results
    ocr_start_time = datetime.now()
    ocr_result = get_ocr_results(file_to_ocr)
    ocr_processing_time = (datetime.now() - ocr_start_time).total_seconds()
    processing_times['ocr_processing_time'] = ocr_processing_time
    
    # Update state after OCR processing
    update_state(document, container, 'ocr_completed', True, ocr_processing_time)
    
    # Extract images from the PDF
    extract_images_from_pdf(file_to_ocr)
    
    # Ensure the /tmp/ directory exists
    imgs_path = "/tmp/"
    os.makedirs(imgs_path, exist_ok=True)
    
    # Determine the path for the temporary images
    imgs = glob.glob(f"{imgs_path}/page*.jpeg")
    
    # Limit images by config
    imgs = imgs[:config.max_images]
    imgs = [load_image(img) for img in imgs]
    
    # Check and reduce images total size if over 20MB
    max_size = config.gpt_vision_limit_mb * 1024 * 1024  # 20MB
    while get_size_of_base64_images(imgs) > max_size:
        imgs.pop()
    
    # Get structured data
    gpt_extraction_start_time = datetime.now()
    structured = get_structured_data(ocr_result.content, prompt, json_schema, imgs)
    gpt_extraction_time = (datetime.now() - gpt_extraction_start_time).total_seconds()
    processing_times['gpt_extraction_time'] = gpt_extraction_time
    
    # Update state after GPT extraction
    update_state(document, container, 'gpt_extraction_completed', True, gpt_extraction_time)
    
    # Delete all generated images created after processing
    for img_path in glob.glob(f"{imgs_path}/page*.jpeg"):
        try:
            os.remove(img_path)
            print(f"Deleted image: {img_path}")
        except Exception as e:
            print(f"Error deleting image {img_path}: {e}")
    
    # Parse structured data and return as JSON
    x = parse_json_markdown(structured.content)
    return ocr_result.content, json.dumps(x), processing_times
