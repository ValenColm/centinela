param location string = 'westus'
param storageName string = 'stcentinela${uniqueString(resourceGroup().id)}'
param funcApiName string = 'func-centinela-api-${uniqueString(resourceGroup().id)}'
param funcScoringName string = 'func-centinela-scoring-${uniqueString(resourceGroup().id)}'
param kvName string = 'kv-centinela-${uniqueString(resourceGroup().id)}'
param appInsightsName string = 'appi-centinela-${uniqueString(resourceGroup().id)}'

resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
  }
}

resource tableTransacciones 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/transacciones'
  dependsOn: [storage]
}

resource tableCasos 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/casos'
  dependsOn: [storage]
}

resource tableConfig 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/configuracion'
  dependsOn: [storage]
}

resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storageName}/default/transacciones-pendientes'
  dependsOn: [storage]
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageName}/default/verificaciones'
  dependsOn: [storage]
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

resource plan 'Microsoft.Web/serverfarms@2022-09-01' = {
  name: 'asp-centinela-${uniqueString(resourceGroup().id)}'
  location: location
  kind: 'functionapp'
  sku: { name: 'Y1', tier: 'Dynamic' }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-centinela-${uniqueString(resourceGroup().id)}'
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
  dependsOn: [logAnalytics]
}

resource funcApi 'Microsoft.Web/sites@2022-09-01' = {
  name: funcApiName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'AZURE_STORAGE_ACCOUNT', value: storage.name }
      ]
    }
  }
  dependsOn: [plan, appInsights, storage]
}

resource funcScoring 'Microsoft.Web/sites@2022-09-01' = {
  name: funcScoringName
  location: location
  kind: 'functionapp'
  properties: {
    serverFarmId: plan.id
    httpsOnly: true
    siteConfig: {
      linuxFxVersion: 'Python|3.11'
      appSettings: [
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'AZURE_STORAGE_ACCOUNT', value: storage.name }
      ]
    }
  }
  dependsOn: [plan, appInsights, storage]
}

output storageName string = storageName
output storageConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=core.windows.net'
output queueName string = 'transacciones-pendientes'
output funcApiEndpoint string = funcApi.properties.defaultHostName
output funcScoringEndpoint string = funcScoring.properties.defaultHostName
output keyVaultName string = kvName
