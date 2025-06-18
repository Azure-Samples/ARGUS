"""
Logic App Concurrency Management Interface

This module provides a Streamlit interface for managing Logic App concurrency settings.
It allows users to view current concurrency settings and update the maximum number of 
concurrent runs for the Logic App workflow.
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_backend_url():
    """Get the backend API URL from environment or use default"""
    return os.getenv('BACKEND_API_URL', 'http://localhost:8000')

def render_concurrency_management():
    """Render the Logic App concurrency management interface"""
    st.header("🔧 Logic App Concurrency Management")
    st.markdown("Manage the concurrency settings for your Logic App workflow to control how many instances can run simultaneously.")
    
    backend_url = get_backend_url()
    
    # Create two columns for better layout
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.subheader("Current Settings")
        
        # Add refresh button
        if st.button("🔄 Refresh Settings", key="refresh_concurrency"):
            st.rerun()
        
        # Fetch current concurrency settings
        try:
            with st.spinner("Loading current concurrency settings..."):
                response = requests.get(f"{backend_url}/api/concurrency", timeout=10)
                
                if response.status_code == 200:
                    settings = response.json()
                    
                    if settings.get("enabled", False):
                        # Display current settings in a nice format
                        st.success("✅ Logic App Manager is active")
                        
                        # Create metrics display
                        metric_col1, metric_col2, metric_col3 = st.columns(3)
                        
                        with metric_col1:
                            st.metric(
                                label="Current Max Runs",
                                value=settings.get("current_max_runs", "Unknown")
                            )
                        
                        with metric_col2:
                            st.metric(
                                label="Workflow State",
                                value=settings.get("workflow_state", "Unknown")
                            )
                        
                        with metric_col3:
                            if settings.get("last_modified"):
                                try:
                                    last_modified = datetime.fromisoformat(
                                        settings["last_modified"].replace("Z", "+00:00")
                                    )
                                    st.metric(
                                        label="Last Modified",
                                        value=last_modified.strftime("%Y-%m-%d %H:%M")
                                    )
                                except:
                                    st.metric(
                                        label="Last Modified",
                                        value="Unknown"
                                    )
                        
                        # Display Logic App details
                        with st.expander("Logic App Details"):
                            st.write(f"**Logic App Name:** {settings.get('logic_app_name', 'Unknown')}")
                            st.write(f"**Resource Group:** {settings.get('resource_group', 'Unknown')}")
                        
                        # Store current settings in session state for updates
                        st.session_state.current_max_runs = settings.get("current_max_runs", 1)
                        st.session_state.logic_app_active = True
                        
                    else:
                        st.error(f"❌ Logic App Manager is not configured: {settings.get('error', 'Unknown error')}")
                        st.session_state.logic_app_active = False
                        
                elif response.status_code == 503:
                    st.error("❌ Logic App Manager is not available. Check configuration.")
                    st.session_state.logic_app_active = False
                else:
                    st.error(f"❌ Failed to fetch settings: HTTP {response.status_code}")
                    st.session_state.logic_app_active = False
                    
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Connection error: {str(e)}")
            st.session_state.logic_app_active = False
        except Exception as e:
            st.error(f"❌ Error loading settings: {str(e)}")
            st.session_state.logic_app_active = False
    
    with col2:
        st.subheader("Update Settings")
        
        # Only show update form if Logic App is active
        if st.session_state.get("logic_app_active", False):
            current_max_runs = st.session_state.get("current_max_runs", 1)
            
            # Input for new max runs
            new_max_runs = st.number_input(
                "New Max Concurrent Runs",
                min_value=1,
                max_value=100,
                value=current_max_runs,
                step=1,
                help="Set the maximum number of Logic App instances that can run concurrently (1-100)"
            )
            
            # Show the impact of the change
            if new_max_runs != current_max_runs:
                if new_max_runs > current_max_runs:
                    st.info(f"ℹ️ This will increase concurrency from {current_max_runs} to {new_max_runs}")
                else:
                    st.warning(f"⚠️ This will decrease concurrency from {current_max_runs} to {new_max_runs}")
            
            # Update button
            if st.button("💾 Update Concurrency", key="update_concurrency"):
                if new_max_runs == current_max_runs:
                    st.info("ℹ️ No changes to apply.")
                else:
                    # Show confirmation for significant changes
                    proceed = True
                    if abs(new_max_runs - current_max_runs) > 5:
                        st.warning("⚠️ This is a significant change in concurrency settings.")
                        proceed = st.checkbox("I understand the impact of this change", key="confirm_update")
                    
                    if proceed:
                        try:
                            with st.spinner(f"Updating max concurrent runs to {new_max_runs}..."):
                                update_payload = {"max_runs": new_max_runs}
                                response = requests.put(
                                    f"{backend_url}/api/concurrency",
                                    json=update_payload,
                                    timeout=30
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    st.success(f"✅ Successfully updated max concurrent runs to {new_max_runs}!")
                                    st.session_state.current_max_runs = new_max_runs
                                    
                                    # Show update details
                                    with st.expander("Update Details"):
                                        st.json(result)
                                    
                                    # Auto-refresh after successful update
                                    st.rerun()
                                else:
                                    error_detail = response.json().get("detail", "Unknown error")
                                    st.error(f"❌ Failed to update settings: {error_detail}")
                                    
                        except requests.exceptions.RequestException as e:
                            st.error(f"❌ Connection error: {str(e)}")
                        except Exception as e:
                            st.error(f"❌ Error updating settings: {str(e)}")
        else:
            st.info("ℹ️ Configure Logic App Manager to enable updates.")
    
    # Information section
    st.markdown("---")
    st.subheader("ℹ️ About Concurrency Management")
    
    with st.expander("Understanding Concurrency Settings"):
        st.markdown("""
        **What is Logic App Concurrency?**
        
        Logic App concurrency controls how many instances of your workflow can run simultaneously:
        
        - **Low Concurrency (1-5)**: Better for resource-intensive operations, prevents overwhelming downstream services
        - **Medium Concurrency (6-20)**: Balanced approach for most scenarios
        - **High Concurrency (21-100)**: Suitable for lightweight operations with high throughput requirements
        
        **Considerations:**
        - Higher concurrency can improve throughput but may increase resource usage
        - Consider the capacity of downstream services (APIs, databases)
        - Monitor performance and adjust based on actual usage patterns
        
        **Environment Variables Required:**
        - `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID
        - `AZURE_RESOURCE_GROUP_NAME`: Resource group containing the Logic App
        - `LOGIC_APP_NAME`: Name of the Logic App workflow
        """)
    
    # Performance monitoring section
    with st.expander("Performance Monitoring Tips"):
        st.markdown("""
        **Monitoring Your Logic App Performance:**
        
        1. **Azure Portal**: Check Logic App metrics and run history
        2. **Application Insights**: Monitor performance and errors
        3. **Resource Usage**: Watch CPU, memory, and execution time
        4. **Downstream Impact**: Monitor connected services for performance issues
        
        **Best Practices:**
        - Start with lower concurrency and gradually increase
        - Test thoroughly in non-production environments
        - Set up alerts for high error rates or performance degradation
        - Review and adjust settings based on actual usage patterns
        """)

# Main render function for the tab
def render():
    """Main render function called by the Streamlit app"""
    render_concurrency_management()

if __name__ == "__main__":
    # For testing the module standalone
    render()
