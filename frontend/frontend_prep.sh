#!/bin/bash

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | xargs)
else
    echo "Error: .env file not found"
    exit 1
fi

# Check if required environment variables are set
required_vars=(
    "BLOB_CONN_STR" "CONTAINER_NAME" "COSMOS_URL" "COSMOS_DB_NAME"
    "COSMOS_DOCUMENTS_CONTAINER_NAME" "COSMOS_CONFIG_CONTAINER_NAME"
    "RESOURCE_GROUP_NAME" "COSMOS_ACCOUNT_NAME"
)
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "Error: $var is not set in the .env file"
        exit 1
    fi
done

# Use the values from .env file
resourceGroupName=$RESOURCE_GROUP_NAME
accountName=$COSMOS_ACCOUNT_NAME

az login

# Get the principal ID of the signed-in user
principalId=$(az ad signed-in-user show --query id -o tsv)

if [ -z "$principalId" ]; then
    echo "Error: Failed to get the principal ID of the signed-in user"
    exit 1
fi

# Get the scope of the Cosmos DB account
scope=$(
    az cosmosdb show \
        --resource-group $resourceGroupName \
        --name $accountName \
        --query id \
        --output tsv
)

if [ -z "$scope" ]; then
    echo "Error: Failed to get the scope of the Cosmos DB account"
    exit 1
fi

# Create role assignment
echo "Creating role assignment for the signed-in user..."
az cosmosdb sql role assignment create \
    --resource-group $resourceGroupName \
    --account-name $accountName \
    --role-definition-name "Cosmos DB Built-in Data Contributor" \
    --principal-id $principalId \
    --scope $scope

if [ $? -eq 0 ]; then
    echo "Role assignment created successfully for the signed-in user"
else
    echo "Error: Failed to create role assignment"
    exit 1
fi