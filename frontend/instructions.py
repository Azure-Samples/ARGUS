import streamlit as st

def instructions_tab():
    st.markdown("""    ## How to Use the ARGUS System

    ### Introduction
    The ARGUS System is a comprehensive document processing platform that uses Azure AI services to extract structured data from PDF files. The system uses direct cloud service integration for fast and efficient processing.

    ### System Architecture
    - **Frontend**: Streamlit-based web interface for user interactions
    - **Azure Services**: Document Intelligence, OpenAI, Storage, and Cosmos DB for data processing and storage
    - **Direct Integration**: Frontend connects directly to Azure services for optimal performance

    ### Step-by-Step Instructions    #### 1. Uploading Files
    1. **Navigate to the "🧠 Process Files" tab**.
    2. **Select a Dataset**:
       - Choose a dataset from the dropdown menu.
       - The selected dataset will load its corresponding model prompt and example schema.
    3. **Configure the Dataset** (Optional):
       - Modify the model prompt or example schema if needed.
       - Click 'Save' to update the configuration.
    4. **Upload Files**:
       - Use the file uploader to select PDF files for processing.
       - Click 'Submit' to upload the files directly to cloud storage.
       - The uploaded files are processed automatically using the selected dataset's configuration.
    5. **What is a Dataset?** 
       - A dataset defines how documents should be processed, including:
         - **Model Prompt**: Instructions for the AI model on how to extract data
         - **Example Schema**: The target data structure to be extracted
       - The example schema can be empty; in this case, the AI model will create a schema based on the document content.

    ---

    #### 2. Exploring Data
    1. **Navigate to the "🔎 Explore Data" tab**.
    2. **View Document Statistics**:
       - See overview metrics including total documents, processed count, errors, and datasets
    3. **Filter and Search**:
       - Use the dataset filter to view documents from specific datasets
       - Browse the document list with processing status indicators
    4. **Analyze Processing Status**:
       - View charts showing processing status distribution
       - See dataset distribution across your documents
    5. **View Document Details**:
       - Select individual documents to view detailed information
       - Review extracted content and processing metadata
    6. **Status Indicators**:
       - ✅ Successfully processed
       - ❌ Processing error
       - ➖ Still processing

    ---

    #### 3. Adding New Dataset
    1. **Navigate to the "🧠 Process Files" tab**.
    2. **Add New Dataset**:
       - Scroll down to the "Add New Dataset" section.
       - Enter a new dataset name, model prompt, and example schema.
       - Click 'Add New Dataset' to create the dataset.
       - The new dataset will be saved directly to the database and available for selection.
       
    ---
       
    #### 4. Additional Notes

    - **Reprocessing Failed Files**:
      - For files that have failed, you can trigger reprocessing from the "🔎 Explore Data" tab.

    - **Handling Long Documents**:
      - Extraction accuracy might take a hit on very long documents. In such cases, we recommend splitting the documents into smaller parts before uploading.

    ---- 
    
    ### Processing Pipeline

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

