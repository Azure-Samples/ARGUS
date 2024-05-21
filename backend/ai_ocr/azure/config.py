import os

from dotenv import load_dotenv

def get_config():
    load_dotenv()
    return {
        "doc_intelligence_endpoint": os.getenv("DOC_INTEL_ENDPOINT", None),
        "doc_intelligence_key": os.getenv("DOC_INTEL_KEY", None),
        "openai_api_key": os.getenv("AZURE_OPENAI_API_KEY", None),
        "openai_api_endpoint": os.getenv("AZURE_OPENAI_ENDPOINT", None),
        "openai_api_version": os.getenv("OPENAI_API_VERSION", None),
        "openai_model_deployment": os.getenv("AZURE_OPENAI_API_DEPLOYMENT", "gpt-4-turbo"),
        "temp_images_outdir" : os.getenv("TEMP_IMAGES_OUTDIR", "")
    }
