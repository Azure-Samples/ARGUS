import base64

from langchain.chains.transform import TransformChain
from langchain_openai import AzureChatOpenAI

from ai_ocr.azure.config import get_config


def get_llm():
    return AzureChatOpenAI(
        model=get_config()["openai_model_deployment"],
        temperature=0,
        max_tokens=4000,
        verbose=True)



def load_image(image_path) -> str:
    """Load image from file and encode it as base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_size_of_base64_images(images):
    total_size = 0
    for img in images:
        total_size += len(img)
    return total_size


load_image_chain = TransformChain(
    input_variables=["image_path"],
    output_variables=["image"],
    transform=load_image
)
