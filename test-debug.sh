#!/bin/bash

# Debug Script for ARGUS Troubleshooting
# This script helps diagnose specific issues with the ARGUS deployment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration from environment
ENV_FILE=".azure/argus-test/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}Error: Environment file not found at $ENV_FILE${NC}"
    exit 1
fi

# Source environment variables
source "$ENV_FILE"

# Required variables
STORAGE_ACCOUNT=$(echo $BLOB_ACCOUNT_URL | sed 's/https:\/\///' | cut -d'.' -f1)
# Get the correct FQDN from Azure CLI
CONTAINER_APP_FQDN=$(az containerapp show --name "$AZURE_CONTAINER_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query 'properties.configuration.ingress.fqdn' --output tsv)
CONTAINER_APP_URL="https://${CONTAINER_APP_FQDN}"

echo -e "${BLUE}=== ARGUS Debug Information ===${NC}"
echo

# Function to show environment info
show_environment() {
    echo -e "${BLUE}=== Environment Configuration ===${NC}"
    echo "Azure Subscription: $AZURE_SUBSCRIPTION_ID"
    echo "Resource Group: $AZURE_RESOURCE_GROUP"
    echo "Location: $AZURE_LOCATION"
    echo "Container App: $AZURE_CONTAINER_APP_NAME"
    echo "Storage Account: $STORAGE_ACCOUNT"
    echo "Storage Container: $CONTAINER_NAME"
    echo "Cosmos DB: $COSMOS_URL"
    echo "Document Intelligence: $DOCUMENT_INTELLIGENCE_ENDPOINT"
    echo
}

# Function to check resource status
check_resources() {
    echo -e "${BLUE}=== Resource Status ===${NC}"
    
    echo -e "${YELLOW}Container App Status:${NC}"
    az containerapp show \
        --name "$AZURE_CONTAINER_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query '{name:name,status:properties.runningStatus,fqdn:properties.configuration.ingress.fqdn,replicas:properties.template.scale.minReplicas}' \
        --output table
    echo
    
    echo -e "${YELLOW}Storage Account Status:${NC}"
    az storage account show \
        --name "$STORAGE_ACCOUNT" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query '{name:name,status:statusOfPrimary,location:location}' \
        --output table
    echo
    
    echo -e "${YELLOW}Cosmos DB Status:${NC}"
    COSMOS_ACCOUNT=$(echo $COSMOS_URL | sed 's/https:\/\///' | cut -d'.' -f1)
    az cosmosdb show \
        --name "$COSMOS_ACCOUNT" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --query '{name:name,status:provisioningState,location:location}' \
        --output table
    echo
}

# Function to check container logs
check_logs() {
    echo -e "${BLUE}=== Recent Application Logs ===${NC}"
    
    echo -e "${YELLOW}Last 50 log entries:${NC}"
    az containerapp logs show \
        --name "$AZURE_CONTAINER_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --follow false \
        --tail 50 || echo "Could not retrieve logs"
    echo
}

# Function to check blob storage
check_storage() {
    echo -e "${BLUE}=== Storage Account Analysis ===${NC}"
    
    echo -e "${YELLOW}Container list:${NC}"
    az storage container list \
        --account-name "$STORAGE_ACCOUNT" \
        --auth-mode login \
        --output table
    echo
    
    echo -e "${YELLOW}Blobs in datasets container:${NC}"
    az storage blob list \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$CONTAINER_NAME" \
        --auth-mode login \
        --output table
    echo
    
    echo -e "${YELLOW}Recent blob activities:${NC}"
    az storage blob list \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$CONTAINER_NAME" \
        --auth-mode login \
        --query '[].{Name:name,Size:properties.contentLength,Modified:properties.lastModified}' \
        --output table
    echo
}

# Function to test connectivity
test_connectivity() {
    echo -e "${BLUE}=== Connectivity Tests ===${NC}"
    
    echo -e "${YELLOW}Testing Container App endpoints:${NC}"
    echo "Health endpoint:"
    curl -s -w "Status: %{http_code}, Time: %{time_total}s\n" "$CONTAINER_APP_URL/health" -o /dev/null || echo "Failed to connect"
    
    echo "Root endpoint:"
    curl -s -w "Status: %{http_code}, Time: %{time_total}s\n" "$CONTAINER_APP_URL/" -o /dev/null || echo "Failed to connect"
    
    echo "Process blob endpoint (POST):"
    curl -s -w "Status: %{http_code}, Time: %{time_total}s\n" -X POST "$CONTAINER_APP_URL/api/process-blob" -H "Content-Type: application/json" -d '{}' -o /dev/null || echo "Failed to connect"
    echo
}

# Function to analyze recent errors
analyze_errors() {
    echo -e "${BLUE}=== Error Analysis ===${NC}"
    
    echo -e "${YELLOW}Searching for recent errors in logs:${NC}"
    az containerapp logs show \
        --name "$AZURE_CONTAINER_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --follow false \
        --tail 100 2>/dev/null | grep -i "error\|exception\|failed\|traceback" | tail -20 || echo "No recent errors found"
    echo
}

# Function to check RBAC permissions
check_permissions() {
    echo -e "${BLUE}=== RBAC Permissions Check ===${NC}"
    
    echo -e "${YELLOW}Container App Identity:${NC}"
    az containerapp identity show \
        --name "$AZURE_CONTAINER_APP_NAME" \
        --resource-group "$AZURE_RESOURCE_GROUP" \
        --output table 2>/dev/null || echo "Could not retrieve identity info"
    echo
    
    echo -e "${YELLOW}Role assignments for managed identity:${NC}"
    MANAGED_IDENTITY_PRINCIPAL_ID="$AZURE_PRINCIPAL_ID"
    if [ ! -z "$MANAGED_IDENTITY_PRINCIPAL_ID" ]; then
        az role assignment list \
            --assignee "$MANAGED_IDENTITY_PRINCIPAL_ID" \
            --query '[].{Role:roleDefinitionName,Scope:scope}' \
            --output table
    else
        echo "Could not determine managed identity principal ID"
    fi
    echo
}

# Function to test blob URL formats
test_blob_urls() {
    echo -e "${BLUE}=== Blob URL Format Testing ===${NC}"
    
    echo -e "${YELLOW}Testing different blob URL formats:${NC}"
    
    # Find a test blob
    TEST_BLOB=$(az storage blob list \
        --account-name "$STORAGE_ACCOUNT" \
        --container-name "$CONTAINER_NAME" \
        --auth-mode login \
        --query '[0].name' \
        --output tsv 2>/dev/null)
    
    if [ ! -z "$TEST_BLOB" ]; then
        echo "Using test blob: $TEST_BLOB"
        echo
        
        # Test different URL formats
        BASE_URL="${BLOB_ACCOUNT_URL}${CONTAINER_NAME}"
        
        echo "Format 1: $BASE_URL/$TEST_BLOB"
        curl -s -w "Status: %{http_code}\n" -X POST \
            -H "Content-Type: application/json" \
            -d "{\"blob_url\": \"$BASE_URL/$TEST_BLOB\"}" \
            "$CONTAINER_APP_URL/api/process-blob" -o /dev/null
        
        echo "Format 2: ${BLOB_ACCOUNT_URL}${TEST_BLOB}"
        curl -s -w "Status: %{http_code}\n" -X POST \
            -H "Content-Type: application/json" \
            -d "{\"blob_url\": \"${BLOB_ACCOUNT_URL}${TEST_BLOB}\"}" \
            "$CONTAINER_APP_URL/api/process-blob" -o /dev/null
        
    else
        echo "No test blobs found in storage"
    fi
    echo
}

# Function to show suggested fixes
show_suggestions() {
    echo -e "${BLUE}=== Troubleshooting Suggestions ===${NC}"
    echo
    echo -e "${YELLOW}Common issues and fixes:${NC}"
    echo
    echo "1. Blob Not Found Error:"
    echo "   - Check blob path format in storage"
    echo "   - Verify container name matches CONTAINER_NAME env var"
    echo "   - Ensure blob URL format matches what the app expects"
    echo
    echo "2. Authentication Issues:"
    echo "   - Verify managed identity has correct RBAC roles"
    echo "   - Check if Storage Blob Data Contributor role is assigned"
    echo "   - Verify Cosmos DB Data Contributor role is assigned"
    echo
    echo "3. Application Errors:"
    echo "   - Check application logs for detailed error messages"
    echo "   - Verify all environment variables are set correctly"
    echo "   - Check if container app is running and healthy"
    echo
    echo "4. Network Connectivity:"
    echo "   - Test endpoints with curl"
    echo "   - Verify firewall rules and network security groups"
    echo
    echo -e "${YELLOW}Manual verification steps:${NC}"
    echo "1. Azure Portal > Container Apps > $AZURE_CONTAINER_APP_NAME > Logs"
    echo "2. Azure Portal > Storage Accounts > $STORAGE_ACCOUNT > Containers > $CONTAINER_NAME"
    echo "3. Azure Portal > Cosmos DB > Check documents in database"
    echo
}

# Main debug function
main() {
    echo -e "${BLUE}Starting ARGUS debug analysis...${NC}"
    echo
    
    show_environment
    check_resources
    test_connectivity
    check_storage
    check_logs
    analyze_errors
    check_permissions
    test_blob_urls
    show_suggestions
    
    echo -e "${GREEN}=== Debug Analysis Complete ===${NC}"
}

# Run main function
main "$@"
