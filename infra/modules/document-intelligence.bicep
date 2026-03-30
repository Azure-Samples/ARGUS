// Document Intelligence (Form Recognizer) with private endpoint and local auth disabled
param location string
param documentIntelligenceName string
param tags object
param privateEndpointsSubnetId string
param privateDnsZoneCognitiveServicesId string

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: documentIntelligenceName
  location: location
  sku: {
    name: 'S0'
  }
  kind: 'FormRecognizer'
  properties: {
    apiProperties: {}
    customSubDomainName: documentIntelligenceName
    publicNetworkAccess: 'Disabled'
    disableLocalAuth: true
    networkAcls: {
      defaultAction: 'Deny'
    }
  }
  tags: tags
}

resource docIntelPrivateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-docintel-${documentIntelligenceName}'
  location: location
  properties: {
    subnet: {
      id: privateEndpointsSubnetId
    }
    privateLinkServiceConnections: [
      {
        name: 'docintel-connection'
        properties: {
          privateLinkServiceId: documentIntelligence.id
          groupIds: ['account']
        }
      }
    ]
  }
  tags: tags
}

resource docIntelDnsGroup 'Microsoft.Network/privateEndpoints/privateDnsZoneGroups@2023-11-01' = {
  parent: docIntelPrivateEndpoint
  name: 'default'
  properties: {
    privateDnsZoneConfigs: [
      {
        name: 'config'
        properties: {
          privateDnsZoneId: privateDnsZoneCognitiveServicesId
        }
      }
    ]
  }
}

output documentIntelligenceId string = documentIntelligence.id
output documentIntelligenceEndpoint string = documentIntelligence.properties.endpoint
output documentIntelligenceName string = documentIntelligence.name
