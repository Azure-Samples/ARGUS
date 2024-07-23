import glob, logging, json, os, sys
from datetime import datetime
import tempfile 
from azure.cosmos import CosmosClient, exceptions
from PyPDF2 import PdfReader
from langchain_core.output_parsers.json import parse_json_markdown

from ai_ocr.azure.doc_intelligence import get_ocr_results
from ai_ocr.azure.openai_ops import load_image, get_size_of_base64_images
from ai_ocr.chains import get_structured_data, get_summary_with_gpt
from ai_ocr.model import Config
from ai_ocr.azure.images import convert_pdf_into_image

def connect_to_cosmos():
    endpoint = os.environ['COSMOS_DB_ENDPOINT']
    key = os.environ['COSMOS_DB_KEY']
    database_name = os.environ['COSMOS_DB_DATABASE_NAME']
    container_name = os.environ['COSMOS_DB_CONTAINER_NAME']
    client = CosmosClient(endpoint, key)
    database = client.get_database_client(database_name)
    docs_container = database.get_container_client(container_name)
    conf_container = database.get_container_client('configuration')

    return docs_container, conf_container

def initialize_document(file_name: str, file_size: int, num_pages:int, prompt: str, json_schema: str, request_timestamp: datetime) -> dict:
    return {
        "id": file_name.replace('/', '__'),
        "properties": {
            "blob_name": file_name,
            "blob_size": file_size,
            "request_timestamp": request_timestamp.isoformat(),
            "num_pages": num_pages
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
        "model_input":{
            "model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME"),
            "model_prompt": prompt,
            "example_schema": json_schema
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


def fetch_model_prompt_and_schema(dataset_type):
    docs_container, conf_container = connect_to_cosmos()

    try:
        config_item = conf_container.read_item(item='configuration', partition_key={})
    except exceptions.CosmosResourceNotFoundError:
        logging.info("Configuration item not found in Cosmos DB. Creating a new configuration item.")
        
        config_item = {
            "id": "configuration"
        }

        # Get the absolute path of the script's directory and construct the demo folder path
        script_dir = os.path.dirname(os.path.abspath(__file__))
        demo_folder_path = os.path.abspath(os.path.join(script_dir, '../', 'example-datasets'))

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
                config_item[folder_name] = item_config

        conf_container.create_item(body=config_item)
        logging.info("Configuration item created.")

    model_prompt = config_item[dataset_type]['model_prompt']
    example_schema = config_item[dataset_type]['example_schema']
    return model_prompt, example_schema


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
    convert_pdf_into_image(file_to_ocr)
    
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

def process_gpt_summary(ocr_response, document, container):
    try:
        classification = 'N/A'
        try:
            classification = ocr_response.categorization
        except AttributeError:
            logging.warning("Cannot find 'categorization' in output schema! Logging it as N/A...")
        summary_start_time = datetime.now()
        gpt_summary = get_summary_with_gpt(ocr_response)
        summary_processing_time = (datetime.now() - summary_start_time).total_seconds()
        update_state(document, container, 'gpt_summary_completed', True, summary_processing_time)
        document['extracted_data']['classification'] = classification
        document['extracted_data']['gpt_summary_output'] = gpt_summary.content
    except Exception as e:
        document['errors'].append(f"NL processing error: {str(e)}")
        update_state(document, container, 'gpt_summary_completed', False)
        sys.exit(1)  # Exit with error
        raise
