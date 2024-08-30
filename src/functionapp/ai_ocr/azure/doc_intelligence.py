import json
import pandas as pd
import os
import sys

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

from ai_ocr.azure.config import get_config

config = get_config()

#New Document Intelligence (preview)
kwargs = {"api_version": "2023-10-31-preview"}
client = document_analysis_client = DocumentIntelligenceClient(endpoint=config["doc_intelligence_endpoint"],
                                                               credential=AzureKeyCredential(config["doc_intelligence_key"]),
                                                               headers={"solution":"ARGUS-1.0"},
                                                               **kwargs)
client.mode = "page"

def get_ocr_results(file_path: str, output: str = "markdown") -> AnalyzeResult:
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout",
                                               analyze_request=f,
                                               content_type="application/octet-stream",
                                            #    features=["keyValuePairs"],
                                               output_content_format=output)
    return poller.result()


#Legacy Document Intelligence
api_version_ga="2023-07-31"                                                            
legacy_di_endpoint = config["doc_intelligence_endpoint"]
legacy_di_key = config["doc_intelligence_key"]

document_analysis_client = DocumentAnalysisClient(
    endpoint=legacy_di_endpoint, credential=AzureKeyCredential(legacy_di_key), api_version=api_version_ga
)

def get_ocr_results_ga(file_path: str) -> AnalyzeResult:
    with open(file_path, "rb") as f:
        poller = document_analysis_client.begin_analyze_document("prebuilt-layout", document=f)
    return poller.result()


#functions to transfrom to markdown
def parse_lines(lines):
    """
    Parse the lines from the OCR data to generate markdown content.
    """
    markdown_content = ""
    for line_idx, line in enumerate(lines):
        line_content = ""
        words = line.get_words()

        for word in words:
            print(
                "......Word '{}' has a confidence of {}".format(
                    word.content, word.confidence
                )
            )
            line_content += f"{word.content} (Confidence: {word.confidence:.2f}) "

        markdown_content += line_content.strip() + "\n" 

    markdown_content += "\n"
    return markdown_content

def extract_table_data(table):

    rows = table.row_count
    columns = table.column_count

    # Create a 2D list to hold the table data
    table_data = [['' for _ in range(columns)] for _ in range(rows)]

    # Populate the table data
    for cell in table.cells:
        row = cell.row_index
        col = cell.column_index
        table_data[row][col] = cell.content

    # Convert the table data into a pandas DataFrame
    df = pd.DataFrame(table_data)

    # Set the first row as header, if appropriate
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    return df

def df_to_markdown(df):
    return df.to_markdown(index=False)

def ocr_to_markdown(ocr_data):
    markdown_output = "# Document Analysis\n\n"

    pages = ocr_data.pages

    # Process pages
    for page in pages:
        markdown_output += f"## Page {page.page_number}\n\n"
        #markdown_output += f"- Dimensions: {page.width} x {page.height} {page.unit}\n"
        #markdown_output += f"- Rotation: {page.angle} degrees\n\n"

        # Process lines
        for line_idx, line in enumerate(page.lines):
            markdown_output += parse_lines([line])

    # Process tables within the page
    for table in ocr_data.tables:
        markdown_output += "### Table\n\n"
        df = extract_table_data(table)
        markdown_output += df_to_markdown(df) + "\n\n"    

    return markdown_output
