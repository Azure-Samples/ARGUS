import streamlit as st
import requests
import json
from typing import List, Dict, Any, Optional


class DocumentChatComponent:
    """Chat component for interacting with document content"""
    
    def __init__(self, backend_url: str):
        self.backend_url = backend_url
        
    def initialize_chat_state(self, document_id: str):
        """Initialize chat state for a document"""
        chat_key = f"chat_history_{document_id}"
        if chat_key not in st.session_state:
            st.session_state[chat_key] = []
        return chat_key
    
    def send_message(self, document_id: str, message: str, document_context: str, chat_history: List[Dict]) -> Optional[Dict]:
        """Send a message to the chat API"""
        try:
            response = requests.post(
                f"{self.backend_url}/api/chat",
                json={
                    "document_id": document_id,
                    "message": message,
                    "chat_history": chat_history
                },
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                st.error(f"Chat API error: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with chat API: {e}")
            return None
    
    def render_chat_interface(self, document_id: str, document_name: str, document_context: str = ""):
        """Render the chat interface"""
        st.markdown(f"### Chat with: {document_name}")
        st.markdown("Ask questions about this document and get insights based on the extracted data.")
        
        # Initialize chat state
        chat_key = self.initialize_chat_state(document_id)
        
        # Display chat history
        chat_container = st.container()
        with chat_container:
            if st.session_state[chat_key]:
                for i, chat_item in enumerate(st.session_state[chat_key]):
                    role = chat_item.get('role', 'user')
                    content = chat_item.get('content', '')
                    with st.chat_message(role):
                        st.write(content)
            else:
                st.info("Start a conversation! Ask questions about the document content, specific details, or request insights.")

        # Use st.chat_input for chat input
        user_message = st.chat_input("Ask a question about this document...")

        if user_message and user_message.strip():
            # Add user message to chat history
            st.session_state[chat_key].append({
                "role": "user",
                "content": user_message.strip()
            })
            # Show loading spinner
            with st.spinner("Thinking..."):
                response = self.send_message(
                    document_id,
                    user_message.strip(),
                    document_context,
                    st.session_state[chat_key]
                )
            if response:
                assistant_response = response.get('response', 'Sorry, I could not process your request.')
                st.session_state[chat_key].append({
                    "role": "assistant",
                    "content": assistant_response
                })
                if 'usage' in response:
                    usage = response['usage']
                    with st.expander("Token Usage", expanded=False):
                        st.write(f"**Prompt Tokens:** {usage.get('prompt_tokens', 0)}")
                        st.write(f"**Completion Tokens:** {usage.get('completion_tokens', 0)}")
                        st.write(f"**Total Tokens:** {usage.get('total_tokens', 0)}")
            st.rerun()

        # Clear chat history button
        if st.session_state[chat_key]:
            st.markdown("---")
            if st.button("Clear Chat History", key=f"clear_chat_{document_id}"):
                st.session_state[chat_key] = []
                st.rerun()


def render_document_chat_tab(document_id: str, document_name: str, backend_url: str, document_context: str = ""):
    """Standalone function to render chat tab content"""
    chat_component = DocumentChatComponent(backend_url)
    chat_component.render_chat_interface(document_id, document_name, document_context)
