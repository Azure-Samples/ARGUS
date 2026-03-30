// User Assigned Managed Identity
param location string
param resourceToken string
param tags object

resource userManagedIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'id-${resourceToken}'
  location: location
  tags: tags
}

output identityId string = userManagedIdentity.id
output identityPrincipalId string = userManagedIdentity.properties.principalId
output identityClientId string = userManagedIdentity.properties.clientId
output identityName string = userManagedIdentity.name
