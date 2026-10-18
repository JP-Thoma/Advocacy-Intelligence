// Resources inside rg-advocacy-poc. Keyless by design: no shared keys, no API keys.
// Deployments are named by ROLE ('chat', 'embedding'), not by model, so a model swap is a one-line change here.

param location string
param tags object
param principalId string
param chatCapacity int
param embeddingCapacity int

// Model settings are parameters because availability changes: a model can be listed, have quota, and still be
// deprecated (no new deployments). Check offered + not deprecated + quota before choosing.
param chatModelName string
param chatModelVersion string
@allowed(['Standard', 'DataZoneStandard', 'GlobalStandard'])
param chatSkuName string
param embeddingModelName string
param embeddingModelVersion string
@allowed(['Standard', 'DataZoneStandard', 'GlobalStandard'])
param embeddingSkuName string

var suffix = uniqueString(resourceGroup().id)
var storageName = 'stadvocacy${suffix}' // 3-24 chars, lowercase letters and digits, globally unique
var openAiName = 'oai-advocacy-${suffix}' // also the custom subdomain, required for Entra token auth

// Built-in role definition IDs (verify with: az role definition list --name "<role name>")
var storageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var cognitiveServicesOpenAiUser = '5e0bd9bd-7b93-4f28-af87-19fc36ad61bd'

// ---------- Storage: system of record (D10) ----------

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS' // cheapest redundancy; a POC does not need zone or geo redundancy
  }
  properties: {
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
    allowBlobPublicAccess: false
    allowSharedKeyAccess: false // Entra ID only; no account keys can be used
    defaultToOAuthAuthentication: true
    accessTier: 'Hot'
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    deleteRetentionPolicy: {
      enabled: true
      days: 7
    }
    containerDeleteRetentionPolicy: {
      enabled: true
      days: 7
    }
  }
}

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [
  for name in ['raw', 'records']: {
    parent: blobService
    name: name
    properties: {
      publicAccess: 'None'
    }
  }
]

// ---------- Azure OpenAI ----------

resource openAi 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: openAiName
  location: location
  tags: tags
  kind: 'OpenAI'
  sku: {
    name: 'S0'
  }
  properties: {
    customSubDomainName: openAiName
    publicNetworkAccess: 'Enabled' // POC; private endpoints are part of the Phase 8 redesign
    disableLocalAuth: true // API keys disabled; Entra tokens only
  }
}

// Chat model: see decision log (D33 was invalidated by deprecation; the replacement is chosen at deploy time).
resource chat 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'chat'
  sku: {
    name: chatSkuName
    capacity: chatCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: chatModelName
      version: chatModelVersion
    }
  }
}

// Embedding model (D34). Deployments on one account must be created one at a time.
resource embedding 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: openAi
  name: 'embedding'
  dependsOn: [
    chat
  ]
  sku: {
    name: embeddingSkuName
    capacity: embeddingCapacity
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: embeddingModelName
      version: embeddingModelVersion
    }
  }
}

// ---------- Keyless access for the developer identity ----------

resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: storage
  name: guid(storage.id, principalId, storageBlobDataContributor)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', storageBlobDataContributor)
    principalId: principalId
    principalType: 'User'
  }
}

resource openAiRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  scope: openAi
  name: guid(openAi.id, principalId, cognitiveServicesOpenAiUser)
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', cognitiveServicesOpenAiUser)
    principalId: principalId
    principalType: 'User'
  }
}

output storageAccountName string = storage.name
output storageBlobEndpoint string = storage.properties.primaryEndpoints.blob
output openAiEndpoint string = openAi.properties.endpoint
output chatDeployment string = chat.name
output embeddingDeployment string = embedding.name
