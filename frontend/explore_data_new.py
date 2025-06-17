import sys, json
import base64
from datetime import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from backend_client import backend_client


def format_finished(finished, error):
    return '✅' if finished else '❌' if error else '➖'

def refresh_data():
    """Refresh data from the backend"""
    try:
        documents = backend_client.get_documents()
        if documents:
            return pd.json_normalize(documents)
        else:
            return pd.DataFrame()
    except Exception as e:
        st.error(f"Error fetching data from backend: {e}")
        return pd.DataFrame()

def explore_data_tab():
    st.header("Explore Processed Data")
    
    # Add refresh button
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Refresh Data"):
            st.rerun()
    
    try:
        df = refresh_data()
        
        if df.empty:
            st.info("No data available. Upload some files first to see processed documents here.")
            return
        
        st.toast('Data fetched successfully!')
        
        # Display basic statistics
        st.subheader("📊 Document Statistics")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Documents", len(df))
        
        with col2:
            finished_count = df['finished'].sum() if 'finished' in df.columns else 0
            st.metric("Processed", finished_count)
        
        with col3:
            error_count = df['error'].sum() if 'error' in df.columns else 0
            st.metric("Errors", error_count)
        
        with col4:
            datasets = df['dataset'].nunique() if 'dataset' in df.columns else 0
            st.metric("Datasets", datasets)
        
        # Display data table
        st.subheader("📋 Document List")
        
        # Filter by dataset if available
        if 'dataset' in df.columns:
            datasets = df['dataset'].unique()
            selected_dataset = st.selectbox("Filter by Dataset", ['All'] + list(datasets))
            
            if selected_dataset != 'All':
                df = df[df['dataset'] == selected_dataset]
        
        # Display columns to show
        display_columns = []
        for col in ['file_name', 'dataset', 'finished', 'error', 'created_at', 'modified_at']:
            if col in df.columns:
                display_columns.append(col)
        
        if display_columns:
            # Format the dataframe for display
            display_df = df[display_columns].copy()
            
            # Format boolean columns
            if 'finished' in display_df.columns:
                display_df['Status'] = display_df.apply(
                    lambda row: format_finished(row.get('finished', False), row.get('error', False)), 
                    axis=1
                )
            
            st.dataframe(display_df, use_container_width=True)
        else:
            st.dataframe(df, use_container_width=True)
        
        # Processing status chart
        if 'finished' in df.columns:
            st.subheader("📈 Processing Status")
            
            status_data = []
            for _, row in df.iterrows():
                if row.get('finished', False):
                    status_data.append('Completed')
                elif row.get('error', False):
                    status_data.append('Error')
                else:
                    status_data.append('Processing')
            
            status_df = pd.DataFrame({'Status': status_data})
            status_counts = status_df['Status'].value_counts()
            
            fig = px.pie(values=status_counts.values, names=status_counts.index, 
                        title="Document Processing Status")
            st.plotly_chart(fig, use_container_width=True)
        
        # Dataset distribution
        if 'dataset' in df.columns:
            st.subheader("📊 Dataset Distribution")
            dataset_counts = df['dataset'].value_counts()
            
            fig = px.bar(x=dataset_counts.index, y=dataset_counts.values,
                        title="Documents per Dataset",
                        labels={'x': 'Dataset', 'y': 'Number of Documents'})
            st.plotly_chart(fig, use_container_width=True)
        
        # Display individual document details
        st.subheader("🔍 Document Details")
        
        if len(df) > 0:
            # Select a document to view details
            document_options = []
            for _, row in df.iterrows():
                filename = row.get('file_name', 'Unknown')
                dataset = row.get('dataset', 'Unknown')
                document_options.append(f"{filename} ({dataset})")
            
            selected_doc = st.selectbox("Select document to view details:", document_options)
            
            if selected_doc:
                # Find the selected document
                selected_idx = document_options.index(selected_doc)
                selected_row = df.iloc[selected_idx]
                
                # Display document details
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write("**Document Information:**")
                    st.write(f"- File Name: {selected_row.get('file_name', 'N/A')}")
                    st.write(f"- Dataset: {selected_row.get('dataset', 'N/A')}")
                    st.write(f"- Status: {format_finished(selected_row.get('finished', False), selected_row.get('error', False))}")
                    st.write(f"- Created: {selected_row.get('created_at', 'N/A')}")
                    st.write(f"- Modified: {selected_row.get('modified_at', 'N/A')}")
                
                with col2:
                    st.write("**Processing Information:**")
                    st.write(f"- Finished: {selected_row.get('finished', 'N/A')}")
                    st.write(f"- Error: {selected_row.get('error', 'N/A')}")
                    
                    if 'extracted_content' in selected_row and selected_row['extracted_content']:
                        st.write("**Extracted Content Available:** ✅")
                    else:
                        st.write("**Extracted Content Available:** ❌")
                
                # Show extracted content if available
                if 'extracted_content' in selected_row and selected_row['extracted_content']:
                    st.write("**Extracted Content:**")
                    with st.expander("View Extracted Content", expanded=False):
                        try:
                            if isinstance(selected_row['extracted_content'], str):
                                content = json.loads(selected_row['extracted_content'])
                            else:
                                content = selected_row['extracted_content']
                            st.json(content)
                        except:
                            st.text(str(selected_row['extracted_content']))
        
    except Exception as e:
        st.error(f"Error in explore data tab: {e}")
        st.info("Please check if the backend is running and accessible.")
