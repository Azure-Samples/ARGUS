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
> - The document-intelligence resource needs to use the markdown preview feature (limited regions: West EU adn East US at the moment). 
> - The Azure OpenAI model needs to be vision capable i.e. GPT-4T-0125, 0409 or Omni

Install requirements.txt provided.


### Notebook flow

1. Run ARGUS on an Invoice sample from the demo/default-dataset folder
2. It creates images out of the invoice and place it ina /tmp/ folder
3. Saves the output in json format
3. An Evaluating prompt and call test the accuracy of what is expected (output schema) vs the first run output (images are also used in the evaluation)
