from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage
from langchain_core.prompts import HumanMessagePromptTemplate

from ai_ocr.azure.openai_ops import get_llm

import logging


def get_structured_data(markdown_content: str, prompt: str, json_schema: str, images=[]) -> any:
    system_message = f"""
    Your task is to extract the JSON contents from a document using the provided materials:
    1. Custom instructions for the extraction process
    2. A JSON schema template for structuring the extracted data
    3. Markdown (from the document)
    4. Images (from the document, not always provided or comprehensive)

    Instructions:
    - Use the markdown as the primary source of information, and reference the images for additional context and validation.
    - Format the output as a JSON instance that adheres to the provided JSON schema template.
    - If the JSON schema template is empty, create an appropriate structure based on the document content.
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
            messages.append(HumanMessage(content=[{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img}"}}]))

    model = get_llm()
    return model.invoke(messages)

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