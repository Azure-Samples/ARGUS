from openai import AzureOpenAI
import logging
import json
import re
from typing import List, Any, Dict, Optional
from ai_ocr.azure.config import get_config

def clean_json_response(raw_content: str) -> str:
    """
    Attempt to clean common JSON formatting issues in GPT responses
    """
    try:
        # Remove markdown code blocks if present
        content = raw_content.strip()
        if content.startswith('```json'):
            content = content[7:]
        if content.startswith('```'):
            content = content[3:]
        if content.endswith('```'):
            content = content[:-3]
        
        # Remove any leading/trailing whitespace
        content = content.strip()
        
        # Try to find the JSON object boundaries
        start_idx = content.find('{')
        end_idx = content.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            content = content[start_idx:end_idx + 1]
        else:
            # Try array boundaries if object boundaries not found
            start_idx = content.find('[')
            end_idx = content.rfind(']')
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                content = content[start_idx:end_idx + 1]
        
        # Fix common JSON issues step by step
        
        # 1. Replace single quotes with double quotes for property names and values
        # Be careful to not break contractions within string values
        content = re.sub(r"'(\w+)':", r'"\1":', content)  # Fix property names with single quotes
        content = re.sub(r': \'([^\']*?)\'(?=\s*[,}\]])', r': "\1"', content)  # Fix string values with single quotes
        
        # 2. Fix trailing commas before closing brackets/braces
        content = re.sub(r',(\s*[}\]])', r'\1', content)
        
        # 3. Fix unescaped quotes within strings (simple heuristic)
        # Find strings that have unescaped quotes and escape them
        def escape_quotes_in_strings(match):
            string_content = match.group(1)
            # Escape any unescaped quotes inside
            escaped = string_content.replace('"', '\\"')
            return f'"{escaped}"'
        
        # This regex finds strings that might have unescaped quotes
        content = re.sub(r'"([^"]*(?:\\"[^"]*)*)"', lambda m: m.group(0), content)
        
        # 4. Fix missing quotes around property names
        content = re.sub(r'(\w+):', r'"\1":', content)
        
        # 5. Fix missing quotes around string values that look like they should be strings
        # This is tricky - only do this for values that are clearly meant to be strings
        content = re.sub(r': ([A-Za-z][A-Za-z0-9\s]*?)(?=\s*[,}\]])', r': "\1"', content)
        
        # 6. Remove any remaining text after the JSON object/array
        if content.startswith('{'):
            brace_count = 0
            for i, char in enumerate(content):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        content = content[:i+1]
                        break
        elif content.startswith('['):
            bracket_count = 0
            for i, char in enumerate(content):
                if char == '[':
                    bracket_count += 1
                elif char == ']':
                    bracket_count -= 1
                    if bracket_count == 0:
                        content = content[:i+1]
                        break
        
        return content
        
    except Exception as e:
        logging.error(f"Error cleaning JSON: {e}")
        return ""

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
    
    # Determine what input modalities we have
    has_text = bool(markdown_content and markdown_content.strip())
    has_images = bool(images)
    
    # Build context-aware instructions
    modality_instruction = ""
    if has_text and has_images:
        modality_instruction = """
        **MULTIMODAL INPUT DETECTED**: You have both text (OCR) and images available.
        
        EXTRACTION STRATEGY:
        1. Use the OCR text as your primary source for detailed information (names, numbers, exact text)
        2. Use the images to validate the OCR text and extract any visual elements not captured in text
        3. Cross-reference between text and images to ensure accuracy
        4. If there are discrepancies, prefer the images for layout and structure, text for precise details
        5. Extract information from BOTH sources to create a comprehensive result
        
        The text contains the exact extracted content from the document, while images provide visual context and layout information.
        """
    elif has_text and not has_images:
        modality_instruction = """
        **TEXT-ONLY INPUT**: You only have OCR text available. 
        Extract all information from the provided text content. Be thorough and extract every relevant detail.
        """
    elif not has_text and has_images:
        modality_instruction = """
        **IMAGE-ONLY INPUT**: You only have images available (no OCR text). 
        Extract all information directly from the images. Read every visible text, number, and structured element.
        Pay attention to layout, tables, forms, and any visual organization of the information.
        """
    else:
        raise ValueError("No input provided - both OCR text and images are missing")
    
    system_content = f"""
    You are an expert document extraction AI. Your task is to extract structured JSON data from a document.

    {modality_instruction}

    EXTRACTION REQUIREMENTS:
    - Format the output as a valid JSON object that follows the provided schema template
    - Extract all data exactly as is, DO NO summarize, DO NOT paraphrase, DO NOT skip any data
    - Fill ALL relevant fields from the schema with extracted information
    - If a schema field cannot be filled from the document, use null or appropriate empty value
    - If additional information exists beyond the schema, include it in the "additional_info" field
    - Return ONLY the JSON object - no explanations, markdown formatting, or wrapper text
    - Ensure the JSON is properly formatted and parseable
    - NEVER return empty objects {{}} - always extract meaningful data

    ⚠️ CRITICAL JSON FORMATTING RULES - FOLLOW EXACTLY:
    1. Use ONLY double quotes (") for all property names and string values
    2. NEVER use single quotes (') anywhere in the JSON
    3. Do NOT include trailing commas before closing brackets }} or ]]
    4. Escape quotes inside strings with backslash (\")
    5. Do NOT wrap the JSON in markdown code blocks or ```
    6. Ensure all brackets and braces are properly closed and balanced
    7. Do NOT include any text before or after the JSON object
    8. Property names must be quoted: {{"name": "value"}}, not {{name: "value"}}
    9. String values must be quoted: {{"key": "text"}}, not {{"key": text}}
    10. Use null (not "null" or None) for missing values

    EXAMPLE OF CORRECT JSON FORMAT:
    {{
        "field1": "string value",
        "field2": 123,
        "field3": null,
        "field4": true,
        "nested": {{
            "subfield": "another string"
        }}
    }}

    CUSTOM EXTRACTION INSTRUCTIONS:
    {prompt}
    
    JSON SCHEMA TEMPLATE TO FOLLOW:
    {json.dumps(json_schema, indent=2)}
    
    ⚠️ IMPORTANT: Return ONLY valid JSON, nothing else. No explanations, no markdown formatting, no text outside the JSON.
    """

    messages = [
        {"role": "user", "content": system_content}
    ]
    
    # Add text content if available
    if has_text:
        messages.append({"role": "user", "content": f"Here is the Document content (in markdown format):\n{markdown_content}"})
    
    # Add images if available  
    if has_images:
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

    # Log the prompt being sent for debugging
    logging.info(f"GPT Extraction Prompt Debug:")
    logging.info(f"  - Has text: {has_text}")
    logging.info(f"  - Has images: {has_images}")
    logging.info(f"  - Message count: {len(messages)}")
    logging.info(f"  - Custom prompt: {prompt}")
    logging.info(f"  - Model: {config['openai_model_deployment']}")
    logging.info(f"  - Using JSON mode: {'gpt-4' in config['openai_model_deployment'].lower()}")

    try:
        response = client.chat.completions.create(
            model=config["openai_model_deployment"],
            messages=messages
        )
        
        raw_content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        
        logging.info(f"GPT Raw Response: {raw_content[:500]}...")  # Log first 500 chars
        logging.info(f"GPT Finish Reason: {finish_reason}")
        
        # Check if the response was truncated due to hitting max tokens
        if finish_reason == "length":
            logging.error("GPT response was truncated due to hitting max completion tokens")
            error_response = {
                "error": "GPT response was truncated due to hitting maximum completion tokens",
                "error_type": "token_limit_exceeded",
                "finish_reason": finish_reason,
                "raw_content": raw_content[:1000],
                "extraction_failed": True,
                "user_action_required": "The document chunk is too large for the current model configuration. Please try one of the following solutions:",
                "recommendations": [
                    "Reduce the 'max_pages_per_chunk' parameter to process smaller chunks of the document",
                    "Use a shorter and more concise JSON schema to reduce output requirements", 
                    "Break down complex extraction tasks into simpler, more focused extractions",
                    "Consider using a model with higher token limits if available"
                ],
                "technical_details": {
                    "response_length": len(raw_content),
                    "truncated": True
                }
            }
            response.choices[0].message.content = json.dumps(error_response)
            return response.choices[0].message
        
        # Try to parse as JSON to validate
        try:
            parsed_json = json.loads(raw_content)
            logging.info("GPT response successfully parsed as JSON")
            return response.choices[0].message
        except json.JSONDecodeError as json_error:
            logging.error(f"GPT returned invalid JSON: {json_error}")
            logging.error(f"Raw content: {raw_content}")
            
            # Check if this might be a partial JSON due to truncation (even if finish_reason wasn't "length")
            is_likely_truncated = False
            if raw_content:
                # Check for common signs of truncation
                content_stripped = raw_content.strip()
                if (not content_stripped.endswith('}') and not content_stripped.endswith(']')) or \
                   content_stripped.count('{') != content_stripped.count('}') or \
                   content_stripped.count('[') != content_stripped.count(']'):
                    is_likely_truncated = True
                    logging.warning("JSON appears to be truncated based on bracket analysis")
            
            if is_likely_truncated:
                error_response = {
                    "error": "GPT response appears to be truncated, resulting in invalid JSON",
                    "error_type": "likely_truncation", 
                    "finish_reason": finish_reason,
                    "json_error": str(json_error),
                    "raw_content": raw_content[:1000],
                    "extraction_failed": True,
                    "user_action_required": "The response was likely truncated. Please try one of the following solutions:",
                    "recommendations": [
                        "Reduce the 'max_pages_per_chunk' parameter to process smaller document chunks",
                        "Simplify the JSON schema to require less detailed output",
                        "Use a more concise system prompt to reduce token usage",
                        "Consider processing the document in smaller sections"
                    ],
                    "technical_details": {
                        "response_length": len(raw_content),
                        "brackets_balanced": content_stripped.count('{') == content_stripped.count('}'),
                        "likely_truncated": True
                    }
                }
                response.choices[0].message.content = json.dumps(error_response)
                return response.choices[0].message
            
            # Multiple fallback strategies for JSON cleaning
            cleanup_strategies = [
                lambda x: clean_json_response(x),  # Our custom cleaner
                lambda x: x.strip().replace('```json', '').replace('```', '').strip(),  # Simple markdown removal
                lambda x: re.sub(r'^.*?(\{.*\}).*$', r'\1', x, flags=re.DOTALL),  # Extract just the JSON object
                lambda x: re.sub(r'^.*?(\[.*\]).*$', r'\1', x, flags=re.DOTALL),  # Extract just the JSON array
            ]
            
            for i, strategy in enumerate(cleanup_strategies):
                try:
                    cleaned_content = strategy(raw_content)
                    if cleaned_content:
                        json.loads(cleaned_content)  # Validate it parses
                        logging.info(f"Successfully cleaned JSON using strategy {i+1}")
                        # Create a new message object with cleaned content
                        response.choices[0].message.content = cleaned_content
                        return response.choices[0].message
                except (json.JSONDecodeError, Exception) as cleanup_error:
                    logging.warning(f"Cleanup strategy {i+1} failed: {cleanup_error}")
                    continue
            
            logging.error("All JSON cleanup strategies failed")
            
            # Return a structured error response for parsing failures
            error_response = {
                "error": "Invalid JSON response from GPT - unable to parse after cleanup attempts",
                "error_type": "json_parse_error",
                "finish_reason": finish_reason,
                "json_error": str(json_error),
                "raw_content": raw_content[:1000],  # First 1000 chars for debugging
                "extraction_failed": True,
                "user_action_required": "GPT returned malformed JSON. This may indicate the response was partially corrupted.",
                "recommendations": [
                    "Try running the extraction again (temporary GPT formatting issue)",
                    "Reduce document complexity or chunk size if the issue persists",
                    "Simplify the JSON schema to reduce formatting complexity",
                    "Check if the system prompt is causing formatting conflicts"
                ],
                "technical_details": {
                    "response_length": len(raw_content),
                    "cleanup_attempts": len(cleanup_strategies),
                    "all_cleanup_failed": True
                }
            }
            response.choices[0].message.content = json.dumps(error_response)
            return response.choices[0].message
            
    except Exception as e:
        logging.error(f"GPT API call failed: {e}")
        error_response = {
            "error": "GPT API call failed",
            "exception": str(e)
        }
        # Create a mock response object
        class MockMessage:
            def __init__(self, content):
                self.content = content
        return MockMessage(json.dumps(error_response))

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
        
        raw_content = response.choices[0].message.content
        finish_reason = response.choices[0].finish_reason
        
        logging.info(f"GPT Evaluation Raw Response: {raw_content[:300]}...")
        logging.info(f"GPT Evaluation Finish Reason: {finish_reason}")
        
        # Check if the response was truncated due to hitting max tokens
        if finish_reason == "length":
            logging.error("GPT evaluation response was truncated due to hitting max completion tokens")
            return {
                "error": "GPT evaluation response was truncated due to hitting maximum completion tokens",
                "error_type": "token_limit_exceeded",
                "finish_reason": finish_reason,
                "raw_response": raw_content[:500],
                "original_data": extracted_data,
                "user_action_required": "The evaluation task is too complex for the current model configuration.",
                "recommendations": [
                    "Simplify the extracted data or reduce the amount of data being evaluated",
                    "Process the evaluation in smaller chunks",
                    "Use a model with higher token limits if available"
                ]
            }
        
        try:
            return json.loads(raw_content)
        except json.JSONDecodeError as json_error:
            logging.error(f"GPT evaluation returned invalid JSON: {json_error}")
            logging.error(f"Raw evaluation content: {raw_content}")
            
            # Check if this might be a partial JSON due to truncation
            is_likely_truncated = False
            if raw_content:
                content_stripped = raw_content.strip()
                if (not content_stripped.endswith('}') and not content_stripped.endswith(']')) or \
                   content_stripped.count('{') != content_stripped.count('}') or \
                   content_stripped.count('[') != content_stripped.count(']'):
                    is_likely_truncated = True
                    logging.warning("Evaluation JSON appears to be truncated based on bracket analysis")
            
            if is_likely_truncated:
                return {
                    "error": "GPT evaluation response appears to be truncated, resulting in invalid JSON",
                    "error_type": "likely_truncation",
                    "finish_reason": finish_reason,
                    "json_error": str(json_error),
                    "original_data": extracted_data,
                    "raw_response": raw_content[:500],
                    "user_action_required": "The evaluation response was likely truncated due to complexity.",
                    "recommendations": [
                        "Reduce the 'max_pages_per_chunk' parameter to process smaller document chunks",
                        "Simplify the evaluation criteria by using a more focused JSON schema",
                        "Process evaluation in smaller chunks or split into multiple simpler evaluations",
                        "Consider skipping evaluation for very large documents if extraction quality is sufficient"
                    ]
                }
            
            # Multiple fallback strategies for JSON cleaning
            cleanup_strategies = [
                lambda x: clean_json_response(x),  # Our custom cleaner
                lambda x: x.strip().replace('```json', '').replace('```', '').strip(),  # Simple markdown removal
                lambda x: re.sub(r'^.*?(\{.*\}).*$', r'\1', x, flags=re.DOTALL),  # Extract just the JSON object
                lambda x: re.sub(r'^.*?(\[.*\]).*$', r'\1', x, flags=re.DOTALL),  # Extract just the JSON array
            ]
            
            for i, strategy in enumerate(cleanup_strategies):
                try:
                    cleaned_content = strategy(raw_content)
                    if cleaned_content:
                        result = json.loads(cleaned_content)  # Validate it parses
                        logging.info(f"Successfully cleaned evaluation JSON using strategy {i+1}")
                        return result
                except (json.JSONDecodeError, Exception) as cleanup_error:
                    logging.warning(f"Evaluation cleanup strategy {i+1} failed: {cleanup_error}")
                    continue
            
            logging.error("All evaluation JSON cleanup strategies failed")
            
            # Return structured error with original data
            return {
                "error": "Failed to parse GPT evaluation result after cleanup attempts",
                "error_type": "json_parse_error",
                "finish_reason": finish_reason,
                "json_error": str(json_error),
                "original_data": extracted_data,
                "raw_response": raw_content[:500],
                "user_action_required": "GPT returned malformed evaluation JSON.",
                "recommendations": [
                    "Try running the evaluation again (temporary GPT formatting issue)",
                    "Reduce evaluation complexity by simplifying the JSON schema",
                    "Process evaluation in smaller chunks or with fewer images",
                    "Consider using extraction results without evaluation if quality is acceptable"
                ]
            }
            
    except Exception as e:
        logging.error(f"Failed to get GPT evaluation: {e}")
        return {
            "error": "Failed to get GPT evaluation",
            "exception": str(e),
            "original_data": extracted_data,
            "user_action_required": "An unexpected error occurred during evaluation.",
            "recommendations": [
                "Check network connectivity and API availability",
                "Try running the evaluation again",
                "Reduce document complexity if the issue persists",
                "Consider using extraction results without evaluation"
            ]
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
