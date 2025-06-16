// Container App version of the ARGUS infrastructure with private ACR
targetScope = 'resourceGroup'

// Parameters
param location string = resourceGroup().location
param environmentName string
param containerAppName string = 'ca-${uniqueString(resourceGroup().id)}'
param resourceToken string = uniqueString(subscription().id, resourceGroup().id, environmentName)

// Storage and Database parameters
param storageAccountName string = 'sa${resourceToken}'
param cosmosDbAccountName string = 'cb${resourceToken}'
param cosmosDbDatabaseName string = 'doc-extracts'
param cosmosDbContainerName string = 'documents'

// Container Registry parameters
param containerRegistryName string = 'cr${resourceToken}'

// Document Intelligence resource name
param documentIntelligenceName string = 'di${resourceToken}'

@description('Principal ID of the running user for role assignments')
param azurePrincipalId string

// Azure OpenAI parameters
@secure()
param azureOpenaiEndpoint string
@secure()
param azureOpenaiKey string
param azureOpenaiModelDeploymentName string

// Common tags
var commonTags = {
  solution: 'ARGUS-1.0'
  environment: environmentName
  'azd-service-name': containerAppName
  'azd-env-name': environmentName
}

// Container Registry
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: containerRegistryName
  location: location
  sku: {
    name: 'Basic'
  }
  properties: {
    adminUserEnabled: false
    publicNetworkAccess: 'Enabled'
  }
  tags: commonTags
}

// Log Analytics Workspace
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2021-06-01' = {
  name: 'law-${resourceToken}'
  location: location
  properties: {
    retentionInDays: 30
  }
  tags: commonTags
}

// Application Insights
resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: 'ai-${resourceToken}'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
  tags: commonTags
}

// Container Apps Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: 'cae-${resourceToken}'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalytics.properties.customerId
        sharedKey: logAnalytics.listKeys().primarySharedKey
      }
    }
  }
  tags: commonTags
}

// User Assigned Managed Identity for Container App
resource userManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceToken}'
  location: location
  tags: commonTags
}

// Storage Account
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

// Blob Service
resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2022-05-01' = {
  parent: storageAccount
  name: 'default'
}

// Blob Container
resource blobContainer 'Microsoft.Storage/storageAccounts/blobServices/containers@2022-05-01' = {
  parent: blobService
  name: 'datasets'
  properties: {
    publicAccess: 'None'
  }
}

// Cosmos DB Account
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

// Cosmos DB Database
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

// Cosmos DB Container for documents
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

// Cosmos DB Container for configuration
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

// Document Intelligence resource
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

// Container App
resource containerApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: containerAppName
  location: location
  identity: {
    type: 'SystemAssigned,UserAssigned'
    userAssignedIdentities: {
      '${userManagedIdentity.id}': {}
    }
  }
  properties: {
    environmentId: containerAppEnvironment.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        corsPolicy: {
          allowedOrigins: ['*']
          allowedMethods: ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
          allowedHeaders: ['*']
          allowCredentials: false
        }
      }
      registries: [
        {
          server: containerRegistry.properties.loginServer
          identity: userManagedIdentity.id
        }
      ]
      secrets: [
        {
          name: 'azure-openai-key'
          value: azureOpenaiKey
        }
        {
          name: 'appinsights-connection-string'
          value: applicationInsights.properties.ConnectionString
        }
      ]
    }
    template: {
      containers: [
        {
          name: containerAppName
          image: 'mcr.microsoft.com/azuredocs/containerapps-helloworld:latest'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
          env: [
            {
              name: 'STORAGE_ACCOUNT_NAME'
              value: storageAccount.name
            }
            {
              name: 'STORAGE_ACCOUNT_URL'
              value: storageAccount.properties.primaryEndpoints.blob
            }
            {
              name: 'CONTAINER_NAME'
              value: blobContainer.name
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
              secretRef: 'azure-openai-key'
            }
            {
              name: 'AZURE_OPENAI_MODEL_DEPLOYMENT_NAME'
              value: azureOpenaiModelDeploymentName
            }
            {
              name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
              secretRef: 'appinsights-connection-string'
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: userManagedIdentity.properties.clientId
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
        rules: [
          {
            name: 'http-rule'
            http: {
              metadata: {
                concurrentRequests: '10'
              }
            }
          }
        ]
      }
    }
  }
  tags: commonTags
}

// Role assignments for User Managed Identity - ACR Pull
resource acrPullRoleAssignment 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(containerRegistry.id, userManagedIdentity.id, 'AcrPull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d') // AcrPull
    principalId: userManagedIdentity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role assignments for Container App System Identity - Storage Blob Data Contributor
resource containerAppStorageBlobDataContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(containerApp.id, storageAccount.id, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Role assignments for Container App System Identity - Storage Blob Data Owner
resource containerAppStorageBlobDataOwnerRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(containerApp.id, storageAccount.id, 'StorageBlobDataOwner')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b7e6dc6d-f1e8-4753-8033-0f276bb0955b') // Storage Blob Data Owner
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// Cosmos DB role assignment for Container App System Identity
resource cosmosDBDataContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2021-04-15' existing = {
  parent: cosmosDbAccount
  name: '00000000-0000-0000-0000-000000000002' // Built-in Data Contributor Role
}

resource cosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2021-04-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosDbAccount.id, containerApp.id, cosmosDBDataContributorRoleDefinition.id)
  properties: {
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    principalId: containerApp.identity.principalId
    scope: cosmosDbAccount.id
  }
}

// Document Intelligence role assignment for Container App System Identity
resource containerAppDocumentIntelligenceContributorRole 'Microsoft.Authorization/roleAssignments@2020-04-01-preview' = {
  name: guid(containerApp.id, documentIntelligence.id, 'CognitiveServicesUser')
  scope: documentIntelligence
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908') // Cognitive Services User
    principalId: containerApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

// User role assignments (for development access)
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
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe') // Storage Blob Data Contributor
  }
}

// Event Grid System Topic for Storage Account
resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: 'st-${resourceToken}'
  location: location
  properties: {
    source: storageAccount.id
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
  tags: commonTags
}

// Event Grid Subscription for blob created events
resource blobCreatedEventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: eventGridSystemTopic
  name: 'blob-created-subscription'
  properties: {
    destination: {
      endpointType: 'WebHook'
      properties: {
        endpointUrl: 'https://${containerApp.properties.configuration.ingress.fqdn}/api/blob-created'
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
      ]
      subjectBeginsWith: '/blobServices/default/containers/datasets/'
      enableAdvancedFilteringOnArrays: false
    }
    eventDeliverySchema: 'EventGridSchema'
    retryPolicy: {
      maxDeliveryAttempts: 3
      eventTimeToLiveInMinutes: 1440
    }
  }
}

// Outputs
output resourceGroupName string = resourceGroup().name
output RESOURCE_GROUP_ID string = resourceGroup().id
output containerAppName string = containerApp.name
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output containerRegistryName string = containerRegistry.name
output containerRegistryLoginServer string = containerRegistry.properties.loginServer
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = 'https://${containerRegistry.properties.loginServer}'
output storageAccountName string = storageAccount.name
output containerName string = blobContainer.name
output userManagedIdentityClientId string = userManagedIdentity.properties.clientId
output userManagedIdentityPrincipalId string = userManagedIdentity.properties.principalId

// Environment variables for the application
output BLOB_ACCOUNT_URL string = storageAccount.properties.primaryEndpoints.blob
output CONTAINER_NAME string = blobContainer.name
output COSMOS_URL string = cosmosDbAccount.properties.documentEndpoint
output COSMOS_DB_NAME string = cosmosDbDatabase.name
output COSMOS_DOCUMENTS_CONTAINER_NAME string = cosmosDbContainer.name
output COSMOS_CONFIG_CONTAINER_NAME string = cosmosDbContainerConf.name
output DOCUMENT_INTELLIGENCE_ENDPOINT string = documentIntelligence.properties.endpoint
output AZURE_OPENAI_MODEL_DEPLOYMENT_NAME string = azureOpenaiModelDeploymentName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = applicationInsights.properties.ConnectionString
