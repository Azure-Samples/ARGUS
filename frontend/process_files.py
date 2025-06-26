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
        # Information box about datasets
        st.info("**📊 Datasets** are pre-configured profiles with custom AI prompts and schemas for different document types (invoices, contracts, etc.)")
        
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
            max_pages_per_chunk = dataset_config.get("max_pages_per_chunk", 10)
            
            # Get current processing options with defaults
            processing_options = dataset_config.get("processing_options", {
                "include_ocr": True,
                "include_images": True,
                "enable_summary": True,
                "enable_evaluation": True
            })

            st.session_state.system_prompt = st.text_area("Model Prompt", value=model_prompt, height=150)
            st.session_state.schema = st.text_area("Example Schema", value=json.dumps(example_schema, indent=4), height=300)
            st.session_state.max_pages_per_chunk = st.number_input("Document Chunk Size (pages)", 
                                                                   min_value=1, 
                                                                   max_value=100, 
                                                                   value=max_pages_per_chunk, 
                                                                   help="For large documents, this controls how many pages are processed together in each chunk. Smaller chunks (1-5 pages) provide more focused extraction but may miss connections across pages. Larger chunks (10-20 pages) maintain context better but may hit processing limits. Most documents work well with 5-15 pages per chunk.")

            # Processing Options section
            st.markdown("Configure which processing steps to perform:")
            
            col_a, col_b = st.columns(2)
            
            with col_a:
                include_ocr = st.checkbox(
                    "📄 Run OCR and use it in GPT Extraction", 
                    value=processing_options.get("include_ocr", True),
                    help="Extract and analyze the text content from your documents using Optical Character Recognition (OCR). This captures all written information including tables, forms, and structured data. Essential for text-heavy documents like contracts, invoices, and reports. When enabled, the AI can understand and extract information from the document's text content."
                )
                
                include_images = st.checkbox(
                    "🖼️ Split in Images and use them in GPT Extraction", 
                    value=processing_options.get("include_images", True),
                    help="Process document pages as images so the AI can visually understand layouts, charts, diagrams, handwritten notes, and visual elements that OCR might miss. This is particularly valuable for forms with checkboxes, complex layouts, signatures, charts, or documents where visual context matters. Combines with OCR for the most comprehensive analysis."
                )
            
            # Validation: Ensure at least one of OCR or Images is enabled
            if not include_ocr and not include_images:
                st.error("⚠️ **Validation Error**: You must enable at least one of 'Include OCR Text' or 'Include Images' for GPT extraction to work properly.")
                # Force at least one to be true
                include_ocr = True
                st.warning("🔧 **Auto-correction**: Automatically re-enabled 'Include OCR Text' to ensure proper functionality.")
            
            with col_b:
                enable_summary = st.checkbox(
                    "📋 Generate Summary", 
                    value=processing_options.get("enable_summary", True),
                    help="Create an intelligent summary of each document including key topics, main points, document type classification, and important insights. This helps you quickly understand what each document contains without reading the full content. Useful for document organization and quick review."
                )
                
                enable_evaluation = st.checkbox(
                    "🔍 Enable Data Evaluation", 
                    value=processing_options.get("enable_evaluation", True),
                    help="Perform additional quality checks and validation on the extracted data using advanced AI evaluation. This includes confidence scoring, data completeness analysis, and enrichment suggestions. Helps ensure the extracted information is accurate and complete, especially important for critical business documents."
                )
            
            # Store processing options in session state
            st.session_state.processing_options = {
                "include_ocr": include_ocr,
                "include_images": include_images,
                "enable_summary": enable_summary,
                "enable_evaluation": enable_evaluation
            }
            
            # Show cost/performance impact
            enabled_steps = sum([include_ocr or include_images, enable_summary, enable_evaluation])
            if enabled_steps <= 1:
                st.info("💡 **Cost Optimized**: Only core extraction enabled - fastest and most cost-effective.")
            elif enabled_steps == 2:
                st.info("💡 **Balanced**: Good balance of features and cost.")
            else:
                st.warning("💡 **Full Processing**: All features enabled - highest cost and processing time.")

            if st.button('Save'):
                # Update the configuration including processing options
                config_data["datasets"][selected_dataset]['model_prompt'] = st.session_state.system_prompt
                config_data["datasets"][selected_dataset]['max_pages_per_chunk'] = st.session_state.max_pages_per_chunk
                config_data["datasets"][selected_dataset]['processing_options'] = st.session_state.processing_options
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
            new_max_pages_per_chunk = st.number_input("Max Pages per Chunk for new dataset", 
                                                      min_value=1, 
                                                      max_value=100, 
                                                      value=10, 
                                                      help="Maximum number of pages to include in each document chunk when splitting large documents")

            # Processing options for new dataset
            st.markdown("**Processing Options for New Dataset:**")
            col_new_a, col_new_b = st.columns(2)
            
            with col_new_a:
                new_include_ocr = st.checkbox("📄 Include OCR Text", value=True, key="new_ocr", 
                                            help="Include extracted text in GPT analysis. If disabled, Document Intelligence will be skipped.")
                new_include_images = st.checkbox("🖼️ Include Images", value=True, key="new_images",
                                                help="Include document images in GPT analysis.")
            
            # Validation for new dataset options
            if not new_include_ocr and not new_include_images:
                st.error("⚠️ **Validation Error**: You must enable at least one of 'Include OCR Text' or 'Include Images' for the new dataset.")
                new_include_ocr = True
                st.warning("🔧 **Auto-correction**: Automatically enabled 'Include OCR Text' for the new dataset.")
            
            with col_new_b:
                new_enable_summary = st.checkbox("📋 Generate Summary", value=True, key="new_summary")
                new_enable_evaluation = st.checkbox("🔍 Enable Evaluation", value=True, key="new_evaluation")

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
                            "example_schema": parsed_schema,
                            "max_pages_per_chunk": new_max_pages_per_chunk,
                            "processing_options": {
                                "include_ocr": new_include_ocr,
                                "include_images": new_include_images,
                                "enable_summary": new_enable_summary,
                                "enable_evaluation": new_enable_evaluation
                            }
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

        # Processing Options Help (moved outside the expander)
        with st.expander("💡 Processing Options Help"):
            st.markdown("""
            **Processing Pipeline Overview:**
            
            1. **📄 OCR Text Extraction** (Conditional - only runs if OCR text is needed)
               - ✅ *Include OCR Text*: Run Document Intelligence to extract text and send to GPT
               - ❌ *Skip OCR Text*: Skip Document Intelligence entirely, use only images for GPT analysis
            
            2. **🖼️ Image Processing** (Conditional - only runs if images are needed)
               - ✅ *Include Images*: Send document images to GPT for visual understanding
               - ❌ *Skip Images*: Use only OCR text for analysis (faster, lower cost)
            
            **⚠️ Important**: You must enable at least one of OCR or Images for GPT extraction to work.
            
            3. **🔍 Data Extraction** (Always runs)
               - Extracts structured data based on your schema using GPT
            
            4. **🔍 Data Evaluation** (Optional)
               - ✅ *Enable*: Additional GPT call to validate 
               - ❌ *Disable*: Use raw extraction results (faster, lower cost)
            
            5. **📋 Summary** (Optional)
               - ✅ *Enable*: Generate document summary 
               - ❌ *Disable*: Skip summary generation (faster, lower cost)
            
            **Cost & Performance Impact:**
            - Disabling OCR saves on Document Intelligence costs when you only need visual analysis
            - Each enabled option adds GPT API calls and processing time
            - **Recommended for testing**: Enable all options for best results
            - **Recommended for production**: Customize based on your specific needs
            - **For cost optimization**: Disable evaluation and summary if not needed
            """)
