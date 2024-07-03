import os
import streamlit as st
from dotenv import load_dotenv

from process_files import process_files_tab
from explore_data import explore_data_tab
from instructions import instructions_tab

# Load environment variables
load_dotenv()

# Initialize the session state variables if they are not already set
def initialize_session_state():
    env_vars = {
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

# Initialize the session state variables
initialize_session_state()

# Set the page layout to wide
st.set_page_config(layout="wide")

# Tabs navigation
title = st.header("ARGUS: Automated Retrieval and GPT Understanding System")
tabs = st.tabs(["🧠 Process Files", "🔎 Explore Data", "🖥️ Instructions"])

# Render the tabs
with tabs[0]:
    process_files_tab()
with tabs[1]:
    explore_data_tab()
with tabs[2]:
    instructions_tab()
