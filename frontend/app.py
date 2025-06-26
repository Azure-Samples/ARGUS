import os
import streamlit as st
from dotenv import load_dotenv

from process_files import process_files_tab
from explore_data import explore_data_tab
from instructions import instructions_tab
from settings import settings_tab

## IMPORTANT: Instructions on how to run the Streamlit app locally can be found in the README.md file.


# Load environment variables
load_dotenv()

# Initialize the session state variables if they are not already set
def initialize_session_state():
    env_vars = {
        'system_prompt': "SYSTEM_PROMPT",
        'schema': "OUTPUT_SCHEMA",
        'blob_conn_str': "BLOB_CONN_STR",
        'blob_url' : "BLOB_ACCOUNT_URL",
        'container_name': "CONTAINER_NAME",
        'cosmos_url': "COSMOS_URL",
        'cosmos_db_name': "COSMOS_DB_NAME",
        'cosmos_documents_container_name': "COSMOS_DOCUMENTS_CONTAINER_NAME",
        'cosmos_config_container_name': "COSMOS_CONFIG_CONTAINER_NAME",
        'backend_url': "BACKEND_URL"
    }
    for var, env in env_vars.items():
        if var not in st.session_state:
            st.session_state[var] = os.getenv(env)

# Initialize the session state variables
initialize_session_state()

# Set the page layout to wide
st.set_page_config(
    page_title="ARGUS - Document Intelligence Platform",
    page_icon="🧠",
    layout="wide"
)

# Header
st.header("🧠 ARGUS: Automated Retrieval and GPT Understanding System")

# Tabs navigation
tabs = st.tabs(["🧠 Process Files", "🔎 Explore Data", "⚙️ Settings", "📋 Instructions"])

# Render the tabs
with tabs[0]:
    process_files_tab()
with tabs[1]:
    explore_data_tab()
with tabs[2]:
    settings_tab()
with tabs[3]:
    instructions_tab()
