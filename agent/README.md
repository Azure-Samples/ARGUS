# ARGUS MCP Server

This directory contains a Model Context Protocol (MCP) server for the ARGUS project, which provides tools for interacting with the ARGUS system.

## Features

- Upload files to Azure Blob Storage using the `upload_file_to_blob` tool
- Manage datasets with `list_datasets`, `get_dataset_details`, and `update_dataset` tools
- View processed files with `get_processed_files` and get detailed information with `get_file_details`
- Delete processed files using the `delete_file` tool
- Trigger reprocessing of files with the `reprocess_file` tool
- Get system information with the `get_system_info` tool

## Prerequisites

- Python 3.8+
- Azure account with Blob Storage and CosmosDB configured
- Required environment variables (see below)

## Environment Variables

Create a `.env` file in this directory with the following variables:

```
BLOB_ACCOUNT_URL=<your-blob-account-url>
CONTAINER_NAME=<your-blob-container-name>
COSMOS_URL=<your-cosmos-db-url>
COSMOS_DB_NAME=<your-cosmos-db-name>
COSMOS_CONFIG_CONTAINER_NAME=<your-cosmos-config-container-name>
COSMOS_DOCUMENTS_CONTAINER_NAME=<your-documents-container-name>
```

## Installation

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Usage

### Running the MCP server

```bash
python server.py
```

This will start the server using SSE transport, which is suitable for development and testing.

### Testing with Chatlit App

You can test the ARGUS MCP server using the included chatlit app:

```bash
python chat.py
```

This will launch a chat interface where you can interact with the ARGUS system through natural language.

### Using with Claude in Claude Desktop

To install this server for use with Claude Desktop:

```bash
mcp install server.py
```

## Development

To test the server in development mode:

```bash
mcp dev server.py
```

This will start the MCP Inspector, which provides a UI for testing tools and resources.

## Integration with ARGUS Frontend

This MCP server complements the existing ARGUS frontend by providing a programmatic interface to the same Azure resources that the frontend uses. The frontend allows for visual exploration and management of data, while the MCP server enables programmatic and AI-assisted interactions.
