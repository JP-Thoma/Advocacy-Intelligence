// M3 foundation: resource group + Storage + Azure OpenAI, keyless, EU region.
// Deploy:  az deployment sub create --location swedencentral --template-file infra/main.bicep --parameters principalId=<object id>
// Tear down: az group delete --name rg-advocacy-poc
targetScope = 'subscription'

@description('Azure region for all resources (EU, decision D30).')
param location string = 'swedencentral'

@description('Object ID of the signed-in user who gets data-plane roles: az ad signed-in-user show --query id -o tsv')
param principalId string

@description('Chat deployment capacity in thousands of tokens per minute. Low on purpose: it caps worst-case spend. Worst case per day = capacity x 1000 x 1440 x price per token; recompute when the model changes.')
@minValue(1)
param chatCapacity int = 10

@description('Embedding deployment capacity in thousands of tokens per minute.')
@minValue(1)
param embeddingCapacity int = 20

@description('Chat model name. No default on purpose: check offered, not deprecated, and quota first.')
param chatModelName string

@description('Chat model version.')
param chatModelVersion string

@description('Chat deployment type: Standard (regional), DataZoneStandard (EU zone) or GlobalStandard.')
@allowed(['Standard', 'DataZoneStandard', 'GlobalStandard'])
param chatSkuName string

param embeddingModelName string = 'text-embedding-3-large'
param embeddingModelVersion string = '1'
@allowed(['Standard', 'DataZoneStandard', 'GlobalStandard'])
param embeddingSkuName string = 'Standard'

@description('Create Azure AI Search (Basic, fixed hourly cost while it exists). Off by default: turn on deliberately, after raising the budget (see docs/delivery-plan.md).')
param deploySearch bool = false

var resourceGroupName = 'rg-advocacy-poc'
var tags = {
  project: 'advocacy-intelligence'
  purpose: 'poc'
  'delete-after': 'demo'
}

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: resourceGroupName
  location: location
  tags: tags
}

module foundation 'modules/foundation.bicep' = {
  name: 'foundation'
  scope: rg
  params: {
    location: location
    tags: tags
    principalId: principalId
    chatCapacity: chatCapacity
    embeddingCapacity: embeddingCapacity
    chatModelName: chatModelName
    chatModelVersion: chatModelVersion
    chatSkuName: chatSkuName
    embeddingModelName: embeddingModelName
    embeddingModelVersion: embeddingModelVersion
    embeddingSkuName: embeddingSkuName
  }
}

module search 'modules/search.bicep' = if (deploySearch) {
  name: 'search'
  scope: rg
  params: {
    location: location
    tags: tags
    principalId: principalId
  }
}

output resourceGroupName string = rg.name
output storageAccountName string = foundation.outputs.storageAccountName
output storageBlobEndpoint string = foundation.outputs.storageBlobEndpoint
output openAiEndpoint string = foundation.outputs.openAiEndpoint
output chatDeployment string = foundation.outputs.chatDeployment
output embeddingDeployment string = foundation.outputs.embeddingDeployment
output searchEndpoint string = deploySearch ? search!.outputs.searchEndpoint : ''
