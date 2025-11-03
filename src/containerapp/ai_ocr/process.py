import glob, logging, json, os, sys
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path
import io, uuid, shutil, tempfile

from datetime import datetime
import tempfile 
from azure.identity import DefaultAzureCredential
from azure.cosmos import CosmosClient, exceptions
from azure.core.exceptions import ResourceNotFoundError
from PyPDF2 import PdfReader, PdfWriter

def safe_parse_json(content: str) -> dict:
    """
    Safely parse JSON content with multiple fallback strategies and truncation detection
    """
    import re
    
    try:
        # First try direct parsing
        return json.loads(content)
    except json.JSONDecodeError as e:
        logging.warning(f"Initial JSON parse failed: {e}")
        
        # Check for signs of truncation before attempting cleanup
        content_stripped = content.strip()
        is_likely_truncated = False
        truncation_indicators = []
        
        # Check for bracket/brace imbalance (strong indicator of truncation)
        open_braces = content_stripped.count('{')
        close_braces = content_stripped.count('}')
        open_brackets = content_stripped.count('[')
        close_brackets = content_stripped.count(']')
        
        if open_braces != close_braces:
            is_likely_truncated = True
            truncation_indicators.append(f"Unbalanced braces: {open_braces} open, {close_braces} close")
        
        if open_brackets != close_brackets:
            is_likely_truncated = True
            truncation_indicators.append(f"Unbalanced brackets: {open_brackets} open, {close_brackets} close")
        
        # Check if content ends abruptly without proper JSON closure
        if content_stripped and not (content_stripped.endswith('}') or content_stripped.endswith(']')):
            is_likely_truncated = True
            truncation_indicators.append(f"Content ends abruptly: '{content_stripped[-50:]}'")
        
        # Check for incomplete string at the end (common in truncation)
        if content_stripped.endswith('"') and content_stripped.count('"') % 2 != 0:
            is_likely_truncated = True
            truncation_indicators.append("Incomplete string at end")
        
        if is_likely_truncated:
            logging.error(f"JSON appears to be truncated. Indicators: {'; '.join(truncation_indicators)}")
            return {
                "error": "JSON response appears to be truncated",
                "error_type": "likely_truncation",
                "parsing_error": str(e),
                "raw_content": content[:1000],
                "extraction_failed": True,
                "truncation_indicators": truncation_indicators,
                "user_action_required": "The response was likely truncated due to token limits.",
                "recommendations": [
                    "Reduce the 'max_pages_per_chunk' parameter to process smaller document chunks",
                    "Simplify the JSON schema to reduce output complexity",
                    "Use a more concise system prompt",
                    "Consider processing the document in smaller sections"
                ]
            }
        
        # Define multiple cleanup strategies
        def basic_cleanup(text):
            """Basic markdown and whitespace cleanup"""
            text = text.strip()
            if text.startswith('```json'):
                text = text[7:]
            elif text.startswith('```'):
                text = text[3:]
            if text.endswith('```'):
                text = text[:-3]
            return text.strip()
        
        def extract_json_object(text):
            """Extract just the JSON object from surrounding text"""
            start_idx = text.find('{')
            end_idx = text.rfind('}')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return text[start_idx:end_idx + 1]
            return text
        
        def extract_json_array(text):
            """Extract just the JSON array from surrounding text"""
            start_idx = text.find('[')
            end_idx = text.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                return text[start_idx:end_idx + 1]
            return text
        
        def fix_common_json_issues(text):
            """Fix common JSON formatting issues"""
            # Fix single quotes to double quotes
            text = re.sub(r"'(\w+)':", r'"\1":', text)  # Property names
            text = re.sub(r': \'([^\']*?)\'(?=\s*[,}\]])', r': "\1"', text)  # String values
            
            # Fix trailing commas
            text = re.sub(r',(\s*[}\]])', r'\1', text)
            
            # Fix missing quotes around property names
            text = re.sub(r'(\w+):', r'"\1":', text)
            
            # Fix missing quotes around string values (simple heuristic)
            text = re.sub(r': ([A-Za-z][A-Za-z0-9\s]*?)(?=\s*[,}\]])', r': "\1"', text)
            
            return text
        
        # Try multiple cleanup strategies in order
        cleanup_strategies = [
            basic_cleanup,
            lambda x: extract_json_object(basic_cleanup(x)),
            lambda x: extract_json_array(basic_cleanup(x)),
            lambda x: fix_common_json_issues(extract_json_object(basic_cleanup(x))),
            lambda x: fix_common_json_issues(extract_json_array(basic_cleanup(x))),
        ]
        
        for i, strategy in enumerate(cleanup_strategies):
            try:
                cleaned_content = strategy(content)
                if cleaned_content and cleaned_content != content:
                    result = json.loads(cleaned_content)
                    logging.info(f"Successfully parsed JSON using cleanup strategy {i+1}")
                    return result
            except (json.JSONDecodeError, Exception) as cleanup_error:
                logging.debug(f"Cleanup strategy {i+1} failed: {cleanup_error}")
                continue
        
        # If all else fails, return an error structure
        logging.error(f"All JSON parsing strategies failed. Content: {content[:500]}...")
        return {
            "error": "Failed to parse JSON response after multiple cleanup attempts",
            "error_type": "json_parse_error",
            "raw_content": content[:1000],
            "parsing_error": str(e),
            "extraction_failed": True,
            "user_action_required": "GPT returned malformed JSON that could not be repaired.",
            "recommendations": [
                "Try running the extraction again (temporary GPT formatting issue)",
                "Reduce document complexity if the issue persists",
                "Simplify the JSON schema to reduce formatting complexity",
                "Check if the system prompt is causing formatting conflicts"
            ]
        }

from ai_ocr.azure.doc_intelligence import get_ocr_results as get_azure_ocr_results
from ai_ocr.azure.mistral_doc_intelligence import get_ocr_results as get_mistral_ocr_results
from ai_ocr.azure.openai_ops import load_image, get_size_of_base64_images
from ai_ocr.chains import get_structured_data, get_summary_with_gpt, perform_gpt_evaluation_and_enrichment
from ai_ocr.model import Config
from ai_ocr.azure.images import convert_pdf_into_image

def connect_to_cosmos():
    endpoint = os.environ['COSMOS_URL']
    database_name = os.environ['COSMOS_DB_NAME']
    container_name = os.environ['COSMOS_DOCUMENTS_CONTAINER_NAME']
    client = CosmosClient(endpoint, DefaultAzureCredential())
    database = client.get_database_client(database_name)
    docs_container = database.get_container_client(container_name)
    conf_container = database.get_container_client(os.environ['COSMOS_CONFIG_CONTAINER_NAME'])

    return docs_container, conf_container

def initialize_document(file_name: str, file_size: int, num_pages:int, prompt: str, json_schema: str, request_timestamp: datetime, dataset: str = None, max_pages_per_chunk: int = 10, processing_options: dict = None) -> dict:
    # Extract dataset from file_name if not provided
    if dataset is None:
        blob_parts = file_name.split('/')
        if len(blob_parts) >= 2:
            dataset = blob_parts[0]
        else:
            dataset = 'default-dataset'
    
    # Set default processing options if not provided
    if processing_options is None:
        processing_options = {
            "include_ocr": True,
            "include_images": True,
            "enable_summary": True,
            "enable_evaluation": True
        }
    
    return {
        "id": file_name.replace('/', '__'),
        "dataset": dataset,
        "properties": {
            "blob_name": file_name,
            "blob_size": file_size,
            "request_timestamp": request_timestamp.isoformat(),
            "num_pages": num_pages,
            "dataset": dataset
        },
        "state": {
            "file_landed": False,
            "ocr_completed": False,
            "gpt_extraction_completed": False,
            "gpt_evaluation_completed": False,
            "gpt_summary_completed": False,
            "processing_completed": False
        },
        "extracted_data": {
            "ocr_output": '',
            "gpt_extraction_output": {},
            "gpt_extraction_output_with_evaluation": {},
            "gpt_summary_output": ''
        },
        "model_input":{
            "model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME"),
            "model_prompt": prompt,
            "example_schema": json_schema,
            "max_pages_per_chunk": max_pages_per_chunk
        },
        "processing_options": processing_options,
        "errors": []
    }

def update_state(document: dict, container: any, state_name: str, state: bool, processing_time: float = None):
    document['state'][state_name] = state
    if processing_time is not None:
        document['state'][f"{state_name}_time_seconds"] = processing_time
    container.upsert_item(document)

def write_blob_to_temp_file(myblob):
    file_content = myblob.read()
    file_name = myblob.name
    temp_file_path = os.path.join(tempfile.gettempdir(), file_name)
    os.makedirs(os.path.dirname(temp_file_path), exist_ok=True)
    with open(temp_file_path, 'wb') as file_to_write:
        file_to_write.write(file_content)
    # Get the size of the file
    file_size = os.path.getsize(temp_file_path)
    # If file is PDF calculate the number of pages in the PDF   
    if file_name.lower().endswith('.pdf'):
        pdf_reader = PdfReader(temp_file_path)
        number_of_pages = len(pdf_reader.pages)
    else:
        number_of_pages = None

    return temp_file_path, number_of_pages, file_size

def split_pdf_into_subsets(pdf_path, max_pages_per_subset=10):
    pdf_reader = PdfReader(pdf_path)
    total_pages = len(pdf_reader.pages)
    subset_paths = []
    for start_page in range(0, total_pages, max_pages_per_subset):
        end_page = min(start_page + max_pages_per_subset, total_pages)
        pdf_writer = PdfWriter()
        for page_num in range(start_page, end_page):
            pdf_writer.add_page(pdf_reader.pages[page_num])
        subset_path = f"{pdf_path}_subset_{start_page}_{end_page-1}.pdf"
        with open(subset_path, 'wb') as f:
            pdf_writer.write(f)
        subset_paths.append(subset_path)
    return subset_paths


def fetch_model_prompt_and_schema(dataset_type, force_refresh=False):
    docs_container, conf_container = connect_to_cosmos()

    # If force refresh is requested, try to delete existing configuration
    if force_refresh:
        try:
            conf_container.delete_item(item='configuration', partition_key='configuration')
            logging.info("Deleted existing configuration for force refresh")
        except exceptions.CosmosResourceNotFoundError:
            logging.info("No existing configuration to delete")
        except Exception as e:
            logging.warning(f"Could not delete existing configuration: {e}")

    try:
        config_item = conf_container.read_item(item='configuration', partition_key='configuration')
        logging.info(f"Retrieved configuration from Cosmos DB: {type(config_item)}")
        logging.info(f"Config item keys: {config_item.keys() if isinstance(config_item, dict) else 'Not a dict'}")
    except exceptions.CosmosResourceExistsError:
        # Handle the case where the item exists but there's a conflict
        logging.info("Configuration item exists but there was a conflict, reading existing one.")
        config_item = conf_container.read_item(item='configuration', partition_key='configuration')
    except exceptions.CosmosResourceNotFoundError:
        logging.info("Configuration item not found in Cosmos DB. Creating a new configuration item.")
        
        config_item = {
            "id": "configuration",
            "partitionKey": "configuration",
            "datasets": {}
        }

        # Get the absolute path of the script's directory and construct the demo folder path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        demo_folder_path = os.path.abspath(os.path.join(script_dir, '../', 'example-datasets'))
        
        # Debug logging
        logging.info(f"Script directory: {script_dir}")
        logging.info(f"Looking for demo folder at: {demo_folder_path}")
        logging.info(f"Demo folder exists: {os.path.exists(demo_folder_path)}")

        if not os.path.exists(demo_folder_path):
            logging.error(f"Demo folder not found at {demo_folder_path}")
            raise FileNotFoundError(f"Demo folder not found at {demo_folder_path}")

        for folder_name in os.listdir(demo_folder_path):
            folder_path = os.path.join(demo_folder_path, folder_name)
            if os.path.isdir(folder_path):
                item_config = {}
                model_prompt = "Default model prompt."
                example_schema = {}

                # Look specifically for system_prompt.txt
                prompt_file_path = os.path.join(folder_path, 'system_prompt.txt')
                if os.path.exists(prompt_file_path):
                    with open(prompt_file_path, 'r') as txt_file:
                        model_prompt = txt_file.read().strip()
                        logging.info(f"Loaded prompt from {prompt_file_path}: {len(model_prompt)} characters")
                else:
                    logging.warning(f"No system_prompt.txt found in {folder_path}, using default prompt")

                # Look specifically for output_schema.json
                schema_file_path = os.path.join(folder_path, 'output_schema.json')
                if os.path.exists(schema_file_path):
                    with open(schema_file_path, 'r') as json_file:
                        example_schema = json.load(json_file)
                        logging.info(f"Loaded schema from {schema_file_path}: {len(str(example_schema))} characters")
                else:
                    logging.warning(f"No output_schema.json found in {folder_path}, using empty schema")

                # Add item config to config_item
                item_config['model_prompt'] = model_prompt
                item_config['example_schema'] = example_schema
                item_config['max_pages_per_chunk'] = 10  # Default value for backward compatibility
                config_item['datasets'][folder_name] = item_config

        try:
            conf_container.create_item(body=config_item)
            logging.info("Configuration item created.")
        except exceptions.CosmosResourceExistsError:
            # Configuration item already exists, update it with fresh data
            logging.info("Configuration item already exists, updating with fresh data.")
            config_item['id'] = 'configuration'
            config_item['partitionKey'] = 'configuration'
            conf_container.upsert_item(body=config_item)
            logging.info("Configuration item updated successfully.")

    # Ensure config_item is a dictionary
    if not isinstance(config_item, dict):
        logging.error(f"Configuration item is not a dictionary: {type(config_item)}")
        raise ValueError("Configuration item is not in expected format")

    # Check if the new structure with 'datasets' key exists
    if 'datasets' in config_item:
        datasets_config = config_item['datasets']
    else:
        # Handle legacy structure where datasets are at the top level
        # Remove system keys that shouldn't be treated as datasets
        datasets_config = {k: v for k, v in config_item.items() 
                          if k not in ['id', 'partitionKey', '_rid', '_self', '_etag', '_attachments', '_ts']}

    logging.info(f"Looking for dataset type '{dataset_type}' in configuration")
    logging.info(f"Available dataset types: {list(datasets_config.keys())}")
    
    if dataset_type not in datasets_config:
        logging.error(f"Dataset type '{dataset_type}' not found in configuration")
        available_types = list(datasets_config.keys())
        if available_types:
            logging.info(f"Using first available dataset type: {available_types[0]}")
            dataset_type = available_types[0]
        else:
            raise ValueError(f"No dataset configurations found")
    
    # Validate the dataset configuration structure
    if not isinstance(datasets_config[dataset_type], dict):
        logging.error(f"Dataset configuration for '{dataset_type}' is not a dictionary")
        raise ValueError(f"Invalid configuration structure for dataset '{dataset_type}'")
    
    if 'model_prompt' not in datasets_config[dataset_type]:
        logging.error(f"No model_prompt found for dataset '{dataset_type}'")
        raise ValueError(f"Missing model_prompt for dataset '{dataset_type}'")
    
    if 'example_schema' not in datasets_config[dataset_type]:
        logging.error(f"No example_schema found for dataset '{dataset_type}'")
        raise ValueError(f"Missing example_schema for dataset '{dataset_type}'")
    
    model_prompt = datasets_config[dataset_type]['model_prompt']
    example_schema = datasets_config[dataset_type]['example_schema']
    max_pages_per_chunk = datasets_config[dataset_type].get('max_pages_per_chunk', 10)  # Default to 10 for backward compatibility
    
    # Get processing options with defaults
    processing_options = datasets_config[dataset_type].get('processing_options', {
        "include_ocr": True,
        "include_images": True,
        "enable_summary": True,
        "enable_evaluation": True
    })
    
    return model_prompt, example_schema, max_pages_per_chunk, processing_options

def create_temp_dir():
    """Create a temporary directory with a random UUID name under /tmp/"""
    random_id = str(uuid.uuid4())
    temp_dir = os.path.join(tempfile.gettempdir(), random_id)
    os.makedirs(temp_dir, exist_ok=True)
    return temp_dir

def convert_pdf_into_image(pdf_path):
    # Create a temporary directory with random UUID
    temp_dir = create_temp_dir()
    output_paths = []
    
    try:
        # Open the PDF file
        pdf_document = fitz.open(pdf_path)
        
        # Iterate through all the pages
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            
            # Convert the page to an image  
            pix = page.get_pixmap()  

            # Convert the pixmap to bytes  
            image_bytes = pix.tobytes("png")  
            
            # Convert the image to a PIL Image object
            image = Image.open(io.BytesIO(image_bytes))
            
            # Define the output path using the temp directory
            output_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")
            output_paths.append(output_path)

            # Save the image as a PNG file
            image.save(output_path, "PNG")
            print(f"Saved image: {output_path}")
            
        return temp_dir
    except Exception as e:
        # Clean up the temporary directory if an error occurs
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise e

def run_ocr_processing(file_to_ocr: str, document: dict, container: any, conf_container: any = None, update_state: bool = True) -> tuple[str, float]:
    """
    Run OCR processing on the input file using the configured OCR provider.
    Returns OCR result and processing time.
    """
    ocr_start_time = datetime.now()
    try:
        # Get the OCR provider from environment variable (solution-level setting)
        ocr_provider = os.getenv('OCR_PROVIDER', 'azure').lower()
        
        logging.info(f"Using OCR provider: {ocr_provider}")
        
        # Select the appropriate OCR function
        if ocr_provider == 'mistral':
            ocr_result = get_mistral_ocr_results(file_to_ocr, None)
        elif ocr_provider == 'azure':
            ocr_result = get_azure_ocr_results(file_to_ocr, None)
        else:
            raise ValueError(f"Unknown OCR provider: {ocr_provider}. Supported providers: 'azure', 'mistral'")
        
        # Don't update document's ocr_output here for chunks - let caller handle merging
        ocr_processing_time = (datetime.now() - ocr_start_time).total_seconds()
        if update_state:
            document['extracted_data']['ocr_output'] = ocr_result
            document['properties']['ocr_provider_used'] = ocr_provider
            update_state(document, container, 'ocr_completed', True, ocr_processing_time)
        return ocr_result, ocr_processing_time
    except Exception as e:
        document['errors'].append(f"OCR processing error: {str(e)}")
        if update_state:
            update_state(document, container, 'ocr_completed', False)
        raise e

def run_gpt_extraction(ocr_result: str, prompt: str, json_schema: str, imgs: list, 
                      document: dict, container: any, conf_container: any = None, update_state: bool = True) -> tuple[dict, float]:
    """
    Run GPT extraction on OCR results.
    Returns extracted data and processing time.
    """
    gpt_extraction_start_time = datetime.now()
    try:
        # Debug logging
        logging.info(f"GPT Extraction Input Debug:")
        logging.info(f"  - OCR text length: {len(ocr_result)} characters")
        logging.info(f"  - Number of images: {len(imgs)}")
        logging.info(f"  - OCR text preview: {ocr_result[:200]}..." if ocr_result else "  - OCR text: EMPTY")
        logging.info(f"  - Images provided: {len(imgs) > 0}")
        
        structured = get_structured_data(ocr_result, prompt, json_schema, imgs, None)
        
        # Debug the structured response
        logging.info(f"GPT Response length: {len(structured.content)} characters")
        logging.info(f"GPT Response preview: {structured.content[:500]}...")
        
        extracted_data = safe_parse_json(structured.content)
        
        # Debug the parsed data
        logging.info(f"Parsed data keys: {list(extracted_data.keys()) if isinstance(extracted_data, dict) else 'Not a dict'}")
        logging.info(f"Parsed data empty: {not bool(extracted_data)}")
        
        # Additional debugging for common issues
        if isinstance(extracted_data, dict):
            if "error" in extracted_data or "extraction_failed" in extracted_data:
                logging.warning(f"Error detected in extracted data: {extracted_data}")
            if len(extracted_data) < 3:  # Very few fields extracted
                logging.warning(f"Suspiciously few fields extracted: {len(extracted_data)} fields")
        
        # Check if we got an error response
        if isinstance(extracted_data, dict) and ("error" in extracted_data or "extraction_failed" in extracted_data):
            error_type = extracted_data.get('error_type', 'unknown')
            error_msg = extracted_data.get('error', 'Unknown error')
            
            # Provide specific error handling for truncation cases
            if error_type in ['token_limit_exceeded', 'likely_truncation']:
                user_msg = f"Document processing failed: {error_msg}"
                if 'user_action_required' in extracted_data:
                    user_msg += f"\n\n{extracted_data['user_action_required']}"
                if 'recommendations' in extracted_data:
                    user_msg += "\n\nRecommended solutions:"
                    for i, rec in enumerate(extracted_data['recommendations'], 1):
                        user_msg += f"\n{i}. {rec}"
                
                # Log technical details for debugging
                if 'technical_details' in extracted_data:
                    tech_details = extracted_data['technical_details']
                    logging.error(f"Truncation technical details: {tech_details}")
                
                logging.error(user_msg)
                document['errors'].append(user_msg)
            else:
                # Handle other types of errors
                logging.error(f"GPT extraction failed: {error_msg}")
                if "json_error" in extracted_data:
                    logging.error(f"JSON parsing error: {extracted_data['json_error']}")
                if "parsing_error" in extracted_data:
                    logging.error(f"JSON parsing error: {extracted_data['parsing_error']}")
                if "raw_content" in extracted_data:
                    logging.error(f"Raw response content: {extracted_data['raw_content'][:500]}...")
                
                # Provide user-friendly message for other errors too
                if 'user_action_required' in extracted_data:
                    user_friendly_msg = f"{error_msg}\n\n{extracted_data['user_action_required']}"
                    if 'recommendations' in extracted_data:
                        user_friendly_msg += "\n\nRecommended solutions:"
                        for i, rec in enumerate(extracted_data['recommendations'], 1):
                            user_friendly_msg += f"\n{i}. {rec}"
                    document['errors'].append(user_friendly_msg)
                else:
                    document['errors'].append(error_msg)
            
            # Return a structured error instead of raising
            if update_state:
                update_state(document, container, 'gpt_extraction_completed', False)
            return {"error": error_msg, "error_type": error_type}, 0.0
        
        gpt_extraction_time = (datetime.now() - gpt_extraction_start_time).total_seconds()
        if update_state:
            document['extracted_data']['gpt_extraction_output'] = extracted_data
            update_state(document, container, 'gpt_extraction_completed', True, gpt_extraction_time)
        return extracted_data, gpt_extraction_time
    except Exception as e:
        logging.error(f"GPT extraction error: {str(e)}")
        logging.error(f"Exception type: {type(e).__name__}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        document['errors'].append(f"GPT extraction error: {str(e)}")
        if update_state:
            update_state(document, container, 'gpt_extraction_completed', False)
        raise e

def run_gpt_evaluation(imgs: list, extracted_data: dict, json_schema: str, 
                      document: dict, container: any, conf_container: any = None, update_state: bool = True) -> tuple[dict, float]:
    """
    Run GPT evaluation and enrichment on extracted data.
    Returns enriched data and processing time.
    """
    evaluation_start_time = datetime.now()
    try:
        enriched_data = perform_gpt_evaluation_and_enrichment(imgs, extracted_data, json_schema, None)
        evaluation_time = (datetime.now() - evaluation_start_time).total_seconds()
        if update_state:
            document['extracted_data']['gpt_extraction_output_with_evaluation'] = enriched_data
            update_state(document, container, 'gpt_evaluation_completed', True, evaluation_time)
        return enriched_data, evaluation_time
    except Exception as e:
        document['errors'].append(f"GPT evaluation error: {str(e)}")
        if update_state:
            update_state(document, container, 'gpt_evaluation_completed', False)
        raise e

def run_gpt_summary(ocr_result: str, document: dict, container: any, conf_container: any = None, update_state: bool = True) -> tuple[dict, float]:
    """
    Run GPT summary on OCR results.
    Returns summary data and processing time.
    """
    summary_start_time = datetime.now()
    try:
        classification = getattr(ocr_result, 'categorization', 'N/A')
        gpt_summary = get_summary_with_gpt(ocr_result, None)
        
        summary_data = {
            'classification': classification,
            'gpt_summary_output': gpt_summary.content
        }
        
        summary_processing_time = (datetime.now() - summary_start_time).total_seconds()
        if update_state:
            document['extracted_data']['classification'] = classification
            document['extracted_data']['gpt_summary_output'] = gpt_summary.content
            update_state(document, container, 'gpt_summary_completed', True, summary_processing_time)
        return summary_data, summary_processing_time
    except Exception as e:
        document['errors'].append(f"Summary processing error: {str(e)}")
        if update_state:
            update_state(document, container, 'gpt_summary_completed', False)
        raise e

def prepare_images(file_to_ocr: str, config: Config = Config()) -> tuple[str, list]:
    """
    Prepare images from PDF file for processing.
    Returns temporary directory path and processed images.
    """
    temp_dir = convert_pdf_into_image(file_to_ocr)
    imgs = glob.glob(os.path.join(temp_dir, "page*.png"))[:config.max_images]
    imgs = [load_image(img) for img in imgs]
    
    # Limit images size
    max_size = config.gpt_vision_limit_mb * 1024 * 1024
    while get_size_of_base64_images(imgs) > max_size:
        imgs.pop()
        
    return temp_dir, imgs



