import os

from dotenv import load_dotenv

def get_config():
    load_dotenv()
    return {
        "doc_intelligence_endpoint": os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT", None),
        "doc_intelligence_key": os.getenv("DOCUMENT_INTELLIGENCE_KEY", None),
        "openai_api_key": os.getenv("AZURE_OPENAI_KEY", None),
        "openai_api_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", None),
        "openai_api_version": "2024-07-01-preview",
        "openai_model_deployment": os.getenv("AZURE_OPENAI_MODEL_DEPLOYMENT_NAME", None),
        "temp_images_outdir" : os.getenv("TEMP_IMAGES_OUTDIR", "/tmp/")
    }
