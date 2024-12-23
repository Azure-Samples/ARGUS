import json
import pandas as pd
from azure.identity import DefaultAzureCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import DocumentAnalysisFeature
from ai_ocr.azure.config import get_config


config = get_config()

document_intelligence_client = DocumentIntelligenceClient(endpoint=config["doc_intelligence_endpoint"],
                                                               credential=DefaultAzureCredential(),
                                                               headers={"solution":"ARGUS-1.0"})

def get_ocr_results(file_path: str):
    with open(file_path, "rb") as f:
        poller = document_intelligence_client.begin_analyze_document("prebuilt-layout", 
                                                                     body=f, 
                                                                     features=[DocumentAnalysisFeature.OCR_HIGH_RESOLUTION])
    ocr_result = poller.result().content
    return ocr_result

