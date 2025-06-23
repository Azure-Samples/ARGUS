import os
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def get_config(cosmos_config_container=None):
    """
    Get configuration with support for loading OpenAI settings from Cosmos DB.
    Falls back to environment variables if Cosmos DB is not available.
    """
    load_dotenv()
    
    # Base configuration from environment variables
    config = {
        "doc_intelligence_endpoint": os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", None),
        "openai_api_key": os.getenv("AZURE_OPENAI_KEY", None),
        "openai_api_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", None),
        "openai_api_version": "2024-12-01-preview",
        "openai_model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", None),
        "temp_images_outdir": os.getenv("TEMP_IMAGES_OUTDIR", "/tmp/")
    }
    
    # Try to load OpenAI settings from Cosmos DB if container is provided
    if cosmos_config_container:
        try:
            openai_config_item = cosmos_config_container.read_item(
                item='openai_config', 
                partition_key='openai_config'
            )
            
            # Override environment variables with Cosmos DB values if they exist
            if openai_config_item.get("openai_endpoint"):
                config["openai_api_endpoint"] = openai_config_item["openai_endpoint"]
                logger.info("Using OpenAI endpoint from Cosmos DB configuration")
            
            if openai_config_item.get("openai_key"):
                config["openai_api_key"] = openai_config_item["openai_key"]
                logger.info("Using OpenAI API key from Cosmos DB configuration")
                
            if openai_config_item.get("deployment_name"):
                config["openai_model_deployment"] = openai_config_item["deployment_name"]
                logger.info(f"Using OpenAI deployment '{openai_config_item['deployment_name']}' from Cosmos DB configuration")
                
        except Exception as e:
            logger.info(f"OpenAI configuration not found in Cosmos DB, using environment variables: {e}")
    
    return config
