import streamlit as st
import requests
import json
import base64
import os
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from dotenv import load_dotenv
import pandas as pd
from instructions import show_instructions

# Load environment variables
load_dotenv()

st.set_page_config(layout="wide", page_title="ARGUS System")

# Initialize the session state variables if they are not already set
def initialize_session_state():
    env_vars = {
        'backend_url': "BACKEND_ENDPOINT",
        'system_prompt': "SYSTEM_PROMPT",
        'schema': "OUTPUT_SCHEMA",
        'blob_conn_str': "BLOB_CONN_STR",
        'container_name': "CONTAINER_NAME",
        'cosmos_url': "COSMOS_URL",
        'cosmos_key': "COSMOS_KEY",
        'cosmos_db_name': "COSMOS_DB_NAME",
        'cosmos_documents_container_name': "COSMOS_DOCUMENTS_CONTAINER_NAME",
        'cosmos_config_container_name': "COSMOS_CONFIG_CONTAINER_NAME"
    }
    for var, env in env_vars.items():
        if var not in st.session_state:
            st.session_state[var] = os.getenv(env)

initialize_session_state()

def upload_files_to_blob(files, dataset_name):
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state.blob_conn_str)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)

    for file in files:
        blob_client = container_client.get_blob_client(f"{dataset_name}/{file.name}")
        blob_client.upload_blob(file)
        st.success(f"File {file.name} uploaded successfully to {dataset_name} folder!")

def fetch_data_from_cosmosdb(container_name):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, st.session_state.cosmos_key)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(container_name)

    query = "SELECT * FROM c"
    items = list(container.query_items(query, enable_cross_partition_query=True))
    return pd.json_normalize(items)

def fetch_configuration():
    cosmos_client = CosmosClient(st.session_state.cosmos_url, st.session_state.cosmos_key)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_config_container_name)

    configuration = container.read_item(item="configuration", partition_key={})
    return configuration

def update_configuration(config_data):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, st.session_state.cosmos_key)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_config_container_name)

    container.upsert_item(config_data)

def format_finished(finished, error):
    if finished:
        return '✅'
    elif error:
        return '❌'
    else:
        return '➖'

def refresh_data():
    return fetch_data_from_cosmosdb(st.session_state.cosmos_documents_container_name)

def delete_item(dataset_name, file_name, item_id):
    # Delete the item from CosmosDB
    cosmos_client = CosmosClient(st.session_state.cosmos_url, st.session_state.cosmos_key)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)
    container.delete_item(item=item_id, partition_key={})

    # Delete the file from Blob Storage
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state.blob_conn_str)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)

    blob_client = container_client.get_blob_client(f"{dataset_name}/{file_name}")
    blob_client.delete_blob()

    st.success(f"Deleted {file_name} from {dataset_name} successfully!")

def reprocess_item(dataset_name, file_name):
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state.blob_conn_str)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)
    
    source_blob = f"{dataset_name}/{file_name}"
    temp_blob = f"{dataset_name}/{file_name}"

    try:
        # Copy the blob to a temporary location to trigger the processing
        blob_client = container_client.get_blob_client(source_blob)
        temp_blob_client = container_client.get_blob_client(temp_blob)

        # Copy the blob to the same location to trigger re-processing
        temp_blob_client.start_copy_from_url(blob_client.url)

        st.success(f"Re-processing triggered for {file_name} in {dataset_name} dataset.")
    except Exception as e:
        st.error(f"Failed to re-process {file_name}: {e}")

# Function to fetch PDF from Blob Storage
def fetch_pdf_from_blob(blob_name):
    blob_service_client = BlobServiceClient.from_connection_string(st.session_state.blob_conn_str)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)
    blob_client = container_client.get_blob_client(blob_name)

    pdf_data = blob_client.download_blob().readall()
    return pdf_data

# Function to fetch JSON from CosmosDB
def fetch_json_from_cosmosdb(item_id):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, st.session_state.cosmos_key)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)
    item = container.read_item(item=item_id, partition_key={})
    return item

# Tabs navigation
title = st.header("ARGUS: Automated Retrieval and GPT Understanding System")
tabs = st.tabs(["🧠 Process Files", "🔎 Explore Data", "🖥️ Instructions"])

with tabs[0]:
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        # Fetch configuration from CosmosDB
        config_data = fetch_configuration()

        dataset_options = [key for key, value in config_data.items() if key != 'id' and isinstance(value, dict) and 'model_prompt' in value and 'example_schema' in value]

        selected_dataset = st.selectbox("Select Dataset:", dataset_options)
        
        if selected_dataset:
            model_prompt = config_data[selected_dataset].get("model_prompt", "")
            example_schema = config_data[selected_dataset].get("example_schema", {})

            st.session_state.system_prompt = st.text_area("Model Prompt", value=model_prompt, height=150)
            st.session_state.schema = st.text_area("Example Schema", value=json.dumps(example_schema, indent=4), height=300)

            if st.button('Save'):
                config_data[selected_dataset]['model_prompt'] = st.session_state.system_prompt
                try:
                    config_data[selected_dataset]['example_schema'] = json.loads(st.session_state.schema)
                    update_configuration(config_data)
                    st.success('Configuration saved!')
                except json.JSONDecodeError:
                    st.error('Invalid JSON format in Example Schema.')

    with col2:
        uploaded_files = st.file_uploader("Choose files to attach to the request", type=['pdf'], accept_multiple_files=True)

        if st.button('Submit'):
            if uploaded_files:
                upload_files_to_blob(uploaded_files, selected_dataset)
            else:
                st.warning('Please upload some files first.')

        st.markdown("---")

        with st.expander("Add New Dataset"):
            new_dataset_name = st.text_input("New Dataset Name:")
            model_prompt = st.text_area("Model Prompt for new dataset", "Extract all data.")
            example_schema = st.text_area("Example Schema for new dataset", "{}")

            if st.button('Add New Dataset'):
                if new_dataset_name and new_dataset_name not in config_data:
                    config_data[new_dataset_name] = {
                        "model_prompt": model_prompt,
                        "example_schema": json.loads(example_schema)
                    }
                    update_configuration(config_data)
                    st.success(f"New dataset '{new_dataset_name}' added!")
                    # Refresh configuration and select the new dataset
                    config_data = fetch_configuration()
                    st.session_state.selected_dataset = new_dataset_name
                    st.experimental_rerun()
                else:
                    st.warning('Please enter a unique dataset name.')

with tabs[1]:

    df = refresh_data()
    
    if not df.empty:
        st.toast('Data fetched successfully!')
        # Extract and format relevant fields
        extracted_data = []
        for item in df.to_dict(orient='records'):
            blob_name = item.get('properties.blob_name', '')
            errors = item.get('errors', '')
            extracted_item = {
                'Dataset': blob_name.split('/')[1],
                'File Name': '/'.join(blob_name.split('/')[2:]),
                'File Landed': format_finished(item.get('state.file_landed', False), errors),
                'OCR Extraction': format_finished(item.get('state.ocr_completed', False), errors),
                'GPT Extraction': format_finished(item.get('state.gpt_extraction_completed',False), errors),
                'GPT Summary': format_finished(item.get('state.gpt_summary_completed', False), errors),
                'Finished': format_finished(item.get('state.processing_completed', False), errors),
                'Request Timestamp': datetime.fromisoformat(item.get('properties.request_timestamp', '')),
                'Total Time': item.get('properties.total_time_seconds', 0),
                'Errors': errors,
                'id': item['id'],
            }
            extracted_data.append(extracted_item)

        extracted_df = pd.DataFrame(extracted_data)
        
        # Add a selection column
        extracted_df.insert(0, 'Select', False)
        
        # Sort by request date, most recent first
        extracted_df = extracted_df.sort_values(by='Request Timestamp', ascending=False)
        
        # Display the table with selection checkboxes
        edited_df = st.data_editor(extracted_df, column_config={"id": None})        

        # Find selected rows
        selected_rows = edited_df[edited_df['Select'] == True]
        
        col1, col2 = st.columns(2)
        with col1:
            sub_col1, sub_col2, sub_col3, sub_col4 = st.columns(4)
            
            with sub_col1:
                # Refresh Table button should be below the table
                if st.button('Refresh Table', key='refresh_table'):
                    df = refresh_data()

            with sub_col2:
                if st.button('Delete Selected', key='delete_selected'):
                    for _, row in selected_rows.iterrows():
                        delete_item(row['Dataset'], row['File Name'], row['id'])
                        
            with sub_col3:
                if st.button('Re-process Selected', key='reprocess_selected'):
                    for _, row in selected_rows.iterrows():
                        reprocess_item(row['Dataset'], row['File Name'])

        if len(selected_rows) == 1:
            with st.expander("Show/Hide raw PDF and extracted JSON...", expanded=False):
                selected_item = selected_rows.iloc[0]
                pdf_blob_name = f"{selected_item['Dataset']}/{selected_item['File Name']}"
                json_item_id = selected_item['id']
                    
                pdf_data = fetch_pdf_from_blob(pdf_blob_name)
                with st.spinner('Fetching PDF and JSON data...'):
                    if pdf_data:
                        st.success('PDF fetched successfully!')
                    else:
                        st.error('Failed to fetch PDF data.')

                    json_data = fetch_json_from_cosmosdb(json_item_id)
                    if json_data:
                        st.success('JSON data fetched successfully!')
                    else:
                        st.error('Failed to fetch JSON data.')
                col1, col2 = st.columns(2)
                with col1:
                    if pdf_data:
                        # Display the PDF
                        pdf_base64 = base64.b64encode(pdf_data).decode('utf-8')
                        pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="1200" type="application/pdf"></iframe>'
                        st.markdown(pdf_display, unsafe_allow_html=True)
                with col2:
                    if json_data:
                        # Display the JSON data
                        st.json(json_data['extracted_data']['gpt_extraction_output'])
        elif len(selected_rows) > 1:
            st.warning('Please select exactly one item to show extraction.')
    else:
        st.error('Failed to fetch data or no data found.')

with tabs[2]:
    ## Display instructions
    show_instructions()
