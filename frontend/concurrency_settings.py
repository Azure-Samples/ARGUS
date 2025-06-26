import streamlit as st
import requests
import json
from datetime import datetime

def concurrency_settings_tab():
    """Simplified tab for managing Logic App concurrency settings"""
    
    st.markdown("## 🚀 Concurrency Settings")
    st.markdown("Configure how many files can be processed in parallel by the Logic App.")
    
    # Get backend URL from session state or environment
    backend_url = st.session_state.get('backend_url', 'http://localhost:8000')
    
    # Auto-load current settings
    current_settings = load_current_settings(backend_url)
    
    if current_settings and current_settings.get('enabled', False):
        # Get current value to prepopulate the input
        current_max_runs = current_settings.get('current_max_runs', 5)
        
        # Status indicator
        st.success("✅ Logic App Manager is enabled")
        
        # Simplified update form - centered layout
        st.markdown("### Set Maximum Concurrent Runs")
        
        with st.form("update_concurrency_form"):
            new_max_runs = st.number_input(
                f"Current setting: {current_max_runs} concurrent runs",
                min_value=1,
                max_value=100,
                value=current_max_runs,  # Prepopulate with current value
                step=1,
                help="Number of files that can be processed simultaneously"
            )
            
            # Show impact guidance
            if new_max_runs <= 5:
                st.info("💡 Lower values: More controlled processing, lower resource usage")
            elif new_max_runs <= 20:
                st.info("💡 Medium values: Balanced approach for most scenarios")
            else:
                st.warning("💡 Higher values: Faster processing, requires sufficient Azure resources")
            
            submit_button = st.form_submit_button("Update Concurrency", type="primary")
            
            if submit_button:
                if new_max_runs == current_max_runs:
                    st.info("ℹ️ No changes needed - value is already set to " + str(new_max_runs))
                else:
                    success = update_concurrency_setting(backend_url, new_max_runs)
                    if success:
                        st.success(f"✅ Successfully updated to {new_max_runs} concurrent runs!")
                        st.rerun()  # Refresh to show new values
                    else:
                        st.error("❌ Failed to update settings. Please try again.")
    
    else:
        # Show error state
        st.error("❌ Logic App Manager is not available")
        if current_settings and 'error' in current_settings:
            st.error(f"Error: {current_settings['error']}")
        st.info("Please check your configuration and ensure the backend service is running.")
        
        # Add diagnostics section for troubleshooting
        st.markdown("---")
        st.markdown("### 🔍 Diagnostics")
        
        if st.button("Run Diagnostics", type="secondary"):
            with st.spinner("Running diagnostics..."):
                try:
                    diag_response = requests.get(f"{backend_url}/api/concurrency/diagnostics", timeout=10)
                    if diag_response.status_code == 200:
                        diagnostics = diag_response.json()
                        
                        st.markdown("**Diagnostic Results:**")
                        
                        # Environment Variables Check
                        env_vars = diagnostics.get("environment_variables", {})
                        st.markdown("**Environment Variables:**")
                        for var, is_set in env_vars.items():
                            status_icon = "✅" if is_set else "❌"
                            value = diagnostics.get("environment_values", {}).get(var, "NOT_SET")
                            st.markdown(f"{status_icon} `{var}`: {value}")
                        
                        # Logic App Manager Status
                        st.markdown("**Logic App Manager Status:**")
                        manager_init = diagnostics.get("logic_app_manager_initialized", False)
                        st.markdown(f"{'✅' if manager_init else '❌'} Logic App Manager Initialized: {manager_init}")
                        
                        if manager_init:
                            manager_enabled = diagnostics.get("logic_app_manager_enabled", False)
                            st.markdown(f"{'✅' if manager_enabled else '❌'} Logic App Manager Enabled: {manager_enabled}")
                            
                            creds_available = diagnostics.get("azure_credentials_available", False)
                            st.markdown(f"{'✅' if creds_available else '❌'} Azure Credentials Available: {creds_available}")
                        
                        # Show full diagnostic data
                        with st.expander("Full Diagnostic Data"):
                            st.json(diagnostics)
                            
                    else:
                        st.error(f"Failed to get diagnostics: HTTP {diag_response.status_code}")
                        
                except Exception as e:
                    st.error(f"Error running diagnostics: {str(e)}")
    
    # Enhanced help section
    st.markdown("---")
    st.markdown("### 📖 About Concurrency Control")
    
    with st.expander("💡 How Concurrency Control Works", expanded=True):
        st.markdown("""
        **Concurrency control** limits how many files can be processed simultaneously. This ensures stable processing and prevents resource overload.

        **What happens when you upload multiple files:**
        1. Each file triggers a separate Logic App workflow run
        2. The concurrency setting limits how many can run at the same time
        3. Excess files wait in a queue until a slot becomes available
        4. This prevents resource overload and ensures stable processing
        
        **Choosing the right setting:**
        - **Conservative (1-5 runs)**: Best for large files or limited Azure resources
        - **Balanced (6-15 runs)**: Good for most use cases with mixed file sizes
        - **Aggressive (16+ runs)**: Best for small files and ample Azure resources
        """)
    
    with st.expander("⚙️ Technical Details"):
        st.markdown("""
        **How the system enforces concurrency:**
        - **Logic App Level**: Controls workflow trigger concurrency
        - **Backend Level**: Uses semaphore to limit parallel processing
        - **End-to-End Control**: Both layers respect the same concurrency limit
        
        **Impact of changes:**
        - Changes take effect immediately for new file uploads
        - Currently running workflows are not affected
        - Higher concurrency = higher resource usage and costs
        - Lower concurrency = more controlled processing, lower costs
        """)
    
    with st.expander("🔧 Monitoring & Troubleshooting"):
        st.markdown("""
        **If processing seems slow:**
        1. Check your current concurrency setting above
        2. Consider increasing it if you have sufficient Azure resources
        3. Monitor your Azure costs as higher concurrency = higher resource usage
        
        **If you see errors:**
        - Ensure the backend has proper permissions to manage the Logic App
        - Check that all required environment variables are set
        - Verify the Logic App exists and is in the 'Enabled' state
        
        **Resource considerations:**
        - Higher concurrency requires more Azure AI Document Intelligence capacity
        - Monitor your Azure OpenAI token usage and rate limits
        - Consider Azure Cosmos DB throughput (RU/s) for high concurrency
        """)


def load_current_settings(backend_url):
    """Load current concurrency settings from the backend"""
    try:
        with st.spinner("Loading current settings..."):
            response = requests.get(f"{backend_url}/api/concurrency", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                # Enhanced error reporting for 503 errors
                if response.status_code == 503:
                    try:
                        error_detail = response.json().get('detail', response.text)
                        st.error(f"Failed to load concurrency settings: HTTP 503")
                        st.error(f"Details: {error_detail}")
                        
                        # Show diagnostic information
                        with st.expander("🔍 Diagnostic Information", expanded=True):
                            st.markdown("**Possible causes:**")
                            st.markdown("1. **Missing Environment Variables**: Logic App Manager requires these environment variables:")
                            st.code("""
AZURE_SUBSCRIPTION_ID
AZURE_RESOURCE_GROUP_NAME  
LOGIC_APP_NAME
""")
                            st.markdown("2. **Logic App Not Deployed**: The Logic App workflow may not exist in Azure")
                            st.markdown("3. **Authentication Issues**: The container app may not have permissions to access the Logic App")
                            
                            st.markdown("**To diagnose further:**")
                            st.markdown("- Check Azure Container App environment variables in the Azure Portal")
                            st.markdown("- Verify the Logic App exists in your resource group")
                            st.markdown("- Check container app logs for authentication errors")
                            
                    except:
                        st.error(f"Failed to load settings: HTTP {response.status_code}")
                        st.error(f"Response: {response.text}")
                else:
                    st.error(f"Failed to load settings: HTTP {response.status_code}")
                return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error loading settings: {str(e)}")
        return None


def update_concurrency_setting(backend_url, new_max_runs):
    """Update the concurrency setting"""
    try:
        with st.spinner(f"Updating to {new_max_runs} concurrent runs..."):
            payload = {"max_runs": new_max_runs}
            response = requests.put(
                f"{backend_url}/api/concurrency",
                json=payload,
                timeout=30,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                return True
            else:
                try:
                    error_data = response.json()
                    error_detail = error_data.get('detail', response.text)
                except:
                    error_detail = response.text
                st.error(f"Update failed: {error_detail}")
                return False
                
    except Exception as e:
        st.error(f"Error updating settings: {str(e)}")
        return False
