import glob
import json
import os

from langchain_core.output_parsers.json import parse_json_markdown

from ai_ocr.azure.doc_intelligence import get_ocr_results
from ai_ocr.azure.openai_ops import load_image, get_size_of_base64_images
from ai_ocr.chains import get_structured_data
from ai_ocr.model import Config
from ai_ocr.azure.images import extract_images_from_pdf

def process_pdf(file_to_ocr: str, prompt: str, json_schema: str, config: Config = Config()) -> any:
    # Get OCR results
    ocr_result = get_ocr_results(file_to_ocr)
    print(ocr_result.content)
    
    # Extract images from the PDF
    extract_images_from_pdf(file_to_ocr)
    
    # Determine the path for the temporary images
    pdf_path = os.path.dirname(file_to_ocr)
    imgs_path = os.path.join(os.getcwd(), os.getenv("TEMP_IMAGES_OUTDIR", ""))
    imgs = glob.glob(f"{imgs_path}/page*.jpeg")
    
    # Limit images by config
    imgs = imgs[:config.max_images]
    imgs = [load_image(img) for img in imgs]
    
    # Check and reduce images total size if over 20MB
    max_size = config.gpt_vision_limit_mb * 1024 * 1024  # 20MB
    while get_size_of_base64_images(imgs) > max_size:
        imgs.pop()
    
    # Get structured data
    structured = get_structured_data(ocr_result.content, prompt, json_schema, imgs)
    
    # Delete all generated images created after processing
    for img_path in glob.glob(f"{imgs_path}/page*.jpeg"):
        try:
            os.remove(img_path)
            print(f"Deleted image: {img_path}")
        except Exception as e:
            print(f"Error deleting image {img_path}: {e}")
    
    # Parse structured data and return as JSON
    x = parse_json_markdown(structured.content)
    return json.dumps(x)
