import os, json
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import streamlit as st

credential = DefaultAzureCredential()


def upload_files_to_blob(files, dataset_name):
    # Connect to the Blob storage account
    blob_service_client = BlobServiceClient(account_url=st.session_state.blob_url, credential=credential)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)

    # Upload each file to the specified dataset folder in Blob storage
    for file in files:
        blob_client = container_client.get_blob_client(f"{dataset_name}/{file.name}")
        blob_client.upload_blob(file)
        st.success(f"File {file.name} uploaded successfully to {dataset_name} folder!")

def fetch_configuration():
    # Connect to the Cosmos DB account
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_config_container_name)
    
    try:
        # Read the configuration item from Cosmos DB
        configuration = container.read_item(item="configuration", partition_key={})
    except Exception as e:
        st.warning("No dataset found, create a new dataset to get started.")
        configuration = {"id": "configuration"}  # Initialize with an empty dataset
    return configuration

def update_configuration(config_data):
    # Connect to the Cosmos DB account
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_config_container_name)

    # Upsert (insert or update) the configuration item in Cosmos DB
    container.upsert_item(config_data)

def process_files_tab():
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        # Fetch configuration from Cosmos DB
        config_data = fetch_configuration()

        # Get the list of dataset options from the configuration
        dataset_options = [key for key, value in config_data.items() if key != 'id' and isinstance(value, dict) and 'model_prompt' in value and 'example_schema' in value]

        # Select a dataset from the options
        selected_dataset = st.selectbox("Select Dataset:", dataset_options)
        
        if selected_dataset:
            # Display the model prompt and example schema for the selected dataset
            model_prompt = config_data[selected_dataset].get("model_prompt", "")
            example_schema = config_data[selected_dataset].get("example_schema", {})

            st.session_state.system_prompt = st.text_area("Model Prompt", value=model_prompt, height=150)
            st.session_state.schema = st.text_area("Example Schema", value=json.dumps(example_schema, indent=4), height=300)

            if st.button('Save'):
                # Update the model prompt and example schema in the configuration
                config_data[selected_dataset]['model_prompt'] = st.session_state.system_prompt
                try:
                    config_data[selected_dataset]['example_schema'] = json.loads(st.session_state.schema)
                    update_configuration(config_data)
                    st.success('Configuration saved!')
                except json.JSONDecodeError:
                    st.error('Invalid JSON format in Example Schema.')

    with col2:
        # Allow the user to upload files to the selected dataset in Blob storage
        uploaded_files = st.file_uploader("Choose files to attach to the request", 
                          type=['pdf', 'jpeg', 'jpg', 'png', 'bmp', 'tiff', 'heif', 'html'], 
                          accept_multiple_files=True)

        if st.button('Submit'):
            if uploaded_files:
                # Upload the files to Blob storage
                upload_files_to_blob(uploaded_files, selected_dataset)
            else:
                st.warning('Please upload some files first.')

        st.markdown("---")

        with st.expander("Add New Dataset"):
            # Allow the user to add a new dataset to the configuration
            new_dataset_name = st.text_input("New Dataset Name:")
            model_prompt = st.text_area("Model Prompt for new dataset", "Extract all data.")
            example_schema = st.text_area("Example Schema for new dataset", "{}")

            if st.button('Add New Dataset'):
                if new_dataset_name and new_dataset_name not in config_data:
                    # Add the new dataset to the configuration
                    config_data[new_dataset_name] = {
                        "model_prompt": model_prompt,
                        "example_schema": json.loads(example_schema)
                    }
                    update_configuration(config_data)
                    st.success(f"New dataset '{new_dataset_name}' added!")
                    # Refresh configuration and select the new dataset
                    config_data = fetch_configuration()
                    st.session_state.selected_dataset = new_dataset_name
                    st.rerun()
                else:
                    st.warning('Please enter a unique dataset name.')
