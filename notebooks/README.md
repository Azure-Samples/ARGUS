# Evaluating ARGUS
### 

> This notebook illustrate how to double check a first run of the Solution against an expected output.


### Notebook instructions

Create a .env file in the notebook folder with these keys:

DOCUMENT_INTELLIGENCE_ENDPOINT=
DOCUMENT_INTELLIGENCE_KEY=
AZURE_OPENAI_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_MODEL_DEPLOYMENT_NAME=

> Notes:
> - The document-intelligence resource needs to use the markdown preview feature (limited regions: West EU and East US at the moment). 
> - The Azure OpenAI model needs to be vision capable i.e. GPT-4T-0125, 0409 or Omni

Install requirements.txt provided.


### Notebook flow

1. Run ARGUS on an Invoice sample from the demo/default-dataset folder
2. Saves the output in json format
3. Run evaluation using LLM as a judge without ground truth data
4. Run evaluation using ground truth

### Evaluation using ground truth data

This approach provides a way to evaluate actual JSON against ground truth data.
The ground truth data suppose to be manually verified by the human and adhere to the schema provided to Argus solution.
The end result is a combination of total summary (ratio) with detailed information of comparison for each field. The output is a JSON file stored in [outputs folder](./outputs)
[Json evaluator](../src/evaluators/json_evaluator.py) can use different mechanisms of comparing string values. For now we provide configurable [custom string evaluator](src/evaluators/custom_string_evaluator.py) and [fuzzy match evaluator](src/evaluators/fuzz_string_evaluator.py). It can be expanded to support other string evaluation techniques that might include LLM calls in combination with ground truth.
The ratio is calculated based on the total number of strings being matched between ground truth and actual divided by the total number of values being compared.