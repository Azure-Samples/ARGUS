// ARGUS Infrastructure — Modularized with VNet, Private Endpoints, Key Vault, RBAC
targetScope = 'resourceGroup'

// ─── Parameters ───
param location string = resourceGroup().location
param environmentName string
param containerAppName string = 'ca-${uniqueString(resourceGroup().id)}'
param frontendContainerAppName string = 'ca-frontend-${uniqueString(resourceGroup().id)}'
param resourceToken string = uniqueString(subscription().id, resourceGroup().id, environmentName)

param storageAccountName string = 'sa${resourceToken}'
param cosmosDbAccountName string = 'cb${resourceToken}'
param cosmosDbDatabaseName string = 'doc-extracts'
param cosmosDbContainerName string = 'documents'
param containerRegistryName string = 'cr${resourceToken}'
param documentIntelligenceName string = 'di${resourceToken}'
param azureOpenaiModelDeploymentName string

@description('Principal ID of the running user for role assignments')
param azurePrincipalId string

// ─── Tags ───
var commonTags = {
  solution: 'ARGUS-1.0'
  environment: environmentName
  'azd-env-name': environmentName
}
var serviceResourceTags = union(commonTags, { 'azd-service-name': 'backend' })

// ═══════════════════════════════════════════════════
// Module: Networking (VNet, subnets, private DNS zones)
// ═══════════════════════════════════════════════════
module network 'modules/network.bicep' = {
  name: 'network'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
  }
}

// ═══════════════════════════════════════════════════
// Module: Managed Identity
// ═══════════════════════════════════════════════════
module identity 'modules/identity.bicep' = {
  name: 'identity'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
  }
}

// ═══════════════════════════════════════════════════
// Module: Monitoring (Log Analytics + App Insights)
// ═══════════════════════════════════════════════════
module monitoring 'modules/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
  }
}

// ═══════════════════════════════════════════════════
// Module: Key Vault (with private endpoint, RBAC)
// ═══════════════════════════════════════════════════
module keyVault 'modules/key-vault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneKeyVaultId: network.outputs.privateDnsZoneKeyVaultId
  }
}

// ═══════════════════════════════════════════════════
// Module: Storage Account (private endpoint, no shared key)
// ═══════════════════════════════════════════════════
module storage 'modules/storage.bicep' = {
  name: 'storage'
  params: {
    location: location
    storageAccountName: storageAccountName
    tags: commonTags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneBlobId: network.outputs.privateDnsZoneBlobId
  }
}

// ═══════════════════════════════════════════════════
// Module: Cosmos DB (private endpoint, local auth disabled)
// ═══════════════════════════════════════════════════
module cosmos 'modules/cosmos.bicep' = {
  name: 'cosmos'
  params: {
    location: location
    cosmosDbAccountName: cosmosDbAccountName
    cosmosDbDatabaseName: cosmosDbDatabaseName
    cosmosDbContainerName: cosmosDbContainerName
    tags: commonTags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneCosmosId: network.outputs.privateDnsZoneCosmosId
  }
}

// ═══════════════════════════════════════════════════
// Module: Document Intelligence (private endpoint, local auth disabled)
// ═══════════════════════════════════════════════════
module docIntel 'modules/document-intelligence.bicep' = {
  name: 'docIntel'
  params: {
    location: location
    documentIntelligenceName: documentIntelligenceName
    tags: commonTags
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneCognitiveServicesId: network.outputs.privateDnsZoneCognitiveServicesId
  }
}

// ═══════════════════════════════════════════════════
// Module: Azure AI Services / OpenAI (private endpoint, managed identity)
// ═══════════════════════════════════════════════════
module aiServices 'modules/ai-services.bicep' = {
  name: 'aiServices'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
    azureOpenaiModelDeploymentName: azureOpenaiModelDeploymentName
    privateEndpointsSubnetId: network.outputs.privateEndpointsSubnetId
    privateDnsZoneOpenAIId: network.outputs.privateDnsZoneOpenAIId
  }
}

// ═══════════════════════════════════════════════════
// Module: Container Registry (Basic, managed identity pull)
// ═══════════════════════════════════════════════════
module acr 'modules/container-registry.bicep' = {
  name: 'acr'
  params: {
    location: location
    containerRegistryName: containerRegistryName
    tags: commonTags
  }
}

// ═══════════════════════════════════════════════════
// Module: Container Apps (Backend + Frontend)
// ═══════════════════════════════════════════════════
module containerApps 'modules/container-apps.bicep' = {
  name: 'containerApps'
  params: {
    location: location
    resourceToken: resourceToken
    containerAppName: containerAppName
    frontendContainerAppName: frontendContainerAppName
    tags: commonTags
    serviceResourceTags: serviceResourceTags
    logAnalyticsCustomerId: monitoring.outputs.logAnalyticsCustomerId
    logAnalyticsSharedKey: monitoring.outputs.logAnalyticsSharedKey
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
    userManagedIdentityId: identity.outputs.identityId
    userManagedIdentityClientId: identity.outputs.identityClientId
    containerRegistryLoginServer: acr.outputs.registryLoginServer
    storageAccountName: storage.outputs.storageAccountName
    blobEndpoint: storage.outputs.blobEndpoint
    containerName: storage.outputs.containerName
    cosmosEndpoint: cosmos.outputs.cosmosEndpoint
    cosmosDatabaseName: cosmos.outputs.cosmosDatabaseName
    cosmosContainerName: cosmos.outputs.cosmosContainerName
    cosmosConfigContainerName: cosmos.outputs.cosmosConfigContainerName
    documentIntelligenceEndpoint: docIntel.outputs.documentIntelligenceEndpoint
    aiServicesEndpoint: aiServices.outputs.aiServicesEndpoint
    azureOpenaiModelDeploymentName: azureOpenaiModelDeploymentName
    keyVaultUri: keyVault.outputs.keyVaultUri
    containerAppsSubnetId: network.outputs.containerAppsSubnetId
  }
}

// ═══════════════════════════════════════════════════
// Module: RBAC Role Assignments (tightened, resource-scoped)
// ═══════════════════════════════════════════════════
module roleAssignments 'modules/role-assignments.bicep' = {
  name: 'roleAssignments'
  params: {
    userManagedIdentityPrincipalId: identity.outputs.identityPrincipalId
    azurePrincipalId: azurePrincipalId
    containerRegistryId: acr.outputs.registryId
    storageAccountId: storage.outputs.storageAccountId
    cosmosAccountId: cosmos.outputs.cosmosAccountId
    cosmosAccountName: cosmosDbAccountName
    documentIntelligenceId: docIntel.outputs.documentIntelligenceId
    aiServicesId: aiServices.outputs.aiServicesId
    keyVaultId: keyVault.outputs.keyVaultId
  }
}

// ═══════════════════════════════════════════════════
// Module: Event Processing (Event Grid + Logic App)
// ═══════════════════════════════════════════════════
module eventProcessing 'modules/event-processing.bicep' = {
  name: 'eventProcessing'
  params: {
    location: location
    resourceToken: resourceToken
    tags: commonTags
    containerAppFqdn: containerApps.outputs.containerAppFqdn
    storageAccountId: storage.outputs.storageAccountId
    storageAccountName: storage.outputs.storageAccountName
  }
}

// ═══════════════════════════════════════════════════
// Outputs
// ═══════════════════════════════════════════════════
output resourceGroupName string = resourceGroup().name
output RESOURCE_GROUP_ID string = resourceGroup().id
output containerAppName string = containerApps.outputs.containerAppName
output containerAppFqdn string = containerApps.outputs.containerAppFqdn
output BACKEND_URL string = 'https://${containerApps.outputs.containerAppFqdn}'
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.registryLoginServer
output containerRegistryName string = acr.outputs.registryName
output containerRegistryLoginServer string = acr.outputs.registryLoginServer
output storageAccountName string = storage.outputs.storageAccountName
output containerName string = storage.outputs.containerName
output userManagedIdentityClientId string = identity.outputs.identityClientId
output userManagedIdentityPrincipalId string = identity.outputs.identityPrincipalId

output BLOB_ACCOUNT_URL string = storage.outputs.blobEndpoint
output CONTAINER_NAME string = storage.outputs.containerName
output COSMOS_URL string = cosmos.outputs.cosmosEndpoint
output COSMOS_DB_NAME string = cosmos.outputs.cosmosDatabaseName
output COSMOS_DOCUMENTS_CONTAINER_NAME string = cosmos.outputs.cosmosContainerName
output COSMOS_CONFIG_CONTAINER_NAME string = cosmos.outputs.cosmosConfigContainerName
output DOCUMENT_INTELLIGENCE_ENDPOINT string = docIntel.outputs.documentIntelligenceEndpoint
output AZURE_OPENAI_ENDPOINT string = aiServices.outputs.aiServicesEndpoint
output AZURE_OPENAI_MODEL_DEPLOYMENT_NAME string = azureOpenaiModelDeploymentName
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output AZURE_KEY_VAULT_URI string = keyVault.outputs.keyVaultUri

output logicAppName string = eventProcessing.outputs.logicAppName
output frontendContainerAppName string = containerApps.outputs.frontendAppName
output frontendContainerAppFqdn string = containerApps.outputs.frontendAppFqdn
output FRONTEND_URL string = 'https://${containerApps.outputs.frontendAppFqdn}'
