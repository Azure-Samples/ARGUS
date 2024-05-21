# AI OCR with Azure and OpenAI

## This project demonstrates Documents OCR with Azure Cognitive Services and GPT4 Vision

Classic OCR models need training to extract structured information from documents.
In this project we demonstrate how to use hybrid approach with LLM (multimodal) to get better results without any pre-training.

The project uses Azure Document Intelligence combined with GPT4 and GPT-Vision. Each of the tools have their strong points and the hybrid approach is better than any of them alone.

Notes:
- The document-intelligence needs to be using the markdown preview (limited regions: West EU adn East US at the moment). 
- The openai model needs to be vision capable i.e. GPT-4T-0125 or 0409

The Solution structure looks like this:
- frontend  
-- streamlit python web-app  
  
- backend  
-- azure function exposed endpoint for core logic  
-- cosmosDB for auditing logging and output schemas storage  
-- Jupyter notebook for fast testing
-- Jupyter notebook Evaluator (WIP) to derive an accuracy between data in the images/doc vs filled in the output schema
  
- demo  
-- folder with some samples, system prompts and output schemas  
  
- docker  

## Credits
Core functionalities library for the combination of document intelligence and GPT done by Petteri Johansson.
https://github.com/piizei/azure-ai-ocr/tree/main/ai_ocr

## How to use

*Complete the .env files before running.*

Local (VSCode):
1. Pull up the Azure function in the backend (VS Code Studio -> Attach Python Function to debug)  
    1. Azure Function only works with Python version 3.7 to 3.11 (NOT 3.12 which is also stable version)  
    2. When creating the local Azure Functions project one needs to select Python (Programming Model V2) NOT just Python  
    3. local.settings.json Blob storage file needs to be created locally and configured with your own azure blob storage endpoint and key
2. Use the streamlint app.py under frontend folder to use UI for:  
    1. configuration of system prompt, backend URL and schema (env file)  
    2. upload document to be processed  
    3. See summary and raw responses  

Local (Docker)
1. Configure the docker folder according to your local containers and images
2. Run the docker_run.sh to build and push the images
3. Docker compose (yml file provided) or: docker compose -f "docker/docker-compose.yml" up -d --build

### Notes on the examples
- Used https://bjdash.github.io/JSON-Schema-Builder/ to create the json-schemas in the example folders. If the keys in the json model are not self-explanatory, you should use description fields to tell the LLM model what you mean by each key to increase accuracy.
- Alternatively you can ask GPT4T to come up with a schema for you.
- The Solution also works with empty output schema i.e.: { }

### WIP

TODO:
- 1-click deployment:
-- Bicep / ARM file
- Code review
- GET API of backend function used for the journal, TODO: move it to different admin backend API
- Plug the Evaluator in the processing
- Raise cases to human feedback in the UI below a certain evaluator threshold
