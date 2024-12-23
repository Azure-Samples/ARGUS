import sys, json
import base64
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import streamlit as st
import pandas as pd
from streamlit_pdf_viewer import pdf_viewer
import plotly.express as px
import plotly.graph_objects as go

credential = DefaultAzureCredential()

def format_finished(finished, error):
    return '✅' if finished else '❌' if error else '➖'

def refresh_data():
    return fetch_data_from_cosmosdb(st.session_state.cosmos_documents_container_name)

def fetch_data_from_cosmosdb(container_name):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(container_name)

    query = "SELECT * FROM c"
    items = list(container.query_items(query, enable_cross_partition_query=True))
    return pd.json_normalize(items)

def delete_item(dataset_name, file_name, item_id):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)
    container.delete_item(item=item_id, partition_key={})

    blob_service_client = BlobServiceClient(account_url=st.session_state.blob_url, credential=credential)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)

    blob_client = container_client.get_blob_client(f"{dataset_name}/{file_name}")
    blob_client.delete_blob()

    st.success(f"Deleted {file_name} from {dataset_name} successfully!")

def reprocess_item(dataset_name, file_name):
    blob_service_client = BlobServiceClient(account_url=st.session_state.blob_url, credential=credential)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)

    source_blob = f"{dataset_name}/{file_name}"
    temp_blob = f"{dataset_name}/{file_name}"

    try:
        blob_client = container_client.get_blob_client(source_blob)
        temp_blob_client = container_client.get_blob_client(temp_blob)

        temp_blob_client.start_copy_from_url(blob_client.url)

        st.success(f"Re-processing triggered for {file_name} in {dataset_name} dataset.")
    except Exception as e:
        st.error(f"Failed to re-process {file_name}: {e}")

def fetch_blob_from_blob(blob_name):
    blob_service_client = BlobServiceClient(account_url=st.session_state.blob_url, credential=credential)
    container_client = blob_service_client.get_container_client(st.session_state.container_name)
    blob_client = container_client.get_blob_client(blob_name)

    blob_data = blob_client.download_blob().readall()
    return blob_data

def fetch_json_from_cosmosdb(item_id):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)
    item = container.read_item(item=item_id, partition_key={})
    return item

def save_feedback_to_cosmosdb(item_id, rating, comments):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)

    item = container.read_item(item=item_id, partition_key={})
    if 'feedback' not in item:
        item['feedback'] = []
    item['feedback'].append({'timestamp': datetime.utcnow().isoformat(), 'rating': rating, 'comments': comments})
    container.upsert_item(item)

def get_existing_feedback(item_id):
    cosmos_client = CosmosClient(st.session_state.cosmos_url, credential)
    database = cosmos_client.get_database_client(st.session_state.cosmos_db_name)
    container = database.get_container_client(st.session_state.cosmos_documents_container_name)

    item = container.read_item(item=item_id, partition_key={})
    if 'feedback' in item and item['feedback']:
        return item['feedback'][-1]  # Return the most recent feedback
    return None

def explore_data_tab():
    df = refresh_data()
    if not df.empty:
        st.toast('Data fetched successfully!')

        extracted_data = []
        for item in df.to_dict(orient='records'):
            blob_name = item.get('properties.blob_name', '')
            errors = item.get('errors', '')
            extracted_item = {
                'Dataset': blob_name.split('/')[1],
                'File Name': '/'.join(blob_name.split('/')[2:]),
                'File Landed': format_finished(item.get('state.file_landed', False), errors),
                'OCR Extraction': format_finished(item.get('state.ocr_completed', False), errors),
                'GPT Extraction': format_finished(item.get('state.gpt_extraction_completed', False), errors),
                'GPT Evaluation': format_finished(item.get('state.gpt_evaluation_completed', False), errors),
                'GPT Summary': format_finished(item.get('state.gpt_summary_completed', False), errors),
                'Finished': format_finished(item.get('state.processing_completed', False), errors),
                'Request Timestamp': datetime.fromisoformat(item.get('properties.request_timestamp', '')),
                'Errors': errors,
                'Total Time': item.get('properties.total_time_seconds', 0),
                'Pages': item.get('properties.num_pages', 0),
                'Size': item.get('properties.blob_size', 0),
                'id': item['id'],
            }
            extracted_data.append(extracted_item)

        extracted_df = pd.DataFrame(extracted_data)
        extracted_df.insert(0, 'Select', False)
        extracted_df = extracted_df.sort_values(by='Request Timestamp', ascending=False)

        st.header("Explore Data")
        filter_col1, filter_col2, filter_col3 = st.columns([3, 1, 1])

        with filter_col1:
            filter_dataset = st.multiselect("Dataset", options=extracted_df['Dataset'].unique(), default=extracted_df['Dataset'].unique())

        with filter_col2:
            filter_finished = st.selectbox("Processing Status", options=['All', 'Finished', 'Not Finished'], index=0)

        with filter_col3:
            filter_date_range = st.date_input("Request Date Range", [])

        filtered_df = extracted_df[
            extracted_df['Dataset'].isin(filter_dataset) &
            (extracted_df['Finished'].apply(lambda x: True if filter_finished == 'All' else (x == '✅' if filter_finished == 'Finished' else (x == '❌' or x == '➖')))) &
            (extracted_df['Request Timestamp'].apply(lambda x: (not filter_date_range) or (x.date() >= filter_date_range[0] and x.date() <= filter_date_range[1])))
        ]

        cols = st.columns([0.5, 10, 0.5])
        with cols[1]:
            tabs_ = st.tabs(["🧮 Table", "📐 Analytics"])

            with tabs_[0]:
                edited_df = st.data_editor(filtered_df, column_config={"id": None})
                selected_rows = edited_df[edited_df['Select'] == True]

                sub_col = st.columns([1, 1, 1, 3])

                with sub_col[0]:
                    if st.button('Refresh Table', key='refresh_table'):
                        df = refresh_data()

                with sub_col[1]:
                    if st.button('Delete Selected', key='delete_selected'):
                        for _, row in selected_rows.iterrows():
                            delete_item(row['Dataset'], row['File Name'], row['id'])
                        st.rerun()

                with sub_col[2]:
                    if st.button('Re-process Selected', key='reprocess_selected'):
                        for _, row in selected_rows.iterrows():
                            reprocess_item(row['Dataset'], row['File Name'])

                if len(selected_rows) == 1:
                    st.markdown("---")
                    ## markdown text with selected item name
                    st.markdown(f"###### {selected_rows.iloc[0]['File Name']}")

                    selected_item = selected_rows.iloc[0]
                    blob_name = f"{selected_item['Dataset']}/{selected_item['File Name']}"
                    json_item_id = selected_item['id']
                    
                    with st.expander("Human in the loop Feedback"):
                        feedback = get_existing_feedback(json_item_id)
                        initial_rating = feedback['rating'] if feedback else None
                        initial_comments = feedback['comments'] if feedback else ""

                        # Feedback section with rating and comments
                        feedback_col1, feedback_col2 = st.columns([1, 2])
                        with feedback_col1:
                            rating = st.slider("Extraction Quality", 1, 10, initial_rating, key="rating")
                        with feedback_col2:
                            comments = st.text_area("Comments on the Extraction", initial_comments, key="comments")

                        if st.button("Done"):
                            save_feedback_to_cosmosdb(json_item_id, rating, comments)
                            st.success("Feedback submitted!")

                    blob_data = fetch_blob_from_blob(blob_name)
                    with st.spinner('Fetching blob and JSON data...'):
                        if blob_data:
                            st.toast('Blob fetched successfully!')
                        else:
                            st.error('Failed to fetch blob data.')

                        json_data = fetch_json_from_cosmosdb(json_item_id)
                        if json_data:
                            st.toast('JSON data fetched successfully!')
                        else:
                            st.error('Failed to fetch JSON data.')

                    pdf_col, json_col = st.columns(2)
                    with pdf_col:
                        if blob_data:
                            file_extension = selected_item['File Name'].split('.')[-1].lower()
                            if file_extension in ['pdf']:
                                if sys.getsizeof(blob_data) > 1500000:
                                    st.toast('PDF file is too large to display in iframe.')
                                    download_link = f'<a href="data:application/octet-stream;base64,{base64.b64encode(blob_data).decode("utf-8")}" download="{blob_name.split("/")[-1]}">Download PDF</a>'
                                    pdf_viewer(blob_data, height=1200)
                                    st.markdown(download_link, unsafe_allow_html=True)
                                pdf_base64 = base64.b64encode(blob_data).decode('utf-8')
                                pdf_display = f'<iframe src="data:application/pdf;base64,{pdf_base64}" width="100%" height="1200" type="application/pdf"></iframe>'
                                st.markdown(pdf_display, unsafe_allow_html=True)
                            elif file_extension in ['jpeg', 'jpg', 'png', 'bmp', 'tiff', 'heif']:
                                image_base64 = base64.b64encode(blob_data).decode('utf-8')
                                image_display = f'<img src="data:image/{file_extension};base64,{image_base64}" width="100%"/>'
                                st.markdown(image_display, unsafe_allow_html=True)
                            elif file_extension in ['docx', 'xlsx', 'pptx', 'html']:
                                download_link = f'<a href="data:application/octet-stream;base64,{base64.b64encode(blob_data).decode("utf-8")}" download="{blob_name.split("/")[-1]}">Download {file_extension.upper()}</a>'
                                st.markdown(download_link, unsafe_allow_html=True)
                            else:
                                st.warning(f'Unsupported file type: {file_extension}')
                    
                    with json_col:
                        if json_data:
                            tabs = st.tabs(["GPT Extraction", "OCR Extraction", "GPT Evaluation", "GPT Summary", "Processing Details"])
                            
                            # OCR Extraction Tab
                            with tabs[1]:
                                try:
                                    ocr_data = json_data['extracted_data']['ocr_output']
                                    # Download button for OCR data
                                    st.download_button(
                                        label="Download OCR Data",
                                        data=ocr_data,
                                        file_name="ocr_extraction.txt",
                                        mime="text/plain"
                                    )
                                    st.text(ocr_data)
                                except KeyError:
                                    st.warning("OCR extraction data not available")
                            
                            # GPT Extraction Tab
                            with tabs[0]:
                                try:
                                    gpt_extraction = json_data['extracted_data']['gpt_extraction_output']
                                    # Download button for GPT extraction
                                    st.download_button(
                                        label="Download GPT Extraction",
                                        data=json.dumps(gpt_extraction, indent=2),
                                        file_name="gpt_extraction.json",
                                        mime="application/json"
                                    )
                                    st.json(gpt_extraction)
                                except KeyError:
                                    st.warning("GPT extraction data not available")
                            
                            # GPT Evaluation Tab
                            with tabs[2]:
                                try:
                                    evaluation_data = json_data['extracted_data']['gpt_extraction_output_with_evaluation']
                                    # Download button for evaluation data
                                    st.download_button(
                                        label="Download Evaluation Data",
                                        data=json.dumps(evaluation_data, indent=2),
                                        file_name="gpt_evaluation.json",
                                        mime="application/json"
                                    )
                                    st.json(evaluation_data)
                                except KeyError:
                                    st.warning("GPT evaluation data not available")
                            
                            # Summary Tab
                            with tabs[3]:
                                try:
                                    summary_data = json_data['extracted_data']['gpt_summary_output']
                                    # Download button for summary
                                    st.download_button(
                                        label="Download Summary",
                                        data=summary_data,
                                        file_name="gpt_summary.md",
                                        mime="text/markdown"
                                    )
                                    st.markdown(summary_data)
                                except KeyError:
                                    st.warning("Summary data not available")
                            with tabs[4]:
                                        try:
                                            # Create a more readable format for the details
                                            details_data = [
                                                ["File ID", json_data['id']],
                                                ["Blob Name", json_data['properties']['blob_name']],
                                                ["Blob Size", f"{json_data['properties']['blob_size']} bytes"],
                                                ["Number of Pages", json_data['properties']['num_pages']],
                                                ["Total Processing Time", f"{json_data['properties']['total_time_seconds']:.2f} seconds"],
                                                ["Request Timestamp", json_data['properties']['request_timestamp']],
                                                ["File Landing Time", f"{json_data['state']['file_landed_time_seconds']:.2f} seconds"],
                                                ["OCR Processing Time", f"{json_data['state']['ocr_completed_time_seconds']:.2f} seconds"],
                                                ["GPT Extraction Time", f"{json_data['state']['gpt_extraction_completed_time_seconds']:.2f} seconds"],
                                                ["GPT Evaluation Time", f"{json_data['state']['gpt_evaluation_completed_time_seconds']:.2f} seconds"],
                                                ["GPT Summary Time", f"{json_data['state']['gpt_summary_completed_time_seconds']:.2f} seconds"],
                                                ["Model Deployment", json_data['model_input']['model_deployment']],
                                                ["Model Prompt", json_data['model_input']['model_prompt']]
                                            ]
                                            
                                            # Convert to DataFrame for better display
                                            df = pd.DataFrame(details_data, columns=['Metric', 'Value'])
                                            
                                            # Display table
                                            st.table(df)
                                            
                                        except KeyError as e:
                                            st.warning(f"Some details are not available: {str(e)}")

                elif len(selected_rows) > 1:
                    st.warning('Please select exactly one item to show extraction.')

            with tabs_[1]:
                col1, col2 = st.columns(2)

                with col1:
                    try:
                        success_counts = filtered_df['Finished'].value_counts()
                        labels = ['Successful', 'Processing', 'Not Successful']
                        sizes = [success_counts.get('✅', 0), success_counts.get('➖', 0), success_counts.get('❌', 0)]
                        colors = ['green', 'orange', 'red']

                        fig3 = go.Figure(data=[go.Pie(labels=labels, values=sizes, marker=dict(colors=colors))])
                        fig3.update_traces(textinfo='label+percent', textfont_size=12)
                        fig3.update_layout(title_text='Processing Status')
                        st.plotly_chart(fig3)
                    except Exception as e:
                        st.error(f"Error in creating the pie chart: {e}")

                with col2:
                    try:
                        fig1 = px.histogram(filtered_df, x='Dataset', title='Number of Files per Dataset', labels={'x': 'Dataset', 'y': 'Number of Files'})
                        fig1.update_layout(xaxis_title_text='Dataset', yaxis_title_text='Number of Files')
                        st.plotly_chart(fig1)
                    except Exception as e:
                        st.error(f"Error in creating the histogram: {e}")

                col3, col4 = st.columns([1, 1])

                with col3:
                    try:
                        fig2 = px.histogram(filtered_df, x='Total Time', nbins=20, title='Distribution of Processing Time', labels={'x': 'Processing Time (seconds)', 'y': 'Number of Files'})
                        fig2.update_layout(xaxis_title_text='Processing Time (seconds)', yaxis_title_text='Number of Files')
                        st.plotly_chart(fig2)
                    except Exception as e:
                        st.error(f"Error in creating the histogram: {e}")

                with col4:
                    try:
                        fig5 = px.scatter(filtered_df, x='Size', y='Total Time', title='Processing Time vs. File Size', labels={'x': 'File Size (bytes)', 'y': 'Processing Time (seconds)'})
                        fig5.update_layout(xaxis_title_text='File Size (bytes)', yaxis_title_text='Processing Time (seconds)')
                        st.plotly_chart(fig5)
                    except Exception as e:
                        st.error(f"Error in creating the scatter plot: {e}")

                col5, col6 = st.columns([1, 1])
                with col5:
                    try:
                        fig4 = px.scatter(filtered_df[filtered_df['Pages'] > 0], x='Request Timestamp', y='Total Time', color='Pages', title='Processing Time per Page by Request Timestamp', labels={'x': 'Request Timestamp', 'y': 'Processing Time (seconds)'})
                        fig4.update_layout(xaxis_title_text='Request Timestamp', yaxis_title_text='Processing Time (seconds)')
                        st.plotly_chart(fig4)
                    except Exception as e:
                        st.error(f"Error in creating the scatter plot: {e}")
                with col6:
                    try:
                        fig6 = px.histogram(filtered_df, x='Pages', title='Number of Pages per File', labels={'x': 'Number of Pages', 'y': 'Number of Files'})
                        fig6.update_layout(xaxis_title_text='Number of Pages', yaxis_title_text='Number of Files')
                        st.plotly_chart(fig6)
                    except Exception as e:
                        st.error(f"Error in creating the histogram: {e}")

    else:
        st.error('Failed to fetch data or no data found. If you submitted files for processing, please wait a few seconds and refresh the page.')
