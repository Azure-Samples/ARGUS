import streamlit as st
import requests
import json
import base64
import tempfile
import os

from dotenv import load_dotenv
import pandas as pd


load_dotenv()

logo = 'static/logo.png'  

st.set_page_config(layout="wide")

# Sidebar navigation
st.sidebar.title('Navigation')
menu_options = ['Input', 'Config','Journal']
menu = st.sidebar.radio("Menu", ('Input', 'Config','Journal'))

# Initialize the session state variables if they are not already set
if 'backend_url' not in st.session_state:
    st.session_state['backend_url'] = os.getenv("BACKEND_ENDPOINT", None)
if 'system_prompt' not in st.session_state:
    st.session_state['system_prompt'] = os.getenv("SYSTEM_PROMPT", None)
if 'schema' not in st.session_state:
    st.session_state['schema'] = os.getenv("OUTPUT_SCHEMA", None)
if 'nl_response' not in st.session_state:
    st.session_state['nl_response'] = '{}'    
if 'ocr_response' not in st.session_state:
    st.session_state['ocr_response'] = '{}'    


# Based on the menu selection, display different pages
if menu == 'Input':
    st.header('Input')
    
    # Use columns to center content
    col1, col2 = st.columns([0.6,0.4])
    with col1:
        sub_col1, sub_col2 = st.columns([1,3])
        with sub_col1:
            st.image(logo, width=100)  # Center the logo
            
        with sub_col2:
            st.title('Claims/Requests AI Automation')  
            

        system_prompt = st.session_state.system_prompt
        
        user_message = st.text_area("Your message:", placeholder="Hello. Please find attached my documents for the case.")
       
        uploaded_files = st.file_uploader("Choose file to attach to the request (1 file per request)", type=['png', 'jpg', 'jpeg', 'pdf'],accept_multiple_files=True)  

        schema = st.session_state.schema

        if st.button('Submit'):  
        
            if uploaded_files is not None:
                for i in range(len(uploaded_files)):
                    # Read the uploaded file
                    file_content = uploaded_files[i].read()
                
                    file_dec = base64.b64encode(file_content)
                    file_str = file_dec.decode() 
                    
                    # Prepare the payload (adjust as needed)
                    payload = {
                        "file_name": uploaded_files[i].name,
                        "file_content": file_str,
                        "user_message": user_message,
                        "system_prompt": system_prompt,
                        "json_schema": schema
                    }

                     # Placeholder for loading message
                    with st.spinner('Calling backend API... Please wait.'):
                        # Make the POST request
                        url = os.getenv("BACKEND_ENDPOINT", None)
                        response = requests.post(url, json=payload)
                
                        if response.status_code == 200:
                            st.success('Successfully executed!')
                            st.session_state['ocr_response'] = response.json()["ocr_response"]
                            st.session_state['nl_response'] = response.json()["nl_response"]
                        else:
                            st.error('Failed to upload files. Status code: {}'.format(response.status_code))

            else:
                st.warning('Please upload some files first.')

    # Split the string by newline characters and join them back with "\n"  
    formatted_nl_response = "\n".join(st.session_state['nl_response'].split("\\n"))  
  
    with col2:  
        st.header("Results:")  
        # Use the formatted string in the text area  
        st.text_area("Summary:", formatted_nl_response) 
        st.text("Raw OCR Results:")  
        # Display the OCR results as JSON  
        st.json(st.session_state['ocr_response'])  
    

elif menu == 'Config':
    st.header('Configurations')
    
    backend_url = st.text_input("Backend API URL:", value=os.getenv("BACKEND_ENDPOINT", None))
    system_prompt = st.text_area("System Prompt", value=os.getenv("SYSTEM_PROMPT", None))
    schema = st.text_area("Output Schema sample", value=json.dumps(os.getenv("OUTPUT_SCHEMA", None)))

    if st.button('Save'):  
        st.session_state.backend_url = backend_url
        st.session_state.system_prompt = system_prompt
        st.session_state.schema = schema
    

elif menu == 'Journal':
    st.header('Journal')
    
    backend_url = st.text_input("CosmosDB API URL:", value=os.getenv("BACKEND_ENDPOINT", None))
    st.session_state.backend_url = backend_url 

     # Prepare the payload (adjust as needed)
    payload = {
        "history": True,
        "size": 10
    }

     # Placeholder for loading message
    with st.spinner('Calling DB API... Please wait.'):
        # Make the GET request
        url = os.getenv("BACKEND_ENDPOINT", None)  # Replace with Azure function endpoint
        response = requests.get(url, json=payload)

        if response.status_code == 200:
            st.success('Successfully executed!')
            df = pd.json_normalize(response.json())
            st.table(df)
            
        else:
            st.error('Failed to upload files. Status code: {}'.format(response.status_code))