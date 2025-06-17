import os, json
import streamlit as st

try:
    from azure.storage.blob import BlobServiceClient
    from azure.identity import DefaultAzureCredential
    from azure.cosmos import CosmosClient
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False


def upload_files_to_blob_storage(files, dataset_name):
    """Upload files directly to blob storage - blob trigger will handle processing"""
    if not AZURE_SDK_AVAILABLE:
        st.error("Azure SDK not available. Please install azure-storage-blob and azure-identity.")
        return 0
    
    # Get storage account details from environment
    blob_account_url = os.getenv('BLOB_ACCOUNT_URL')
    container_name = os.getenv('CONTAINER_NAME', 'datasets')
    
    if not blob_account_url:
        st.error("Storage account configuration not found. Please check environment variables.")
        return 0
    
    success_count = 0
    
    try:
        # Initialize blob service client with managed identity
        credential = DefaultAzureCredential()
        blob_service_client = BlobServiceClient(account_url=blob_account_url, credential=credential)
        
        for file in files:
            try:
                # Reset file pointer to beginning
                file.seek(0)
                file_content = file.read()
                
                # Upload to blob storage in the dataset subdirectory
                blob_name = f"{dataset_name}/{file.name}"
                blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
                
                # Upload the file
                blob_client.upload_blob(file_content, overwrite=True)
                
                st.success(f"File {file.name} uploaded successfully to {dataset_name} folder! Processing will begin automatically.")
                success_count += 1
                
            except Exception as e:
                st.error(f"Error uploading {file.name}: {str(e)}")
                
    except Exception as e:
        st.error(f"Error connecting to storage account: {str(e)}")
            
    return success_count

def fetch_configuration():
    """Fetch configuration from Cosmos DB"""
    if not AZURE_SDK_AVAILABLE:
        st.error("Azure SDK not available. Cannot fetch configuration.")
        return {
            "id": "configuration", 
            "partitionKey": "configuration",
            "datasets": {}
        }
    
    try:
        # Get configuration from session state
        cosmos_url = st.session_state.get('cosmos_url')
        cosmos_db_name = st.session_state.get('cosmos_db_name')
        cosmos_config_container_name = st.session_state.get('cosmos_config_container_name')
        
        if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
            st.error("Missing Cosmos DB configuration. Please check environment variables.")
            return {
                "id": "configuration",
                "partitionKey": "configuration",
                "datasets": {}
            }
        
        # Initialize Cosmos client
        credential = DefaultAzureCredential()
        cosmos_client = CosmosClient(cosmos_url, credential=credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Try to fetch the configuration document
        try:
            config_doc = container.read_item(
                item="configuration", 
                partition_key="configuration"
            )
            return config_doc
        except Exception as read_error:
            # If configuration doesn't exist, create a default one
            default_config = {
                "id": "configuration",
                "partitionKey": "configuration", 
                "datasets": {}
            }
            
            try:
                container.create_item(default_config)
                return default_config
            except Exception as create_error:
                st.warning(f"Could not create default configuration: {str(create_error)}")
                return default_config
                
    except Exception as e:
        st.error(f"Failed to fetch configuration from Cosmos DB: {str(e)}")
        return {
            "id": "configuration",
            "partitionKey": "configuration",
            "datasets": {}
        }

def update_configuration(config_data):
    """Update configuration in Cosmos DB"""
    if not AZURE_SDK_AVAILABLE:
        st.error("Azure SDK not available. Cannot update configuration.")
        return None
    
    try:
        # Get configuration from session state
        cosmos_url = st.session_state.get('cosmos_url')
        cosmos_db_name = st.session_state.get('cosmos_db_name')
        cosmos_config_container_name = st.session_state.get('cosmos_config_container_name')
        
        if not all([cosmos_url, cosmos_db_name, cosmos_config_container_name]):
            st.error("Missing Cosmos DB configuration. Please check environment variables.")
            return None
        
        # Initialize Cosmos client
        credential = DefaultAzureCredential()
        cosmos_client = CosmosClient(cosmos_url, credential=credential)
        database = cosmos_client.get_database_client(cosmos_db_name)
        container = database.get_container_client(cosmos_config_container_name)
        
        # Update the configuration document
        try:
            response = container.upsert_item(config_data)
            st.success("Configuration updated successfully!")
            return response
        except Exception as e:
            st.error(f"Failed to update configuration: {str(e)}")
            return None
            
    except Exception as e:
        st.error(f"Failed to connect to Cosmos DB: {str(e)}")
        return None

def process_files_tab():
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        # Fetch configuration from Cosmos DB
        config_data = fetch_configuration()

        # Get the list of dataset options from the configuration
        datasets = config_data.get("datasets", {})
        dataset_options = [key for key, value in datasets.items() if isinstance(value, dict) and 'model_prompt' in value and 'example_schema' in value]

        # Select a dataset from the options
        selected_dataset = st.selectbox("Select Dataset:", dataset_options)
        
        if selected_dataset:
            # Display the model prompt and example schema for the selected dataset
            dataset_config = datasets[selected_dataset]
            model_prompt = dataset_config.get("model_prompt", "")
            example_schema = dataset_config.get("example_schema", {})

            st.session_state.system_prompt = st.text_area("Model Prompt", value=model_prompt, height=150)
            st.session_state.schema = st.text_area("Example Schema", value=json.dumps(example_schema, indent=4), height=300)

            if st.button('Save'):
                # Update the model prompt and example schema in the configuration
                config_data["datasets"][selected_dataset]['model_prompt'] = st.session_state.system_prompt
                try:
                    config_data["datasets"][selected_dataset]['example_schema'] = json.loads(st.session_state.schema)
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
                upload_files_to_blob_storage(uploaded_files, selected_dataset)
            else:
                st.warning('Please upload some files first.')

        st.markdown("---")

        with st.expander("Add New Dataset"):
            # Allow the user to add a new dataset to the configuration
            new_dataset_name = st.text_input("New Dataset Name:")
            model_prompt = st.text_area("Model Prompt for new dataset", "Extract all data.")
            example_schema = st.text_area("Example Schema for new dataset", "{}")

            if st.button('Add New Dataset'):
                if new_dataset_name and new_dataset_name not in config_data.get("datasets", {}):
                    # Ensure datasets key exists
                    if "datasets" not in config_data:
                        config_data["datasets"] = {}
                    
                    # Add the new dataset to the configuration
                    try:
                        parsed_schema = json.loads(example_schema)
                        config_data["datasets"][new_dataset_name] = {
                            "model_prompt": model_prompt,
                            "example_schema": parsed_schema
                        }
                        update_configuration(config_data)
                        st.success(f"New dataset '{new_dataset_name}' added!")
                        # Refresh configuration and select the new dataset
                        config_data = fetch_configuration()
                        st.session_state.selected_dataset = new_dataset_name
                        st.rerun()
                    except json.JSONDecodeError:
                        st.error('Invalid JSON format in Example Schema.')
                else:
                    st.warning('Please enter a unique dataset name.')
