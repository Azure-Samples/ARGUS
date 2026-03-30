// Logic App + Event Grid for blob-triggered file processing
param location string
param resourceToken string
param tags object
param containerAppFqdn string
param storageAccountId string
param storageAccountName string

resource eventGridSystemTopic 'Microsoft.EventGrid/systemTopics@2022-06-15' = {
  name: 'st-${resourceToken}'
  location: location
  properties: {
    source: storageAccountId
    topicType: 'Microsoft.Storage.StorageAccounts'
  }
  tags: tags
}

resource logicApp 'Microsoft.Logic/workflows@2019-05-01' = {
  name: 'logic-argus-v2-${resourceToken}'
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    state: 'Enabled'
    definition: {
      '$schema': 'https://schema.management.azure.com/providers/Microsoft.Logic/schemas/2016-06-01/workflowdefinition.json#'
      contentVersion: '1.0.0.0'
      parameters: {
        backendUrl: {
          type: 'string'
          defaultValue: 'https://${containerAppFqdn}'
        }
      }
      triggers: {
        When_a_blob_is_created: {
          type: 'Request'
          kind: 'Http'
          inputs: {
            schema: {
              type: 'array'
              items: {
                type: 'object'
                properties: {
                  topic: { type: 'string' }
                  subject: { type: 'string' }
                  eventType: { type: 'string' }
                  eventTime: { type: 'string' }
                  id: { type: 'string' }
                  data: {
                    type: 'object'
                    properties: {
                      api: { type: 'string' }
                      requestId: { type: 'string' }
                      eTag: { type: 'string' }
                      contentType: { type: 'string' }
                      contentLength: { type: 'integer' }
                      blobType: { type: 'string' }
                      url: { type: 'string' }
                      sequencer: { type: 'string' }
                      storageDiagnostics: { type: 'object' }
                    }
                  }
                  dataVersion: { type: 'string' }
                  metadataVersion: { type: 'string' }
                }
              }
            }
          }
          runtimeConfiguration: {
            concurrency: {
              runs: 5
            }
          }
        }
      }
      actions: {
        Check_If_File_In_Datasets_Subdirectory: {
          type: 'If'
          expression: {
            and: [
              {
                contains: [
                  '@triggerBody()[0]?[\'subject\']'
                  '/blobServices/default/containers/datasets/blobs/'
                ]
              }
              {
                greater: [
                  '@length(split(replace(triggerBody()[0]?[\'subject\'], \'/blobServices/default/containers/datasets/blobs/\', \'\'), \'/\'))'
                  1
                ]
              }
            ]
          }
          actions: {
            HTTP_Call_Backend: {
              type: 'Http'
              inputs: {
                method: 'POST'
                uri: '@concat(parameters(\'backendUrl\'), \'/api/process-file\')'
                headers: {
                  'Content-Type': 'application/json'
                }
                body: {
                  filename: '@last(split(replace(triggerBody()[0]?[\'subject\'], \'/blobServices/default/containers/datasets/blobs/\', \'\'), \'/\'))'
                  dataset: '@first(split(replace(triggerBody()[0]?[\'subject\'], \'/blobServices/default/containers/datasets/blobs/\', \'\'), \'/\'))'
                  blob_path: '@concat(\'/datasets/\', replace(triggerBody()[0]?[\'subject\'], \'/blobServices/default/containers/datasets/blobs/\', \'\'))'
                  trigger_source: 'blob_upload'
                }
              }
            }
          }
          else: {
            actions: {}
          }
          runAfter: {}
        }
      }
      outputs: {}
    }
  }
  tags: tags
}

resource logicAppEventSubscription 'Microsoft.EventGrid/systemTopics/eventSubscriptions@2022-06-15' = {
  parent: eventGridSystemTopic
  name: 'logic-app-blob-subscription'
  properties: {
    destination: {
      endpointType: 'WebHook'
      properties: {
        endpointUrl: '${listCallbackUrl(resourceId('Microsoft.Logic/workflows/triggers', logicApp.name, 'When_a_blob_is_created'), '2019-05-01').value}'
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

// Storage Blob Data Reader for Logic App
resource logicAppStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(logicApp.id, storageAccountId, 'StorageBlobDataReader')
  scope: storageAccountRef
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '2a2b9908-6ea1-4ae2-8e65-a410df84e7d1')
    principalId: logicApp.identity.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storageAccountRef 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

output logicAppName string = logicApp.name
