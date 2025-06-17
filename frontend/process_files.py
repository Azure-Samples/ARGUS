import os, json
import streamlit as st
from backend_client import backend_client


def upload_files_to_backend(files, dataset_name):
    """Upload files to the backend API instead of directly to blob storage"""
    success_count = 0
    for file in files:
        try:
            # Read the file content
            file_content = file.read()
            
            # Upload via backend API
            result = backend_client.upload_file(file_content, file.name, dataset_name)
            
            if result.get('status') == 'success':
                st.success(f"File {file.name} uploaded successfully to {dataset_name} folder!")
                success_count += 1
            else:
                st.error(f"Failed to upload {file.name}: {result.get('message', 'Unknown error')}")
        except Exception as e:
            st.error(f"Error uploading {file.name}: {e}")
            
    return success_count

def fetch_configuration():
    """Fetch configuration from the backend API"""
    try:
        configuration = backend_client.get_configuration()
        return configuration
    except Exception as e:
        st.warning("No dataset found, create a new dataset to get started.")
        return {"id": "configuration"}  # Initialize with an empty dataset

def update_configuration(config_data):
    """Update configuration via the backend API"""
    try:
        result = backend_client.update_configuration(config_data)
        return result
    except Exception as e:
        st.error(f"Error updating configuration: {e}")
        return None

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
                          type=['pdf', 'pptx', 'docx', 'xlsx' 'jpeg', 'jpg', 'png', 'bmp', 'tiff', 'heif', 'html'], 
                          accept_multiple_files=True)

        if st.button('Submit'):
            if uploaded_files:
                # Upload the files to Blob storage
                upload_files_to_backend(uploaded_files, selected_dataset)
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
