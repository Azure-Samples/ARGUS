# ARGUS: Automated Retrieval and GPT Understanding System
### 

> Argus Panoptes, in ancient Greek mythology, was a giant with a hundred eyes and a servant of the goddess Hera. His many eyes made him an excellent watchman, as some of his eyes would always remain open while the others slept, allowing him to be ever-vigilant.


## This solution demonstrates Azure Document Intelligence + GPT4 Vision

Classic OCR (Object Character Recognition) models lack reasoning ability based on context when extracting information from documents. In this project we demonstrate how to use a hybrid approach with OCR and LLM (multimodal Large Language Model) to get better results without any pre-training.

This solution uses Azure Document Intelligence combined with GPT4-Vision. Each of the tools have their strong points and the hybrid approach is better than any of them alone.

> Notes:
> - The Azure OpenAI model needs to be vision capable i.e. GPT-4T-0125, 0409 or Omni


## Solution Overview

- **Frontend**: A Streamlit Python web-app for user interaction. UNDER CONSTRUCTION
- **Backend**: An Azure Function for core logic, Cosmos DB for auditing, logging, and storing output schemas, Azure Document Intelligence, GPT-4 Vision and a Logic App for integrating with Outlook Inbox.
- **Demo**: Sample documents, system prompts, and output schemas.

![architecture](docs/ArchitectureOverview.png)

## Prerequisites
### Azure OpenAI Resource

Before deploying the solution, you need to create an OpenAI resource and deploy a model that is vision capable.

1. **Create an OpenAI Resource**:
   - Follow the instructions [here](https://learn.microsoft.com/en-us/azure/cognitive-services/openai/how-to/create-resource) to create an OpenAI resource in Azure.

2. **Deploy a Vision-Capable Model**:
   - Ensure the deployed model supports vision, such as GPT-4T-0125, GPT-4T-0409 or GPT-4-Omni.


## Deployment

### One-Click Deployment

Click the button to directly deploy to Azure: 

[![Deploy to Azure](https://aka.ms/deploytoazurebutton)](https://portal.azure.com/#create/Microsoft.Template/uri/https%3A%2F%2Fraw.githubusercontent.com%2FAzure-Samples%2FARGUS%2Fmain%2Finfra%2Fmain.json)

`Deploy to Azure` offers a one click deployment without cloning the code. Alternatively, follow the instructions below.

### Deployment with `azd up`

1. **Prerequisites**:
   - Install [Azure Developer CLI](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd).
   - Ensure you have access to an Azure subscription.
   - Create an OpenAI resource and deploy a vision-capable model.

2. **Deployment Steps**:
   - Run the following command to deploy all resources:
     ```sh
     azd up
     ```

### Alternative: Manual Deployment

1. **Bicep Template Deployment**:
   - Use the provided `main.bicep` file to deploy resources manually:
     ```sh
     az deployment group create --resource-group <your-resource-group> --template-file main.bicep
     ```

> Note: After deployment wait for about 10 minutes for the docker images to be pulled. You can check the progress in your Functionapp > Deployment Center > Logs.

## Running the Streamlit Frontend (recommended)

To run the Streamlit app `app.py` located in the `frontend` folder, follow these steps:

1. Install the required dependencies by running the following command in your terminal:
   ```sh
   pip install -r frontend/requirements.txt
   ```

2. Rename the `.env.temp` file to `.env`:
   ```sh
   mv frontend/.env.temp frontend/.env
   ```

3. Populate the `.env` file with the necessary environment variables. Open the `.env` file in a text editor and provide the required values for each variable.

4. Assign a CosmsosDB and Blob Storage Role to your Principal ID:

   Get the `principal ID` of the currently signed-in user:
   ```
   az ad signed-in-user show --query id -o tsv
   ```
   Then, create Cosmos and Blob `role assignments`:
   ```
   az cosmosdb sql role assignment create \
      --principal-id "<principal-id>" \
      --resource-group "<resource-group-name>" \
      --account-name "<cosmos-account-name>" \
      --role-definition-name "CosmosBackupOperator" \
      --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.DocumentDB/databaseAccounts/<cosmos-account-name>"
   ```
   ```
   az role assignment create \
      --assignee "<principal-id>" \
      --role "Storage Blob Data Contributor" \
      --scope "/subscriptions/<subscription-id>/resourceGroups/<resource-group-name>/providers/Microsoft.Storage/storageAccounts/<storage-account-name>/blobServices/default/containers/<container-name>"
   ```

5. Start the Streamlit app by running the following command in your terminal:
   ```sh
   streamlit run frontend/app.py
   ```

## Running the Outlook integration with Logic App

You can connect a Outlook inbox to send incoming attachments directly to the blob storage to trigger the extraction process. For that a Logic App was already built for you. The only thing you need to do is to open the resource "LogicAppName" add a trigger and connect it to your Outlook inbox. Open this [Microsoft Learn page](https://learn.microsoft.com/en-us/azure/logic-apps/tutorial-process-email-attachments-workflow) and search for "Add a trigger to check incoming email" follow the described steps then activate it with the "Run" button. 


## How to Use

### Upload and Process Documents

1. **Upload PDF Files**:
   - Navigate to the `sa-uniqueID` storage account and the `datasets` container
   - Create a new folder called `default-dataset` and upload your PDF files.

2. **View Results**:
   - Processed results will be available in your Cosmos DB database under the `doc-extracts` collection and the `documents` container.


## Model Input Instructions

The input to the model consists of two main components: a `model prompt` and a `JSON template` with the schema of the data to be extracted.

### `Model Prompt`

The prompt is a textual instruction explaining what the model should do, including the type of data to extract and how to extract it. Here are a couple of example prompts:

1. **Default Prompt**:
Extract all data from the document. 

2. **Example Prompt**:
Extract all financial data, including transaction amounts, dates, and descriptions from the document. For date extraction use american formatting. 


### `JSON Template`

The JSON template defines the schema of the data to be extracted. This can be an empty JSON object `{}` if the model is supposed to create its own schema. Alternatively, it can be more specific to guide the model on what data to extract or for further processing in a structured database. Here are some examples:

1. Empty JSON Template (default):
```json
{}
```
2. Specific JSON Template Example:
```
{
    "transactionDate": "",
    "transactionAmount": "",
    "transactionDescription": ""
}
```
By providing a prompt and a JSON template, users can control the behavior of the model to extract specific data from their documents in a structured manner.

- JSON Schemas created using [JSON Schema Builder](https://bjdash.github.io/JSON-Schema-Builder/).



## Team behind ARGUS

- [Alberto Gallo](https://github.com/albertaga27)
- [Petteri Johansson](https://github.com/piizei)
- [Christin Pohl](https://github.com/pohlchri)
- [Konstantinos Mavrodis](https://github.com/kmavrodis_microsoft)


---

This README file provides an overview and quickstart guide for deploying and using Project ARGUS. For detailed instructions, consult the documentation and code comments in the respective files.
