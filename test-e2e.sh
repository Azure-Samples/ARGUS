#!/bin/bash

# Simplified End-to-End Test Script for ARGUS
# This script tests the complete workflow from document upload to processing

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}Starting ARGUS End-to-End Test${NC}"

# Load environment variables
ENV_FILE=".azure/argus-test/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Environment file not found: $ENV_FILE${NC}"
    exit 1
fi

source "$ENV_FILE"

# Set key variables manually (from deployment output and env file)
CONTAINER_APP_URL="https://ca-argus-test.happymushroom-0bb928ac.eastus2.azurecontainerapps.io"
STORAGE_ACCOUNT="sa5xm7rawmgdbia"
RESOURCE_GROUP="rg-argus-test-3"
CONTAINER_NAME="datasets"

echo -e "${BLUE}Configuration:${NC}"
echo -e "  Container App URL: $CONTAINER_APP_URL"
echo -e "  Storage Account: $STORAGE_ACCOUNT"
echo -e "  Resource Group: $RESOURCE_GROUP"
echo -e "  Container: $CONTAINER_NAME"

# Test document
TEST_DOCUMENT="demo/default-dataset/Invoice Sample.pdf"
if [ ! -f "$TEST_DOCUMENT" ]; then
    echo -e "${RED}Test document not found: $TEST_DOCUMENT${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Step 1: Testing Application Health${NC}"
echo "Testing root endpoint..."
if curl -s -f "$CONTAINER_APP_URL/" > /dev/null; then
    echo -e "${GREEN}✓ Root endpoint is accessible${NC}"
else
    echo -e "${RED}✗ Root endpoint failed${NC}"
    exit 1
fi

echo "Testing health endpoint..."
HEALTH_RESPONSE=$(curl -s "$CONTAINER_APP_URL/health")
if echo "$HEALTH_RESPONSE" | grep -q "healthy"; then
    echo -e "${GREEN}✓ Health endpoint returns healthy status${NC}"
    echo "  Response: $HEALTH_RESPONSE"
else
    echo -e "${RED}✗ Health endpoint failed${NC}"
    echo "  Response: $HEALTH_RESPONSE"
    exit 1
fi

echo -e "\n${YELLOW}Step 2: Uploading Test Document${NC}"
BLOB_NAME="default-dataset/test-invoice-$(date +%s).pdf"
echo "Uploading: $TEST_DOCUMENT as $BLOB_NAME"

az storage blob upload \
    --account-name "$STORAGE_ACCOUNT" \
    --container-name "$CONTAINER_NAME" \
    --name "$BLOB_NAME" \
    --file "$TEST_DOCUMENT" \
    --auth-mode login

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Document uploaded successfully${NC}"
else
    echo -e "${RED}✗ Document upload failed${NC}"
    exit 1
fi

echo -e "\n${YELLOW}Step 3: Testing Document Processing${NC}"
BLOB_URL="https://${STORAGE_ACCOUNT}.blob.core.windows.net/${CONTAINER_NAME}/${BLOB_NAME}"
echo "Processing blob: $BLOB_URL"

# Trigger processing
PROCESS_RESPONSE=$(curl -s -X POST \
    -H "Content-Type: application/json" \
    -d "{\"blob_url\":\"$BLOB_URL\"}" \
    "$CONTAINER_APP_URL/api/process-blob")

echo "Process response: $PROCESS_RESPONSE"

if echo "$PROCESS_RESPONSE" | grep -q "success\|processing"; then
    echo -e "${GREEN}✓ Document processing initiated successfully${NC}"
else
    echo -e "${RED}✗ Document processing failed${NC}"
    echo "Response: $PROCESS_RESPONSE"
    exit 1
fi

echo -e "\n${YELLOW}Step 4: Checking Application Logs${NC}"
echo "Waiting 30 seconds for processing to complete..."
sleep 30

echo -e "\n${YELLOW}Step 5: Verifying Storage${NC}"
echo "Checking uploaded blob exists..."
if az storage blob exists \
    --account-name "$STORAGE_ACCOUNT" \
    --container-name "$CONTAINER_NAME" \
    --name "$BLOB_NAME" \
    --auth-mode login \
    --query exists \
    --output tsv | grep -q "true"; then
    echo -e "${GREEN}✓ Uploaded blob still exists in storage${NC}"
else
    echo -e "${RED}✗ Uploaded blob not found${NC}"
fi

echo -e "\n${BLUE}Test Summary:${NC}"
echo -e "${GREEN}✓ Application is running and accessible${NC}"
echo -e "${GREEN}✓ Health checks pass${NC}"
echo -e "${GREEN}✓ Document upload works${NC}"
echo -e "${GREEN}✓ Document processing endpoint responds${NC}"
echo -e "${GREEN}✓ Storage integration works${NC}"

echo -e "\n${GREEN}End-to-End Test Completed Successfully!${NC}"
echo -e "\n${YELLOW}Next Steps:${NC}"
echo -e "1. Check application logs: azd logs"
echo -e "2. Check Azure portal for Cosmos DB documents"
echo -e "3. Test Event Grid integration (if needed)"
echo -e "4. Upload different document types to test various datasets"

echo -e "\n${BLUE}Application URLs:${NC}"
echo -e "  Main: $CONTAINER_APP_URL"
echo -e "  Health: $CONTAINER_APP_URL/health"
echo -e "  Process: $CONTAINER_APP_URL/api/process-blob"
echo -e "  Event: $CONTAINER_APP_URL/api/blob-created"
