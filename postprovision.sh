#!/bin/sh

# Ensure the function app is published
echo 'Building and publishing the function app...'
cd src/functionapp
# sleep 60
# func azure functionapp publish $functionAppName --build remote
az cosmosdb sql container create-item --account-name $cosmosDbAccountName --database-name $cosmosDbDatabaseName --container-name 'configuration' --resource-group $resourceGroup --partition-key-path "/configKey	" --body '{
    "id": "empty_schema",
    "data": "Sample data"
  }'

echo "Function app published."

# Insert an item into Cosmos DB if it doesn't exist
cosmos_container_exists=$(az cosmosdb sql container show --account-name $cosmosDbAccountName --database-name $cosmosDbDatabaseName --name $cosmosDbContainerName --resource-group $resourceGroup --query 'id' -o tsv)
if [ -z "$cosmos_container_exists" ]; then
  az cosmosdb sql container create --account-name $cosmosDbAccountName --database-name $cosmosDbDatabaseName --name $cosmosDbContainerName --resource-group $resourceGroup --partition-key-path "/partitionKey"
fi

# Check if the item exists
item_exists=$(az cosmosdb sql container show --account-name $cosmosDbAccountName --database-name $cosmosDbDatabaseName --name $cosmosDbContainerName --resource-group $resourceGroup --query "id" -o tsv)
if [ -z "$item_exists" ]; then
  az cosmosdb sql container create-item --account-name $cosmosDbAccountName --database-name $cosmosDbDatabaseName --container-name $cosmosDbContainerName --resource-group $resourceGroup --partition-key-path "/partitionKey" --body '{
    "id": "empty_schema",
    "data": "Sample data"
  }'
else
  echo "Item already exists in Cosmos DB."
fi

# # Create a folder in the storage container
# az storage blob directory create --account-name $storageAccountName --container-name 'datasets' --name 'empty_schema'

# echo "Post-provisioning steps completed."