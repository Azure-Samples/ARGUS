def extract_document_info(doc):
    """Extract document information with proper dataset and filename parsing"""
    # Extract filename and dataset from document ID or other fields
    doc_id = doc.get("id", "")
    
    # Initialize defaults
    filename = "unknown"
    dataset = "unknown"
    
    # Method 1: Extract from document ID (format: dataset__filename) - This is the primary method
    if "__" in doc_id:
        parts = doc_id.split("__", 1)
        dataset = parts[0]
        filename = parts[1]
    
    # Method 2: Extract from properties.blob_name (most common in CosmosDB)
    properties = doc.get("properties", {})
    blob_name = properties.get("blob_name", "")
    if blob_name and "/" in blob_name:
        # Format: "dataset/filename.pdf"
        blob_parts = blob_name.split("/")
        if len(blob_parts) >= 2:
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])  # Handle nested paths
    
    # Method 3: Fallback to root-level blob_name if properties.blob_name not found
    elif doc.get("blob_name"):
        blob_name = doc.get("blob_name")
        if "/" in blob_name:
            blob_parts = blob_name.split("/")
            dataset = blob_parts[0]
            filename = "/".join(blob_parts[1:])
        else:
            filename = blob_name
    
    # Method 4: Use direct dataset/filename fields if available (override if they exist)
    if doc.get("dataset"):
        dataset = doc.get("dataset")
    if doc.get("file_name"):
        filename = doc.get("file_name")
    elif doc.get("filename"):
        filename = doc.get("filename")
    
    # Method 5: Extract from other properties fields as fallback
    if filename == "unknown":
        filename = (properties.get("original_filename") or 
                   properties.get("filename") or 
                   "unknown")
    
    # Final fallback for dataset
    if dataset == "unknown":
        dataset = (doc.get("dataset") or 
                  properties.get("dataset") or 
                  "default")
    
    # Remove Cosmos DB specific fields and simplify structure
    cleaned_doc = {
        "id": doc.get("id"),
        "file_name": filename,
        "dataset": dataset,
        "finished": doc.get("state", {}).get("processing_completed", False),
        "error": bool(doc.get("errors", [])),
        "created_at": doc.get("properties", {}).get("request_timestamp"),
        "modified_at": doc.get("_ts"),
        "size": doc.get("properties", {}).get("blob_size"),
        "pages": doc.get("properties", {}).get("num_pages"),
        "total_time": doc.get("properties", {}).get("total_time_seconds", 0),
        "extracted_data": doc.get("extracted_data", {}),
        "state": doc.get("state", {})
    }
    return cleaned_doc
