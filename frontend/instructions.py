import streamlit as st

def show_instructions():
    st.markdown("""
    ## How to Use the ARGUS System

    ### Introduction
    The ARGUS System is designed to process PDF files to extract data using Azure Document Intelligence and Azure OpenAI. Below are the steps to use the system, along with a detailed explanation of the processes happening behind the scenes.


    ### Step-by-Step Instructions

    #### 1. Uploading Files
    1. **Navigate to the "🧠 Process Files" tab**.
    2. **Select a Dataset**:
       - Choose a dataset from the dropdown menu.
       - The selected dataset will load its corresponding model prompt and example schema.
    3. **Configure the Dataset** (Optional):
       - Modify the model prompt or example schema if needed.
       - Click 'Save' to update the configuration.
    4. **Upload Files**:
       - Use the file uploader to select PDF files for processing.
       - Click 'Submit' to upload the files to Azure Blob Storage.
       - The uploaded files enter a queue for processing and the selected dataset's configuration will be used for extraction.
    5. **What is a Dataset?** 
       - The GPT model processes documents based on the model prompt (which acts as instructions) and the example schema (which is the target data model to be extracted).
       - The example schema can be empty; in this case, the GPT model will create a schema based on the document being processed.

    ---

    #### 2. Exploring Data
    1. **Navigate to the "🔎 Explore Data" tab**.
    2. **Fetch Data**:
       - The system will automatically fetch data from CosmosDB.
       - Data will be displayed in a table, showing the status of each file.
    3. **Interact with Data**:
       - Use the checkboxes to select files for further actions.
       - Use the buttons to refresh the table, delete selected files, or reprocess selected files.
    4. **View Details**:
       - Select exactly one file to view its raw PDF and extracted JSON data.
       - Use the expander to show/hide the detailed view.
    ---

    #### 3. Adding New Dataset
    1. **Navigate to the "🧠 Process Files" tab**.
    2. **Add New Dataset**:
       - Scroll down to the "Add New Dataset" section.
       - Enter a new dataset name, model prompt, and example schema.
       - Click 'Add New Dataset' to create the dataset.
       - The new dataset will be added to the configuration and available for selection.
       
    ---
       
    #### 4. Additional Notes

    - **Reprocessing Failed Files**:
      - For files that have failed, you can trigger reprocessing from the "🔎 Explore Data" tab.

    - **Handling Long Documents**:
      - Extraction accuracy might take a hit on very long documents. In such cases, we recommend splitting the documents into smaller parts before uploading.

    ---- 
    
    ### Backend Processes

    1. **File Upload and Storage**:
       - Uploaded files are sent to Azure Blob Storage.
       - Files are organized into folders based on the selected dataset.

    2. **Triggering Processing**:
       - The upload of a file triggers an Azure Function to start the processing pipeline.
       - The pipeline involves Azure Document Intelligence OCR and a Vision-enabled version of GPT-4.

    3. **Data Extraction**:
       - **Azure Document Intelligence OCR**: Extracts text and structure from the uploaded PDF.
       - **Vision-enabled GPT-4**: Processes the extracted text to generate structured data based on the provided system prompt and example schema.

    4. **Data Storage**:
       - Extracted data is stored in CosmosDB along with metadata and processing logs.
       - The system maintains logs and audit trails for each processed file.

    5. **Data Retrieval and Display**:
       - The "🔎 Explore Data" tab fetches data from CosmosDB.
       - Displays the processing status and details of each file.
       - Allows for reprocessing or deletion of files directly from the interface.

    6. **Configuration Management**:
       - Dataset configurations, including model prompts and example schemas, are stored in CosmosDB.
       - Configurations can be updated through the interface and are used to guide the extraction process.

    ---

    ### Additional Information
    For more details and to view the source code, visit the [Github Repo](https://github.com/albertaga27/azure-doc-extraction-gbb-ai/tree/one-click-deployment).

    ---

    This guide provides a comprehensive overview of the ARGUS System, ensuring that users can effectively upload, process, and manage their documents with ease.
    """)

