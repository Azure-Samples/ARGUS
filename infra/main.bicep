// Define the resource group location
param location string = resourceGroup().location

// Define the storage account name
param storageAccountName string = 'sa${uniqueString(resourceGroup().id)}'

// Define the Cosmos DB account name
param cosmosDbAccountName string = 'cb${uniqueString(resourceGroup().id)}'

// Define the Cosmos DB database name
param cosmosDbDatabaseName string = 'doc-extracts'

// Define the Cosmos DB container name
param cosmosDbContainerName string = 'documents'

// Define the function app name
param functionAppName string = 'fa${uniqueString(resourceGroup().id)}'

// Define the storage account for function app
param functionAppStorageName string = 'fs${uniqueString(resourceGroup().id)}'

param appServicePlanName string = '${functionAppName}-plan'

// Define the Document Intelligence resource name
param documentIntelligenceName string = 'di${uniqueString(resourceGroup().id)}'

// Define the location for the Document Intelligence resource
@allowed([
  'westeurope'
  'eastus'
])
param documentIntelligenceLocation string

// Define the Azure OpenAI parameters
@secure()
param azureOpenaiEndpoint string
@secure()
param azureOpenaiKey string
param azureOpenaiModelDeploymentName string

// Define the storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2022-05-01' = {
  name: storageAccountName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

// Define the blob service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-05-01' = {
  parent: storageAccount
  name: 'default'
}

// Define the blob container
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-05-01' = {
  parent: blobService
  name: 'datasets'
  properties: {
    publicAccess: 'None'
  }
}

// Define the Cosmos DB account
resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2021-04-15' = {
  name: cosmosDbAccountName
  location: location
  kind: 'GlobalDocumentDB'
  properties: {
    databaseAccountOfferType: 'Standard'
    locations: [
      {
        locationName: location
        failoverPriority: 0
        isZoneRedundant: false
      }
    ]
    consistencyPolicy: {
      defaultConsistencyLevel: 'Session'
    }
    capabilities: [
      {
        name: 'EnableServerless'
      }
    ]
  }
}

// Define the Cosmos DB database
resource cosmosDbDatabase 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2021-04-15' = {
  parent: cosmosDbAccount
  name: cosmosDbDatabaseName
  properties: {
    resource: {
      id: cosmosDbDatabaseName
    }
  }
}

// Define the Cosmos DB container for documents
resource cosmosDbContainer 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2021-04-15' = {
  parent: cosmosDbDatabase
  name: cosmosDbContainerName
  properties: {
    resource: {
      id: cosmosDbContainerName
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

// Define the Cosmos DB container for configuration
resource cosmosDbContainerConf 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2021-04-15' = {
  parent: cosmosDbDatabase
  name: 'configuration'
  properties: {
    resource: {
      id: 'configuration'
      partitionKey: {
        paths: ['/partitionKey']
        kind: 'Hash'
      }
      defaultTtl: -1
    }
  }
}

// Define the storage account for function app
resource functionAppStorage 'Microsoft.Storage/storageAccounts@2022-05-01' = {
  name: functionAppStorageName
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

// Define the blob service for function app storage
resource functionAppBlobService 'Microsoft.Storage/storageAccounts/blobServices@2022-05-01' = {
  parent: functionAppStorage
  name: 'default'
}

// Define the storage container for function app code
resource codeContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-05-01' = {
  parent: functionAppBlobService
  name: 'app-artifacts'
  properties: {
    publicAccess: 'None'
  }
}

// Define the Application Insights resource
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'app-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    Request_Source: 'rest'
  }
}

// Define the App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2021-03-01' = {
  name: appServicePlanName
  location: location
  kind: 'Linux'
  sku: {
    name: 'P0V3'
    tier: 'Premium'
  }
  properties: {
    reserved: true
  }
}

// Define the Document Intelligence resource
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2021-04-30' = {
  name: documentIntelligenceName
  location: documentIntelligenceLocation
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  properties: {
    apiProperties: {}
    customSubDomainName: documentIntelligenceName
  }
}

// Define the Function App
resource functionApp 'Microsoft.Web/sites@2021-03-01' = {
  name: functionAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'functionapp'
  tags: {
    'azd-service-name': 'functionapp'
  }
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'python|3.11'
      alwaysOn: true
      appSettings: [
        {
          name: 'AzureWebJobsStorage'
          value: 'DefaultEndpointsProtocol=https;AccountName=${storageAccount.name};AccountKey=${listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTAZUREFILECONNECTIONSTRING'
          value: 'DefaultEndpointsProtocol=https;AccountName=${functionAppStorage.name};AccountKey=${listKeys(functionAppStorage.id, functionAppStorage.apiVersion).keys[0].value};EndpointSuffix=core.windows.net'
        }
        {
          name: 'WEBSITE_CONTENTSHARE'
          value: 'functionapp-content'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {
          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: applicationInsights.properties.InstrumentationKey
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'COSMOS_DB_ENDPOINT'
          value: cosmosDbAccount.properties.documentEndpoint
        }
        {
          name: 'COSMOS_DB_KEY'
          value: cosmosDbAccount.listKeys().primaryMasterKey
        }
        {
          name: 'COSMOS_DB_DATABASE_NAME'
          value: cosmosDbDatabaseName
        }
        {
          name: 'COSMOS_DB_CONTAINER_NAME'
          value: cosmosDbContainerName
        }
        {
          name: 'DOCUMENT_INTELLIGENCE_ENDPOINT'
          value: documentIntelligence.properties.endpoint
        }
        {
          name: 'DOCUMENT_INTELLIGENCE_KEY'
          value: documentIntelligence.listKeys().key1
        }
        {
          name: 'AZURE_OPENAI_ENDPOINT'
          value: azureOpenaiEndpoint
        }
        {
          name: 'AZURE_OPENAI_KEY'
          value: azureOpenaiKey
        }
        {
          name: 'AZURE_OPENAI_MODEL_DEPLOYMENT_NAME'
          value: azureOpenaiModelDeploymentName
        }
        {
          name: 'FUNCTIONS_WORKER_PROCESS_COUNT'
          value: '1'
        }
        {
          name: 'WEBSITE_MAX_DYNAMIC_APPLICATION_SCALE_OUT'
          value: '1'
        }
      ]
    }
  }
}
output resourceGroup string = resourceGroup().name
output functionAppEndpoint string = functionApp.properties.defaultHostName
output functionAppName string = functionApp.name
output storageAccountName string = storageAccount.name
output containerName string = blobContainer.name
output storageAccountKey string = listKeys(storageAccount.id, storageAccount.apiVersion).keys[0].value
