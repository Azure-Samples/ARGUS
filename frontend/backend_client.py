import os
import requests
import streamlit as st
from typing import Optional, List, Dict, Any


class BackendClient:
    """Client for communicating with the ARGUS backend API"""
    
    def __init__(self, backend_url: Optional[str] = None):
        self.backend_url = backend_url or os.getenv('BACKEND_URL', 'http://localhost:8000')
        self.session = requests.Session()
        
    def _make_request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make a request to the backend API"""
        url = f"{self.backend_url}/api{endpoint}"
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            st.error(f"Error communicating with backend: {e}")
            raise
    
    def upload_file(self, file_content: bytes, filename: str, dataset_name: str) -> Dict[str, Any]:
        """Upload a file to the specified dataset"""
        files = {
            'file': (filename, file_content, 'application/octet-stream')
        }
        data = {
            'dataset_name': dataset_name
        }
        response = self._make_request('POST', '/upload', files=files, data=data)
        return response.json()
    
    def get_configuration(self) -> Dict[str, Any]:
        """Get the current configuration from the backend"""
        response = self._make_request('GET', '/configuration')
        return response.json()
    
    def update_configuration(self, config_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update the configuration via the backend"""
        response = self._make_request('POST', '/configuration', json=config_data)
        return response.json()
    
    def get_datasets(self) -> List[str]:
        """Get list of available datasets"""
        response = self._make_request('GET', '/datasets')
        return response.json()
    
    def get_dataset_files(self, dataset_name: str) -> List[Dict[str, Any]]:
        """Get files in a specific dataset"""
        response = self._make_request('GET', f'/datasets/{dataset_name}/files')
        return response.json()
    
    def get_documents(self, dataset_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get processed documents, optionally filtered by dataset"""
        params = {'dataset': dataset_name} if dataset_name else {}
        response = self._make_request('GET', '/documents', params=params)
        data = response.json()
        
        # Handle both old format (direct array) and new format (with wrapper)
        if isinstance(data, dict) and 'documents' in data:
            return data['documents']
        elif isinstance(data, list):
            return data
        else:
            return []
    
    def get_document_details(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get details for a specific document"""
        try:
            response = self._make_request('GET', f'/documents/{document_id}')
            return response.json()
        except requests.exceptions.RequestException:
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """Check if the backend is healthy"""
        # Try the health endpoint without /api prefix first (for local development)
        try:
            url = f"{self.backend_url}/health"
            response = self.session.get(url)
            response.raise_for_status()
            return response.json()
        except:
            # Fallback to /api/health for production backend
            response = self._make_request('GET', '/health')
            return response.json()
    
    def delete_document(self, document_id: str) -> Optional[requests.Response]:
        """Delete a document by ID"""
        try:
            response = self._make_request('DELETE', f'/documents/{document_id}')
            return response
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to delete document: {e}")
            return None
    
    def reprocess_document(self, document_id: str) -> Optional[requests.Response]:
        """Reprocess a document by ID"""
        try:
            response = self._make_request('POST', f'/documents/{document_id}/reprocess')
            return response
        except requests.exceptions.RequestException as e:
            st.error(f"Failed to reprocess document: {e}")
            return None


# Global backend client instance
backend_client = BackendClient()
