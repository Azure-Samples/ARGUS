import streamlit as st
import requests
import json
from datetime import datetime

def settings_tab():
    """Combined settings tab for OpenAI configuration and concurrency settings"""
    
    st.markdown("## ⚙️ Settings")
    st.markdown("Configure OpenAI settings and processing concurrency for ARGUS.")
    
    # Create two columns for the two settings sections
    col1, col2 = st.columns(2)
    
    with col1:
        openai_settings_section()
    
    with col2:
        concurrency_settings_section()

def openai_settings_section():
    """OpenAI configuration settings section"""
    st.markdown("### 🤖 OpenAI Configuration")
    
    # Get backend URL from session state
    backend_url = st.session_state.get('backend_url', 'http://localhost:8000')
    
    # Load current OpenAI settings
    current_openai_settings = load_current_openai_settings(backend_url)
    
    # Check if configuration is environment-variable based
    is_env_based = current_openai_settings.get('note', '').startswith('Configuration is read from environment variables')
    
    if is_env_based:
        # Show current configuration and provide editing capability
        st.info("ℹ️ **Configuration is managed via environment variables** for enhanced security and consistency.")
        
        # Create tabs for runtime updates vs persistent instructions
        tab1, tab2 = st.tabs(["🔄 Runtime Updates", "📋 Persistent Updates"])
        
        with tab1:
            st.markdown("**Update environment variables at runtime** (temporary until container restart):")
            
            with st.form("env_var_settings_form"):
                # Get current values, handling the hidden key
                current_endpoint = current_openai_settings.get('openai_endpoint', '')
                current_key_display = current_openai_settings.get('openai_key', '')
                current_deployment = current_openai_settings.get('deployment_name', '')
                
                # OpenAI Endpoint
                openai_endpoint = st.text_input(
                    "Azure OpenAI Endpoint",
                    value=current_endpoint,
                    help="Your Azure OpenAI service endpoint URL",
                    placeholder="https://your-resource.openai.azure.com/"
                )
                
                # OpenAI API Key
                openai_key = st.text_input(
                    "Azure OpenAI API Key",
                    value="" if current_key_display == "***hidden***" else current_key_display,
                    type="password",
                    help="Your Azure OpenAI API key (leave blank to keep current key)",
                    placeholder="Enter new key or leave blank to keep current"
                )
                
                # Model Deployment Name
                deployment_name = st.text_input(
                    "Model Deployment Name",
                    value=current_deployment,
                    help="The name of your deployed model",
                    placeholder="gpt-4o"
                )
                
                # Submit button
                submit_env_vars = st.form_submit_button("🔄 Update Runtime Environment Variables", type="primary")
                
                if submit_env_vars:
                    # Validate inputs
                    if not openai_endpoint or not deployment_name:
                        st.error("❌ Endpoint and Deployment Name are required!")
                    elif not openai_key and current_key_display in ["", "***hidden***"]:
                        st.error("❌ API Key is required (current key is hidden)!")
                    else:
                        # Prepare update data
                        update_data = {
                            "openai_endpoint": openai_endpoint,
                            "openai_deployment_name": deployment_name
                        }
                        # Only include key if provided
                        if openai_key:
                            update_data["openai_key"] = openai_key
                        
                        # Update settings
                        success = update_openai_env_vars(backend_url, update_data)
                        if success:
                            st.success("✅ Runtime environment variables updated successfully!")
                            st.info("🔄 Changes are active immediately for new requests.")
                            st.rerun()
                        else:
                            st.error("❌ Failed to update environment variables. Please try again.")
            
            st.warning("⚠️ **Note**: Runtime updates are temporary and will be lost when the container restarts. For persistent changes, use the 'Persistent Updates' tab.")
        
        with tab2:
            st.markdown("**For changes that persist across container restarts**, update the environment variables in your deployment:")
            
            st.markdown("""
            **Option 1: Update via Azure Portal (Recommended)**
            1. Go to Azure Portal → Container Apps → Your Backend App
            2. Navigate to **Settings** → **Environment variables**
            3. Update these variables:
               - `AZURE_OPENAI_ENDPOINT`
               - `AZURE_OPENAI_API_KEY` 
               - `AZURE_OPENAI_DEPLOYMENT_NAME`
            4. **Restart** the container app for changes to take effect
            
            **Option 2: Update via Azure CLI**
            ```bash
            az containerapp update \\
              --name <your-backend-app-name> \\
              --resource-group <your-resource-group> \\
              --set-env-vars \\
                AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/" \\
                AZURE_OPENAI_API_KEY="your-api-key" \\
                AZURE_OPENAI_DEPLOYMENT_NAME="your-deployment-name"
            ```
            
            **Option 3: Update via Infrastructure (azd)**
            If you're using Azure Developer CLI (azd):
            1. Update the environment variables in your `infra/main.parameters.json` file
            2. Run `azd up` to redeploy with new settings
            """)
        
        # Current configuration display
        with st.expander("👀 View Current Configuration", expanded=False):
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("**Endpoint:**")
                st.markdown("**API Key:**")
                st.markdown("**Deployment:**")
            
            with col2:
                endpoint = current_openai_settings.get('openai_endpoint', 'Not configured')
                key_status = '✅ Configured' if current_openai_settings.get('openai_key', '') != '' else '❌ Missing'
                deployment = current_openai_settings.get('deployment_name', 'Not configured')
                
                st.code(endpoint)
                st.markdown(f"`{key_status}`")
                st.code(deployment)
        
        # Refresh button
        if st.button("🔄 Refresh Configuration", help="Reload current configuration from backend"):
            st.rerun()
    
    else:
        # Legacy form-based configuration (fallback)
        with st.form("openai_settings_form"):
            st.markdown("Configure your Azure OpenAI connection settings:")
            
            # OpenAI Endpoint
            openai_endpoint = st.text_input(
                "Azure OpenAI Endpoint",
                value=current_openai_settings.get('openai_endpoint', ''),
                help="Your Azure OpenAI service endpoint URL (e.g., https://your-resource.openai.azure.com/)",
                placeholder="https://your-resource.openai.azure.com/"
            )
            
            # OpenAI API Key
            openai_key = st.text_input(
                "Azure OpenAI API Key",
                value=current_openai_settings.get('openai_key', ''),
                type="password",
                help="Your Azure OpenAI API key for authentication"
            )
            
            # Model Deployment Name
            deployment_name = st.text_input(
                "Model Deployment Name",
                value=current_openai_settings.get('deployment_name', ''),
                help="The name of your deployed model (e.g., gpt-4o, gpt-35-turbo)",
                placeholder="gpt-4o"
            )
            
            # Submit button
            submit_openai = st.form_submit_button("Update OpenAI Settings", type="primary")
            
            if submit_openai:
                # Validate inputs
                if not openai_endpoint or not openai_key or not deployment_name:
                    st.error("❌ All OpenAI fields are required!")
                else:
                    # Update OpenAI settings
                    success = update_openai_settings(
                        backend_url, 
                        openai_endpoint, 
                        openai_key, 
                        deployment_name
                    )
                    if success:
                        st.success("✅ OpenAI settings updated successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update OpenAI settings. Please try again.")
    
    # Help section for OpenAI settings
    with st.expander("💡 OpenAI Configuration Help"):
        st.markdown("""
        **Azure OpenAI Endpoint**: The base URL for your Azure OpenAI resource. 
        - Format: `https://your-resource-name.openai.azure.com/`
        - Find this in Azure Portal → Your OpenAI Resource → Keys and Endpoint
        
        **API Key**: Your authentication key for the Azure OpenAI service.
        - Found in Azure Portal → Your OpenAI Resource → Keys and Endpoint
        - Use either Key 1 or Key 2
        
        **Model Deployment Name**: The name you gave to your model deployment.
        - This is the name you specified when deploying a model in Azure OpenAI Studio
        - Common examples: `gpt-4o`, `gpt-35-turbo`, `gpt-4-vision-preview`
        """)

def concurrency_settings_section():
    """Concurrency settings section"""
    st.markdown("### 🚀 Concurrency Settings")
    
    # Get backend URL from session state
    backend_url = st.session_state.get('backend_url', 'http://localhost:8000')
    
    # Auto-load current settings
    current_settings = load_current_concurrency_settings(backend_url)
    
    if current_settings and current_settings.get('enabled', False):
        # Get current value to prepopulate the input
        current_max_runs = current_settings.get('current_max_runs', 1)
        
        # Status indicator
        st.success("✅ Logic App Manager is enabled")
        
        # Concurrency update form
        with st.form("update_concurrency_form"):
            new_max_runs = st.number_input(
                f"Maximum Concurrent Runs (Current: {current_max_runs})",
                min_value=1,
                max_value=100,
                value=current_max_runs,
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
            
            submit_concurrency = st.form_submit_button("Update Concurrency", type="primary")
            
            if submit_concurrency:
                if new_max_runs == current_max_runs:
                    st.info("ℹ️ No changes needed - value is already set to " + str(new_max_runs))
                else:
                    success = update_concurrency_setting(backend_url, new_max_runs)
                    if success:
                        st.success(f"✅ Successfully updated to {new_max_runs} concurrent runs!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to update concurrency settings. Please try again.")
    
    else:
        # Show error state
        st.error("❌ Logic App Manager is not available")
        if current_settings and 'error' in current_settings:
            st.error(f"Error: {current_settings['error']}")
        st.info("Please check your configuration and ensure the backend service is running.")
    
    # Help section for concurrency
    with st.expander("💡 Concurrency Control Help"):
        st.markdown("""
        **Concurrency control** limits how many files can be processed simultaneously.
        
        **Choosing the right setting:**
        - **Conservative (1-5 runs)**: Best for large files or limited Azure resources
        - **Balanced (6-15 runs)**: Good for most use cases with mixed file sizes
        - **Aggressive (16+ runs)**: Best for small files and ample Azure resources
        
        **Resource considerations:**
        - Higher concurrency requires more Azure AI Document Intelligence capacity
        - Monitor Azure OpenAI token usage and rate limits
        - Consider Azure Cosmos DB throughput (RU/s) for high concurrency
        """)

def load_current_openai_settings(backend_url):
    """Load current OpenAI settings from the backend"""
    try:
        with st.spinner("Loading OpenAI settings..."):
            response = requests.get(f"{backend_url}/api/openai-settings", timeout=10)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                # No settings found, return empty defaults
                return {}
            else:
                st.error(f"Failed to load OpenAI settings: HTTP {response.status_code}")
                return {}
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error loading OpenAI settings: {str(e)}")
        return {}
    except Exception as e:
        st.error(f"Error loading OpenAI settings: {str(e)}")
        return {}

def update_openai_settings(backend_url, endpoint, key, deployment_name):
    """Update OpenAI settings via the backend API"""
    try:
        with st.spinner("Updating OpenAI settings..."):
            payload = {
                "openai_endpoint": endpoint,
                "openai_key": key,
                "deployment_name": deployment_name
            }
            response = requests.put(
                f"{backend_url}/api/openai-settings",
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
        st.error(f"Error updating OpenAI settings: {str(e)}")
        return False

def load_current_concurrency_settings(backend_url):
    """Load current concurrency settings from the backend"""
    try:
        with st.spinner("Loading concurrency settings..."):
            response = requests.get(f"{backend_url}/api/concurrency", timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Failed to load concurrency settings: HTTP {response.status_code}")
                return None
    except requests.exceptions.RequestException as e:
        st.error(f"Connection error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error loading concurrency settings: {str(e)}")
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
        st.error(f"Error updating concurrency settings: {str(e)}")
        return False

def update_openai_env_vars(backend_url, settings_data):
    """Update OpenAI environment variables via the backend API"""
    try:
        with st.spinner("Updating environment variables..."):
            response = requests.put(
                f"{backend_url}/api/openai-settings",
                json=settings_data,
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
        st.error(f"Error updating environment variables: {str(e)}")
        return False
