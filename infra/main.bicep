// Define the resource group location
param location string

// Define the storage account name
param storageAccountName string = 'sa${uniqueString(resourceGroup().id)}'

// Define the container registry name
param containerRegistryName string = 'acr${uniqueString(resourceGroup().id)}'

// Define the Cosmos DB account name
param cosmosDbAccountName string = 'cb${uniqueString(resourceGroup().id)}'

// Define the Cosmos DB database name
param cosmosDbDatabaseName string = 'doc-extracts'

// Define the Cosmos DB container name
param cosmosDbContainerName string = 'documents'

// Define the function app name
param functionAppName string = 'fa${uniqueString(resourceGroup().id)}'

param appServicePlanName string = '${functionAppName}-plan'

// Define the Document Intelligence resource name
param documentIntelligenceName string = 'di${uniqueString(resourceGroup().id)}'

@description('Principal ID of the running user for role assignments')
param azurePrincipalId string

// Define the Azure OpenAI parameters
@secure()
param azureOpenaiEndpoint string
@secure()
param azureOpenaiKey string
param azureOpenaiModelDeploymentName string

// Define common tags  
var commonTags = {  
  solution: 'ARGUS-1.0'    
}

// Define the Azure Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: true
  }
  tags: commonTags
}

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
  tags: commonTags
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
  tags: commonTags
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
  tags: commonTags
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
  tags: commonTags
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
  tags: commonTags
}





resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {  
  name: 'logAnalyticsWorkspace'  
  location: location  
  properties: {  
    retentionInDays: 30  
  }  
  tags: {  
    solution: 'ARGUS-1.0'  
  }  
}  

// Define the Application Insights resource
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'app-insights'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
  tags: commonTags
}

// Define the App Service Plan
resource appServicePlan 'Microsoft.Web/serverfarms@2021-03-01' = {
  name: appServicePlanName
  location: location
  kind: 'Linux'
  sku: {
    name: 'B1'
    tier: 'Basic'
  }
  properties: {
    reserved: true
  }
  tags: commonTags
}

// Define the Document Intelligence resource
resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2021-04-30' = {
  name: documentIntelligenceName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  properties: {
    apiProperties: {}
    customSubDomainName: documentIntelligenceName
    publicNetworkAccess: 'Enabled'
  }
  tags: commonTags
}

// Define the Function App
resource functionApp 'Microsoft.Web/sites@2021-03-01' = {
  name: functionAppName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  kind: 'functionapp'
  tags: commonTags
  properties: {
    serverFarmId: appServicePlan.id
    httpsOnly: true
    siteConfig: {
      pythonVersion: '3.11'
      linuxFxVersion: 'DOCKER|${containerRegistry.properties.loginServer}/argus-backend:latest'
      alwaysOn: true
      appSettings: [
        {          name: 'AzureWebJobsStorage__credential'
          value: 'managedidentity'
        }
        {
          name: 'AzureWebJobsStorage__serviceUri'
          value: 'https://${storageAccount.name}.blob.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__blobServiceUri'
          value: 'https://${storageAccount.name}.blob.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__queueServiceUri'
          value: 'https://${storageAccount.name}.queue.${environment().suffixes.storage}'
        }
        {
          name: 'AzureWebJobsStorage__tableServiceUri'
          value: 'https://${storageAccount.name}.table.${environment().suffixes.storage}'
        }
        {
          name: 'WEBSITES_ENABLE_APP_SERVICE_STORAGE'
          value: 'false'
        }
        {
          name: 'FUNCTIONS_EXTENSION_VERSION'
          value: '~4'
        }
        {          name: 'APPINSIGHTS_INSTRUMENTATIONKEY'
          value: applicationInsights.properties.InstrumentationKey
        }
        {
          name: 'FUNCTIONS_WORKER_RUNTIME'
          value: 'python'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_URL'
          value: 'https://${containerRegistry.properties.loginServer}'
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_USERNAME'
          value: containerRegistry.name
        }
        {
          name: 'DOCKER_REGISTRY_SERVER_PASSWORD'
          value: containerRegistry.listCredentials().passwords[0].value
        }
        {
          name: 'COSMOS_DB_ENDPOINT'
          value: cosmosDbAccount.properties.documentEndpoint
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

// Role assignments for the Function App's managed identity
resource functionAppStorageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageBlobDataOwnerRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b') // Storage Blob Data Owner
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageQueueDataContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageQueueDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '974c5e8b-45b9-4653-ba55-5f855dd0fb88') // Storage Queue Data Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppStorageAccountContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, storageAccount.id, 'StorageAccountContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab') // Storage Account Contributor
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB role assignment
resource cosmosDBDataContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2021-04-15' existing = {
  parent: cosmosDbAccount
  name: '00000000-0000-0000-0000-000000000002' // Built-in Data Contributor Role
}

resource cosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosDbAccount.id, functionApp.id, cosmosDBDataContributorRoleDefinition.id)
  properties: {
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    principalId: functionApp.identity.principalId
    scope: cosmosDbAccount.id
  }
}

resource functionAppDocumentIntelligenceContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, documentIntelligence.id, 'CognitiveServicesUser')
  scope: documentIntelligence
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource functionAppAcrPullRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(functionApp.id, containerRegistry.id, 'AcrPull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalId: functionApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

param roleDefinitionId string = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe' //Default as Storage Blob Data Contributor role
 
var logicAppDefinition = json(loadTextContent('logic_app.json'))
 
resource blobConnection 'Microsoft.Web/connections@2018-07-01-preview' = {
  name: 'azureblob'
  location: location
  kind: 'V1'
  properties: {
    alternativeParameterValues: {}
    api: {
      id: 'subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${location}/managedApis/azureblob'
    }
    customParameterValues: {}
    displayName: 'azureblob'
    parameterValueSet: {
      name: 'managedIdentityAuth'
      values: {}
    }
  }
  tags: commonTags
}
 
resource logicapp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logicAppName'
  location: location
  dependsOn: [
    blobConnection
  ]
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: 'Enabled'
    definition: logicAppDefinition.definition
    parameters: {
      '$connections': {
        value: {
            azureblob: {
                connectionId: '/subscriptions/${subscription().subscriptionId}/resourceGroups/${resourceGroup().name}/providers/Microsoft.Web/connections/azureblob'
                connectionName: 'azureblob'
                connectionProperties: {
                    authentication: {
                        type: 'ManagedServiceIdentity'
                    }
                }
                id: '/subscriptions/${subscription().subscriptionId}/providers/Microsoft.Web/locations/${location}/managedApis/azureblob'            }
        }
      }
      storageAccount: {
        value: storageAccountName
      }
    }
  }
  tags: commonTags
}
 
// resource logicAppStorageAccountRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-10-01-preview' = {
//   scope: storageAccount
//   name: roleAssignmentName
//   properties: {
//     principalType: 'ServicePrincipal'
//     roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
//     principalId: logicapp.identity.principalId
//   }
// }

resource userCosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  name: guid(cosmosDbAccount.id, cosmosDbDatabase.id, cosmosDbContainer.id, azurePrincipalId)
  parent: cosmosDbAccount
  properties: {
    principalId: azurePrincipalId
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    scope: cosmosDbAccount.id
  }
}

resource userStorageAccountRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccount.id, azurePrincipalId, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    principalId: azurePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}

// TODO: could we remove some of those outputs?
output resourceGroup string = resourceGroup().name
output functionAppEndpoint string = functionApp.properties.defaultHostName
output functionAppName string = functionApp.name
output storageAccountName string = storageAccount.name
output containerName string = blobContainer.name

output BLOB_ACCOUNT_URL string = storageAccount.properties.primaryEndpoints.blob
output CONTAINER_NAME string = blobContainer.name
output COSMOS_URL string = cosmosDbAccount.properties.documentEndpoint
output COSMOS_DB_NAME string = cosmosDbDatabase.name
output COSMOS_DOCUMENTS_CONTAINER_NAME string = cosmosDbContainer.name
output COSMOS_CONFIG_CONTAINER_NAME string = cosmosDbContainerConf.name
output CONTAINER_REGISTRY_LOGIN_SERVER string = containerRegistry.properties.loginServer
output CONTAINER_REGISTRY_NAME string = containerRegistry.name
