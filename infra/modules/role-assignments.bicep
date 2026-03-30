// RBAC role assignments — tightened, scoped to individual resources
param userManagedIdentityPrincipalId string
param azurePrincipalId string

// Resource IDs for scoping
param containerRegistryId string
param storageAccountId string
param cosmosAccountId string
param documentIntelligenceId string
param aiServicesId string
param keyVaultId string
param cosmosAccountName string

// ─── ACR Pull (scoped to ACR) ───
resource acrPullRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(containerRegistryId, userManagedIdentityPrincipalId, 'AcrPull')
  scope: containerRegistry
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Storage Blob Data Contributor (scoped to Storage Account) ───
resource storageBlobContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userManagedIdentityPrincipalId, storageAccountId, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Cosmos DB Data Contributor (scoped to Cosmos Account) ───
resource cosmosDBDataContributorRoleDefinition 'Microsoft.DocumentDB/databaseAccounts/sqlRoleDefinitions@2024-05-15' existing = {
  parent: cosmosDbAccount
  name: '00000000-0000-0000-0000-000000000002'
}

resource cosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosAccountId, userManagedIdentityPrincipalId, cosmosDBDataContributorRoleDefinition.id)
  properties: {
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    principalId: userManagedIdentityPrincipalId
    scope: cosmosAccountId
  }
}

// ─── Cognitive Services User for Document Intelligence (scoped) ───
resource docIntelUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userManagedIdentityPrincipalId, documentIntelligenceId, 'CognitiveServicesUser')
  scope: documentIntelligence
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'a97b65f3-24c7-4388-baec-2e87135dc908')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Cognitive Services OpenAI User for AI Services (scoped) ───
resource aiServicesUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userManagedIdentityPrincipalId, aiServicesId, 'CognitiveServicesOpenAIUser')
  scope: aiServicesResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Key Vault Secrets User (scoped to Key Vault) ───
resource kvSecretsUserRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userManagedIdentityPrincipalId, keyVaultId, 'KeyVaultSecretsUser')
  scope: keyVaultResource
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── Logic App Contributor (scoped to RG — required for Logic App management) ───
resource logicAppContributorRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(userManagedIdentityPrincipalId, resourceGroup().id, 'LogicAppContributor')
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '87a39d53-fc1b-424a-814c-f7e04687dc9e')
    principalId: userManagedIdentityPrincipalId
    principalType: 'ServicePrincipal'
  }
}

// ─── User dev access: Cosmos DB ───
resource userCosmosDBRoleAssignment 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosDbAccount
  name: guid(cosmosAccountId, azurePrincipalId, 'UserCosmosContributor')
  properties: {
    principalId: azurePrincipalId
    roleDefinitionId: cosmosDBDataContributorRoleDefinition.id
    scope: cosmosAccountId
  }
}

// ─── User dev access: Storage Blob Data Contributor ───
resource userStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageAccountId, azurePrincipalId, 'StorageBlobDataContributor')
  scope: storageAccount
  properties: {
    principalId: azurePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  }
}

// ─── User dev access: Key Vault Secrets Officer ───
resource userKvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultId, azurePrincipalId, 'KeyVaultSecretsOfficer')
  scope: keyVaultResource
  properties: {
    principalId: azurePrincipalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')
  }
}

// Existing resource references for scoping
resource containerRegistry 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: last(split(containerRegistryId, '/'))
}

resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: last(split(storageAccountId, '/'))
}

resource cosmosDbAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(documentIntelligenceId, '/'))
}

resource aiServicesResource 'Microsoft.CognitiveServices/accounts@2024-10-01' existing = {
  name: last(split(aiServicesId, '/'))
}

resource keyVaultResource 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultId, '/'))
}
