from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.prompts import HumanMessagePromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from ai_ocr.azure.openai_ops import get_llm

import logging, json


def get_structured_data(markdown_content: str, prompt: str, json_schema: str, images=[]) -> any:
    system_message = f"""
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

    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=system_message),
            HumanMessagePromptTemplate.from_template("Here is the Document content (in markdown format):\n{markdown}"),
        ]
    )

    messages = chat_template.format_messages(markdown=markdown_content)

    if images:
        messages.append(HumanMessage(content="Here are the images from the document:"))
        for img in images:
            messages.append(HumanMessage(content=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]))

    #todo manage token count
    model = get_llm()
    return model.invoke(messages)




def perform_gpt_evaluation_and_enrichment(images: list, extracted_data: dict, json_schema: str) -> dict:
    model = get_llm()
    
    parser = JsonOutputParser()
    
    system_message = f"""
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
            
    ..and take your time to complete the tasks.
    

    IMPORTANT: Return only the JSON instance filled with data from the document and the evaluation, without any additional comments. Don't include  ```json and ```.
    
    Here is the JSON schema template that was used for the extraction:

    {json_schema}
    
    ------
    
    {parser.get_format_instructions()}
    """

    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(content=system_message),
            HumanMessagePromptTemplate.from_template("Here is the extracted data :\n{extracted}"),
        ]
    )
    messages = chat_template.format_messages(extracted=json.dumps(extracted_data, indent=2))

    if images:
        messages.append(HumanMessage(content="Here are the images from the document:"))
        for img in images:
            messages.append(HumanMessage(content=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img}"}}]))

    evaluation_result = model.invoke(messages)
    try:
        return parser.parse(evaluation_result.content)
    except Exception as e:
        logging.error(f"Failed to parse GPT evaluation and enrichment result: {e}")
        return {
            "error": "Failed to parse GPT evaluation and enrichment result",
            "original_data": extracted_data
        }


def get_summary_with_gpt(mkd_output_json: str) -> any:
    reasoning_prompt = """
    Use the provided data represented in the schema to produce a summary in natural language. The format should be a few sentences summary of the document.

    As an example, for the schema {"properties": {"foo": {"title": "Foo", "description": "a list of strings", "type": "array", "items": {"type": "string"}}}, "required": ["foo"]}
    the object {"foo": ["bar", "baz"]} is a well-formatted instance of the schema. The object {"properties": {"foo": ["bar", "baz"]}} is not well-formatted.
    """
    
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=(
                    reasoning_prompt
                )
            ),
            HumanMessagePromptTemplate.from_template("{text}"),
        ]
    )
    messages = chat_template.format_messages(text=mkd_output_json)

    model = get_llm()
    return model.invoke(messages)


def classify_doc_with_llm(ocr_input: str, classification_system_prompt) -> any:
    prompt = classification_system_prompt
    
    chat_template = ChatPromptTemplate.from_messages(
        [
            SystemMessage(
                content=(
                    prompt
                )
            ),
            HumanMessagePromptTemplate.from_template("{text}"),
        ]
    )
    messages = chat_template.format_messages(text=ocr_input)

    model = get_llm()
    return model.invoke(messages)