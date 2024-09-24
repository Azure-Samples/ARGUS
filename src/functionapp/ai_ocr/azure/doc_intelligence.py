import json
import pandas as pd
import os
import sys
import html

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.formrecognizer import DocumentAnalysisClient, AnalysisFeature
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from azure.ai.formrecognizer import DocumentAnalysisClient

from ai_ocr.azure.config import get_config

config = get_config()

# kwargs = {"api_version": doc_int_api_version}
client = document_analysis_client = DocumentAnalysisClient(endpoint=config["doc_intelligence_endpoint"],
                                                               credential=AzureKeyCredential(config["doc_intelligence_key"]),
                                                               headers={"solution":"ARGUS-1.0"})
                                                            #    **kwargs)

# Get OCR and convert it to HTML, using ocr_high_resolution feature as default
def get_ocr_results(file_path: str):
    with open(file_path, "rb") as f:
        poller = client.begin_analyze_document("prebuilt-layout",
                                               document=f,
                                               features=[AnalysisFeature.OCR_HIGH_RESOLUTION])
    ocr_result = poller.result()
    return ocr_to_html(ocr_result)

def table_to_html(table):
    table_html = "<table>"
    rows = [
        sorted(
            [cell for cell in table.cells if cell.row_index == i],
            key=lambda cell: cell.column_index,
        )
        for i in range(table.row_count)
    ]
    for row_cells in rows:
        table_html += "<tr>"
        for cell in row_cells:
            tag = (
                "th"
                if (cell.kind == "columnHeader" or cell.kind == "rowHeader")
                else "td"
            )
            cell_spans = ""
            if cell.column_span > 1:
                cell_spans += f" colSpan={cell.column_span}"
            if cell.row_span > 1:
                cell_spans += f" rowSpan={cell.row_span}"
            table_html += f"<{tag}{cell_spans}>{html.escape(cell.content)}</{tag}>"
        table_html += "</tr>"
    table_html += "</table>"
    return table_html

def ocr_to_html(form_recognizer_results):
    offset = 0
    page_map = []
    form_recognizer_role_to_html = {
        "title": "h1",
        "sectionHeading": "h2",
        "pageHeader": None,
        "pageFooter": None,
        "paragraph": "p",
    }

    try:
        roles_start = {}
        roles_end = {}
        for paragraph in form_recognizer_results.paragraphs:
            # if paragraph.role!=None:
            para_start = paragraph.spans[0].offset
            para_end = paragraph.spans[0].offset + paragraph.spans[0].length
            roles_start[para_start] = (
                paragraph.role if paragraph.role is not None else "paragraph"
            )
            roles_end[para_end] = (
                paragraph.role if paragraph.role is not None else "paragraph"
            )

        for page_num, page in enumerate(form_recognizer_results.pages):
            tables_on_page = [
                table
                for table in form_recognizer_results.tables
                if table.bounding_regions[0].page_number == page_num + 1
            ]

            # mark all positions of the table spans in the page
            page_offset = page.spans[0].offset
            page_length = page.spans[0].length
            table_chars = [-1] * page_length
            for table_id, table in enumerate(tables_on_page):
                for span in table.spans:
                    # replace all table spans with "table_id" in table_chars array
                    for i in range(span.length):
                        idx = span.offset - page_offset + i
                        if idx >= 0 and idx < page_length:
                            table_chars[idx] = table_id

            # build page text by replacing charcters in table spans with table html and replace the characters corresponding to headers with html headers, if using layout
            page_text = ""
            added_tables = set()
            for idx, table_id in enumerate(table_chars):
                if table_id == -1:
                    position = page_offset + idx
                    if position in roles_start.keys():
                        role = roles_start[position]
                        html_role = form_recognizer_role_to_html.get(role)
                        if html_role is not None:
                            page_text += f"<{html_role}>"
                    if position in roles_end.keys():
                        role = roles_end[position]
                        html_role = form_recognizer_role_to_html.get(role)
                        if html_role is not None:
                            page_text += f"</{html_role}>"

                    page_text += form_recognizer_results.content[page_offset + idx]

                elif table_id not in added_tables:
                    page_text += table_to_html(tables_on_page[table_id])
                    added_tables.add(table_id)

            page_text += " "
            page_map.append(
                {"page_number": page_num, "offset": offset, "page_text": page_text}
            )
            offset += len(page_text)

        return page_map
    except Exception as e:
        print(f"Error converting OCR results to HTML: {e}")
        return None


## FUNCTIONS BELOW ARE NOT USED IN THE CURRENT IMPLEMENTATION (OCR to markdown is not used)
def parse_paragraphs(paragraphs):
    """
    Parse the paragraphs from the OCR data to generate markdown content.
    """
    markdown_content = ""
    for paragraph in paragraphs:
        content = paragraph["content"].strip()
        role = paragraph.get("role")

        if role == "title":
            markdown_content += f"# {content}\n\n"
        elif role == "sectionHeading":
            markdown_content += f"## {content}\n\n"
        elif content.startswith("-"):
            # Assuming content that starts with "-" is a list item
            markdown_content += f"{content}\n"
        else:
            markdown_content += f"{content}\n\n"

    return markdown_content

def extract_table_data(table):
    rows = table['rowCount']
    columns = table['columnCount']

    # Create a 2D list to hold the table data
    table_data = [['' for _ in range(columns)] for _ in range(rows)]

    # Populate the table data
    for cell in table['cells']:
        row = cell['rowIndex']
        col = cell['columnIndex']
        table_data[row][col] = cell['content']

    # Convert the table data into a pandas DataFrame
    df = pd.DataFrame(table_data)

    # Set the first row as header
    df.columns = df.iloc[0]
    df = df[1:].reset_index(drop=True)

    return df

def df_to_markdown(df):
    return df.to_markdown(index=False)

def ocr_to_markdown(ocr_data):
    markdown_output = "# Document Analysis\n\n"
    analyze_result = ocr_data.get('analyzeResult', {})
    analyze_result = ocr_data
    # Process paragraphs
    if 'paragraphs' in analyze_result:
        markdown_output += "## Paragraphs\n\n"
        markdown_output += parse_paragraphs(analyze_result['paragraphs'])

    # Process tables
    if 'tables' in analyze_result:
        markdown_output += "## Tables\n\n"
        for i, table in enumerate(analyze_result['tables'], 1):
            markdown_output += f"### Table {i}\n\n"
            df = extract_table_data(table)
            markdown_output += df_to_markdown(df) + "\n\n"

    # Process pages
    if 'pages' in analyze_result:
        markdown_output += "## Page Details\n\n"
        for page in analyze_result['pages']:
            markdown_output += f"### Page {page['pageNumber']}\n\n"
            markdown_output += f"- Dimensions: {page['width']} x {page['height']} {page['unit']}\n"
            markdown_output += f"- Rotation: {page['angle']} degrees\n\n"

            # Process words on the page
            markdown_output += "#### Words on this page:\n\n"
            for word in page['words']:
                markdown_output += f"- {word['content']} (Confidence: {word['confidence']})\n"
            markdown_output += "\n"

    return markdown_output