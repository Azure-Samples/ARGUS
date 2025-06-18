import streamlit as st
import requests
import json
from datetime import datetime

def concurrency_settings_tab():
    """Tab for managing Logic App concurrency settings"""
    
    st.markdown("## 🚀 Concurrency Settings")
    st.markdown("Configure how many files can be processed in parallel by the Logic App.")
    
    # Get backend URL from session state or environment
    backend_url = st.session_state.get('backend_url', 'http://localhost:8000')
    
    # Create two columns
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("### Current Settings")
        
        # Button to refresh current settings
        if st.button("🔄 Refresh Settings", key="refresh_concurrency"):
            try:
                response = requests.get(f"{backend_url}/api/concurrency", timeout=10)
                if response.status_code == 200:
                    settings = response.json()
                    st.session_state['concurrency_settings'] = settings
                    st.success("Settings refreshed successfully!")
                else:
                    st.error(f"Failed to fetch settings: {response.status_code} - {response.text}")
            except Exception as e:
                st.error(f"Error fetching settings: {str(e)}")
        
        # Display current settings if available
        if 'concurrency_settings' in st.session_state:
            settings = st.session_state['concurrency_settings']
            
            if settings.get('enabled', False):
                st.success("✅ Logic App Manager is enabled")
                
                # Create metrics display
                col_a, col_b = st.columns(2)
                with col_a:
                    st.metric("Max Concurrent Runs", settings.get('current_max_runs', 'N/A'))
                with col_b:
                    st.metric("Workflow State", settings.get('workflow_state', 'N/A'))
                
                # Additional info
                st.info(f"**Logic App:** {settings.get('logic_app_name', 'N/A')}")
                st.info(f"**Resource Group:** {settings.get('resource_group', 'N/A')}")
                
                if settings.get('last_modified'):
                    try:
                        last_modified = datetime.fromisoformat(settings['last_modified'].replace('Z', '+00:00'))
                        st.info(f"**Last Modified:** {last_modified.strftime('%Y-%m-%d %H:%M:%S UTC')}")
                    except:
                        st.info(f"**Last Modified:** {settings.get('last_modified', 'N/A')}")
                        
            else:
                st.error("❌ Logic App Manager is not enabled")
                if 'error' in settings:
                    st.error(f"Error: {settings['error']}")
        else:
            st.info("Click 'Refresh Settings' to load current configuration")
    
    with col2:
        st.markdown("### Update Settings")
        
        # Form to update concurrency settings
        with st.form("update_concurrency_form"):
            st.markdown("**Set Maximum Concurrent Runs**")
            
            # Get current value for default
            current_max = 1
            if 'concurrency_settings' in st.session_state:
                current_max = st.session_state['concurrency_settings'].get('current_max_runs', 1)
            
            new_max_runs = st.number_input(
                "Max Concurrent Runs",
                min_value=1,
                max_value=100,
                value=current_max,
                step=1,
                help="Number of files that can be processed simultaneously (1-100)"
            )
            
            st.markdown("---")
            st.markdown("**Impact of Changes:**")
            st.markdown("""
            - **Lower values (1-5)**: More controlled processing, lower resource usage
            - **Higher values (10-50)**: Faster bulk processing, higher resource usage
            - **Very high values (50-100)**: Maximum throughput, requires sufficient Azure resources
            """)
            
            submit_button = st.form_submit_button("🔧 Update Concurrency", type="primary")
            
            if submit_button:
                try:
                    # Make API call to update settings
                    payload = {"max_runs": new_max_runs}
                    response = requests.put(
                        f"{backend_url}/api/concurrency",
                        json=payload,
                        timeout=30,
                        headers={"Content-Type": "application/json"}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        st.success(f"✅ Successfully updated max concurrent runs to {new_max_runs}")
                        st.success(f"Updated at: {result.get('updated_at', 'N/A')}")
                        
                        # Refresh the settings display
                        try:
                            refresh_response = requests.get(f"{backend_url}/api/concurrency", timeout=10)
                            if refresh_response.status_code == 200:
                                st.session_state['concurrency_settings'] = refresh_response.json()
                        except:
                            pass  # Ignore refresh errors
                        
                        # Rerun to update the display
                        st.rerun()
                    else:
                        error_detail = "Unknown error"
                        try:
                            error_data = response.json()
                            error_detail = error_data.get('detail', response.text)
                        except:
                            error_detail = response.text
                        
                        st.error(f"❌ Failed to update settings: {error_detail}")
                        
                except Exception as e:
                    st.error(f"❌ Error updating settings: {str(e)}")
    
    # Add explanatory section
    st.markdown("---")
    st.markdown("### 📖 About Concurrency Control")
    
    with st.expander("How it works", expanded=False):
        st.markdown("""
        **Logic App Concurrency Control** manages how many file processing workflows can run simultaneously:
        
        **What happens when you upload multiple files:**
        1. Each file triggers a separate Logic App workflow run
        2. The concurrency setting limits how many can run at the same time
        3. Excess files wait in a queue until a slot becomes available
        4. This prevents resource overload and ensures stable processing
        
        **Choosing the right setting:**
        - **Conservative (1-5 runs)**: Best for large files or limited Azure resources
        - **Balanced (5-15 runs)**: Good for most use cases with mixed file sizes
        - **Aggressive (15+ runs)**: Best for small files and ample Azure resources
        
        **Technical details:**
        - Changes take effect immediately for new file uploads
        - Currently running workflows are not affected
        - The setting is stored at the Azure Logic App level
        - Requires 'Logic App Contributor' permissions
        """)
    
    # Add monitoring section
    with st.expander("Monitoring & Troubleshooting", expanded=False):
        st.markdown("""
        **If processing seems slow:**
        1. Check the current max concurrent runs setting
        2. Consider increasing it if you have sufficient Azure resources
        3. Monitor your Azure costs as higher concurrency = higher resource usage
        
        **If you see errors:**
        - Ensure the backend has proper permissions to manage the Logic App
        - Check that all required environment variables are set
        - Verify the Logic App exists and is in the 'Enabled' state
        
        **Resource requirements:**
        - Higher concurrency requires more Azure AI Document Intelligence capacity
        - Monitor your Azure OpenAI token usage and rate limits
        - Consider Azure Cosmos DB throughput (RU/s) for high concurrency
        """)
