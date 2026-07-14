param location string = 'westus'
param suffix string = substring(uniqueString(resourceGroup().id), 0, 6)
param storageName string = 'stcentinela${suffix}'
param kvName string = 'kv-centinela-${suffix}'
param appInsightsName string = 'appi-centinela-${suffix}'
param funcApiName string = 'func-api-${suffix}'
param funcScoringName string = 'func-scoring-${suffix}'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
  }
}

resource tableTransacciones 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/transacciones'
  parent: storage
}

resource tableCasos 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/casos'
  parent: storage
}

resource tableConfig 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/configuracion'
  parent: storage
}

resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storageName}/default/transacciones-pendientes'
  parent: storage
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageName}/default/verificaciones'
  parent: storage
}

resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { name: 'standard', family: 'A' }
    enableRbacAuthorization: true
  }
}

resource kvSecretStorageConn 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: 'StorageConnectionString'
  parent: keyVault
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${listKeys(storage.id, '2023-01-01').keys[0].value};EndpointSuffix=core.windows.net'
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-centinela-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'asp-centinela-${suffix}'
  location: location
  sku: { name: 'Y1', tier: 'Dynamic' }
}

resource funcApi 'Microsoft.Web/sites@2022-09-01' = {
  name: funcApiName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
      ]
    }
  }
  identity: { type: 'SystemAssigned' }
}

resource funcScoring 'Microsoft.Web/sites@2022-09-01' = {
  name: funcScoringName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      appSettings: [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'AzureWebJobsStorage__accountName', value: storage.name }
      ]
    }
  }
  identity: { type: 'SystemAssigned' }
}

resource roleApiStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(funcApi.id, storage.id, 'storage')
  scope: storage
  properties: {
    principalId: funcApi.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')
  }
}

resource roleApiKV 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(funcApi.id, keyVault.id, 'kv')
  scope: keyVault
  properties: {
    principalId: funcApi.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

resource roleScoringStorage 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(funcScoring.id, storage.id, 'storage2')
  scope: storage
  properties: {
    principalId: funcScoring.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '17d1049b-9a84-46fb-8f53-869881c3d3ab')
  }
}

resource roleScoringKV 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(funcScoring.id, keyVault.id, 'kv2')
  scope: keyVault
  properties: {
    principalId: funcScoring.identity.principalId
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
  }
}

output storageName string = storageName
output queueName string = 'transacciones-pendientes'
output keyVaultName string = kvName
output keyVaultSecretName string = 'StorageConnectionString'
output funcApiEndpoint string = funcApi.properties.defaultHostName
output funcScoringEndpoint string = funcScoring.properties.defaultHostName
