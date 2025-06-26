"""
Data models for the ARGUS Container App
"""
from typing import Dict, Any


class EventGridEvent:
    """Event Grid event model"""
    def __init__(self, event_data: Dict[str, Any]):
        self.id = event_data.get('id')
        self.event_type = event_data.get('eventType')
        self.subject = event_data.get('subject')
        self.event_time = event_data.get('eventTime')
        self.data = event_data.get('data', {})
        self.data_version = event_data.get('dataVersion')
        self.metadata_version = event_data.get('metadataVersion')


class BlobInputStream:
    """Mock BlobInputStream to match the original function interface"""
    def __init__(self, blob_name: str, blob_size: int, blob_client):
        self.name = blob_name
        self.length = blob_size
        self._blob_client = blob_client
        self._content = None
    
    def read(self, size: int = -1):
        """Read blob content"""
        if self._content is None:
            blob_data = self._blob_client.download_blob()
            self._content = blob_data.readall()
        
        if size == -1:
            return self._content
        else:
            return self._content[:size]
