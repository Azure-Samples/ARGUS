import os
import logging

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def get_config(cosmos_config_container=None):
    """
    Get configuration from environment variables only.
    
    Note: cosmos_config_container parameter is kept for backwards compatibility 
    but is ignored. Configuration is now sourced exclusively from environment variables.
    """
    load_dotenv()
    
    # Configuration from environment variables only
    config = {
        "doc_intelligence_endpoint": os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", None),
        "openai_api_key": os.getenv("AZURE_OPENAI_KEY", None),
        "openai_api_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", None),
        "openai_api_version": "2024-12-01-preview",
        "openai_model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", None),
        "temp_images_outdir": os.getenv("TEMP_IMAGES_OUTDIR", "/tmp/")
    }
    
    # Log which values are configured (without exposing secrets)
    logger.info("Using OpenAI configuration from environment variables")
    logger.info(f"OpenAI endpoint: {'✓ Set' if config['openai_api_endpoint'] else '✗ Missing'}")
    logger.info(f"OpenAI API key: {'✓ Set' if config['openai_api_key'] else '✗ Missing'}")
    logger.info(f"OpenAI deployment: {'✓ Set' if config['openai_model_deployment'] else '✗ Missing'}")
    
    return config
