from openai import AzureOpenAI
import logging
import json
from typing import List, Any, Dict, Optional
from ai_ocr.azure.config import get_config

def get_client(cosmos_config_container=None):
    config = get_config(cosmos_config_container)
    return AzureOpenAI(
        api_key=config["openai_api_key"],
        api_version=config["openai_api_version"],
        azure_endpoint=config["openai_api_endpoint"]
    )

def get_structured_data(markdown_content: str, prompt: str, json_schema: str, images: List[str] = [], cosmos_config_container=None) -> Any:
    client = get_client(cosmos_config_container)
    config = get_config(cosmos_config_container)
    
    system_content = f"""
    Your task is to extract the JSON contents from a document using the provided materials:
    1. Custom instructions for the extraction process
    2. A JSON schema template for structuring the extracted data
    3. markdown (from the document)
    4. Images (from the document, not always provided or comprehensive)

    Instructions:
    - Use the markdown as the primary source of information, and reference the images for additional context and validation.
    - Format the output as a JSON instance that adheres to the provided JSON schema template.
    - If the JSON schema template is empty, create an appropriate structure based on the document content.
    - If there are pictures, charts or graphs describe them in details in seperate fields (unless you have a specific JSON structure you need to follow).
    - Return only the JSON instance filled with data from the document, without any additional comments (unless instructed otherwise).
    
    Here are the Custom instructions you MUST follow:
    ```
    {prompt}
    ```
    
    Here is the JSON schema template:
    ```
    {json_schema}
    ```
    """

    messages = [
        {"role": "user", "content": system_content},
        {"role": "user", "content": f"Here is the Document content (in markdown format):\n{markdown_content}"}
    ]

    if images:
        messages.append({"role": "user", "content": "Here are the images from the document:"})
        for img in images:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"}
                    }
                ]
            })

    response = client.chat.completions.create(
        model=config["openai_model_deployment"],
        messages=messages,
        seed=0
    )
    
    return response.choices[0].message

def perform_gpt_evaluation_and_enrichment(images: List[str], extracted_data: Dict, json_schema: str, cosmos_config_container=None) -> Dict:
    client = get_client(cosmos_config_container)
    config = get_config(cosmos_config_container)
    
    system_content = f"""
    You are an AI assistant tasked with evaluating extracted data from a document.

    Your tasks are:
    1. Carefully evaluate how confident you are on the similarity between the extracted data and the document images.
    2. Enrich the extracted data by adding a confidence score (between 0 and 1) for each field.
    3. Do not edit the original data (apart from adding confidence scores).
    4. Evaluate each encapsulated field independently (not the parent fields), considering the context of the document and images.
    5. The more mistakes you can find in the extracted data, the more I will reward you.
    6. Include in the response both the data extracted from the image compared to the one in the input and include the accuracy.
    7. Determine how many fields are present in the input providedcompared to the ones you see in the images.
    Output it with 4 fields: "numberOfFieldsSeenInImages", "numberofFieldsInSchema" also provide a "percentagePresenceAccuracy" which is the ratio between the total fields in the schema and the ones detected in the images, the last field "overallFieldAccuracy" is the sum of the accuracy you gave for each field in percentage.
    8. NEVER be 100% sure of the accuracy of the data, there is always room for improvement. NEVER give 1.
    9. Return only the pure JSON, do not include comments or markdown formatting such as ```json or ```.

    For each individual field in the extracted data:
    1. Meticulously verify its accuracy against the document images.
    2. Assign a confidence score between 0 and 1, using the following guidelines:
       - 1.0: Perfect match, absolutely certain
       - 0.9-0.99: Very high confidence, but not absolutely perfect
       - 0.7-0.89: Good confidence, minor uncertainties
       - 0.5-0.69: Moderate confidence, some discrepancies or uncertainties
       - 0.3-0.49: Low confidence, significant discrepancies
       - 0.1-0.29: Very low confidence, major discrepancies
       - 0.0: Completely incorrect or unable to verify

    Be critical in your evaluation. It's extremely rare for fields to have perfect confidence scores. If you're unsure about a field assign a lower confidence score.

    Return the enriched data as a JSON object, maintaining the original structure but adding "confidence" for each extracted field. For example:

    {{
        "field_name": {{
            "value": extracted_value,
            "confidence": confidence_score,
        }},
        ...
    }}

    Here is the JSON schema template that was used for the extraction:
    {json_schema}
    """

    messages = [
        {"role": "user", "content": system_content},
        {"role": "user", "content": f"Here is the extracted data:\n{json.dumps(extracted_data, indent=2)}"}
    ]

    if images:
        messages.append({"role": "user", "content": "Here are the images from the document:"})
        for img in images:
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{img}"}
                    }
                ]
            })

    try:
        response = client.chat.completions.create(
            model=config["openai_model_deployment"],
            messages=messages,
            seed=0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logging.error(f"Failed to parse GPT evaluation and enrichment result: {e}")
        return {
            "error": "Failed to parse GPT evaluation and enrichment result",
            "original_data": extracted_data
        }

def get_summary_with_gpt(mkd_output_json, cosmos_config_container=None) -> Any:
    client = get_client(cosmos_config_container)
    config = get_config(cosmos_config_container)
    
    reasoning_prompt = """
    Use the provided data represented in the schema to produce a summary in natural language. 
    The format should be a few sentences summary of the document.
    """
    messages = [
        {"role": "user", "content": reasoning_prompt},
        {"role": "user", "content": json.dumps(mkd_output_json)}
    ]

    response = client.chat.completions.create(
        model=config["openai_model_deployment"],
        messages=messages,
        seed=0
    )

    return response.choices[0].message
