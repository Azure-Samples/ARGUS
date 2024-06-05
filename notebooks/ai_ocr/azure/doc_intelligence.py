from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential

from ai_ocr.azure.config import get_config

config = get_config()
kwargs = {"api_version": "2023-10-31-preview"}
client = document_analysis_client = DocumentIntelligenceClient(endpoint=config["doc_intelligence_endpoint"],
                                                               credential=AzureKeyCredential(config["doc_intelligence_key"]),
                                                               **kwargs)
client.mode = "page"


def get_ocr_results(file_path: str, output: str = "markdown") -> AnalyzeResult:
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout",
                                               analyze_request=f,
                                               content_type="application/octet-stream",
                                               features=["keyValuePairs"],
                                               output_content_format=output)
    return poller.result()
