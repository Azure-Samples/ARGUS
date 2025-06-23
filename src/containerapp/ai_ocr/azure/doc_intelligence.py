import json
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from ai_ocr.azure.config import get_config


def get_document_intelligence_client(cosmos_config_container=None):
    """Create a new Document Intelligence client instance for each request to avoid connection pooling issues"""
    config = get_config(cosmos_config_container)
    return DocumentIntelligenceClient(
        endpoint=config["doc_intelligence_endpoint"],
        credential=DefaultAzureCredential(),
        headers={"solution":"ARGUS-1.0"}
    )

def get_ocr_results(file_path: str, cosmos_config_container=None):
    import threading
    import logging
    
    thread_id = threading.current_thread().ident
    logger = logging.getLogger(__name__)
    
    logger.info(f"[Thread-{thread_id}] Starting Document Intelligence OCR for: {file_path}")
    
    # Create a new client instance for this request to ensure parallel processing
    client = get_document_intelligence_client(cosmos_config_container)
    
    with open(file_path, "rb") as f:
        logger.info(f"[Thread-{thread_id}] Submitting document to Document Intelligence API")
        poller = client.begin_analyze_document("prebuilt-layout", body=f)

    logger.info(f"[Thread-{thread_id}] Waiting for Document Intelligence results...")
    ocr_result = poller.result().content
    logger.info(f"[Thread-{thread_id}] Document Intelligence OCR completed, {len(ocr_result)} characters")
    
    return ocr_result

