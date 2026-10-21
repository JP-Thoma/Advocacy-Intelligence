// Azure AI Search: derived, rebuildable retrieval index over the records in Blob (D10, D37).
// Keyless like the rest: API keys are disabled, the developer identity gets roles.
//
// COST: Basic bills a fixed amount for every hour the service exists, whether or not it is used.
// Check the price shown in the portal, raise the budget first (see docs/thursday-plan.md), and delete
// the resource group after the demo.

param location string
param tags object
param principalId string

var suffix = uniqueString(resourceGroup().id)
var searchName = 'srch-advocacy-${suffix}' // lowercase letters, digits, hyphens; becomes the endpoint name

// Built-in role definition IDs (verified with: az role definition list --name "<role name>")
var searchServiceContributor = '7ca78c08-252a-4471-8644-bb5ff32d4ba0' // create and change indexes
var searchIndexDataContributor = '8ebe5a00-799e-43f5-93ac-243d3dce84a7' // load, read and query documents

resource search 'Microsoft.Search/searchServices@2023-11-01' = {
  name: searchName
  location: location
  tags: tags
  sku: {
    name: 'basic' // vector and hybrid search work from Basic up; 'free' allows only one per subscription and is too small to rely on
  }
  properties: {
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'default'
    publicNetworkAccess: 'enabled' // POC; private endpoints belong to the Phase 8 redesign
    disableLocalAuth: true // API keys disabled; Entra tokens only
    semanticSearch: 'disabled' // the semantic ranker is a separate paid feature and is cut from the demo scope
  }
}

resource serviceRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, principalId, searchServiceContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchServiceContributor)
    principalId: principalId
    principalType: 'User'
  }
}

resource dataRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: search
  name: guid(search.id, principalId, searchIndexDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', searchIndexDataContributor)
    principalId: principalId
    principalType: 'User'
  }
}

output searchName string = search.name
output searchEndpoint string = 'https://${search.name}.search.windows.net'
