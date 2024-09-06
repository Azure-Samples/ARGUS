import base64

from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion
from semantic_kernel.connectors.ai import PromptExecutionSettings

from ai_ocr.azure.config import get_config

def get_completion_service():  
    api_key = get_config()['openai_api_key'] 
    if not api_key:  
        raise ValueError("openai_api_key environment variable is not set.")  

    chat_completion_service = AzureChatCompletion(
            deployment_name=get_config()["openai_model_deployment"],
            api_key=api_key,
            base_url=get_config()["openai_api_endpoint"],
            api_version=get_config()["openai_api_version"])
    
    req_settings = PromptExecutionSettings(
        extension_data = {
            "max_tokens": 4000,
            "temperature": 0,
        }
    )
    return chat_completion_service, req_settings


def load_image(image_path) -> str:
    """Load image from file and encode it as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_size_of_base64_images(images):
    total_size = 0
    for img in images:
        total_size += len(img)
    return total_size
