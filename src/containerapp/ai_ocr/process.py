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
from langchain_core.output_parsers.json import parse_json_markdown

from ai_ocr.azure.doc_intelligence import get_ocr_results
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

def initialize_document(file_name: str, file_size: int, num_pages:int, prompt: str, json_schema: str, request_timestamp: datetime, dataset: str = None, max_pages_per_chunk: int = 10) -> dict:
    # Extract dataset from file_name if not provided
    if dataset is None:
        blob_parts = file_name.split('/')
        if len(blob_parts) >= 2:
            dataset = blob_parts[0]
        else:
            dataset = 'default-dataset'
    
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


def fetch_model_prompt_and_schema(dataset_type):
    docs_container, conf_container = connect_to_cosmos()

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

                # Find any txt file for model prompt
                for file_name in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file_name)
                    if file_name.endswith('.txt'):
                        with open(file_path, 'r') as txt_file:
                            model_prompt = txt_file.read().strip()
                            break

                # Find any json file for example schema
                for file_name in os.listdir(folder_path):
                    file_path = os.path.join(folder_path, file_name)
                    if file_name.endswith('.json'):
                        with open(file_path, 'r') as json_file:
                            example_schema = json.load(json_file)
                            break

                # Add item config to config_item
                item_config['model_prompt'] = model_prompt
                item_config['example_schema'] = example_schema
                item_config['max_pages_per_chunk'] = 10  # Default value for backward compatibility
                config_item['datasets'][folder_name] = item_config

        try:
            conf_container.create_item(body=config_item)
            logging.info("Configuration item created.")
        except exceptions.CosmosResourceExistsError:
            # Configuration item already exists, try to read it again
            logging.info("Configuration item already exists, reading existing one.")
            config_item = conf_container.read_item(item='configuration', partition_key='configuration')

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
    return model_prompt, example_schema, max_pages_per_chunk

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
    Run OCR processing on the input file.
    Returns OCR result and processing time.
    """
    ocr_start_time = datetime.now()
    try:
        ocr_result = get_ocr_results(file_to_ocr, conf_container)
        # Don't update document's ocr_output here for chunks - let caller handle merging
        ocr_processing_time = (datetime.now() - ocr_start_time).total_seconds()
        if update_state:
            document['extracted_data']['ocr_output'] = ocr_result
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
        structured = get_structured_data(ocr_result, prompt, json_schema, imgs, conf_container)
        extracted_data = parse_json_markdown(structured.content)
        gpt_extraction_time = (datetime.now() - gpt_extraction_start_time).total_seconds()
        if update_state:
            document['extracted_data']['gpt_extraction_output'] = extracted_data
            update_state(document, container, 'gpt_extraction_completed', True, gpt_extraction_time)
        return extracted_data, gpt_extraction_time
    except Exception as e:
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
        enriched_data = perform_gpt_evaluation_and_enrichment(imgs, extracted_data, json_schema, conf_container)
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
        gpt_summary = get_summary_with_gpt(ocr_result, conf_container)
        
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



