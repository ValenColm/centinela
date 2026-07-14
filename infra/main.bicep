param location string = 'eastus'
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
}

resource tableCasos 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/casos'
}

resource tableConfig 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/configuracion'
}

resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storageName}/default/transacciones-pendientes'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageName}/default/verificaciones'
}

resource keyVault 'Microsoft.KeyVault/vaults@2023-04-01' = {
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

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}

resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-centinela-${uniqueString(resourceGroup().id)}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
  }
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
        { name: 'AZURE_STORAGE_CONNECTION_STRING', value: 'DefaultEndpointsProtocol=https;AccountName=${storageName};AccountKey=${listKeys(storage.id, '2023-01-01').keys[0].value};TableEndpoint=https://${storageName}.table.core.windows.net/' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
      ]
    }
  }
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
        { name: 'AZURE_STORAGE_CONNECTION_STRING', value: 'DefaultEndpointsProtocol=https;AccountName=${storageName};AccountKey=${listKeys(storage.id, '2023-01-01').keys[0].value};TableEndpoint=https://${storageName}.table.core.windows.net/' }
        { name: 'APPINSIGHTS_INSTRUMENTATIONKEY', value: appInsights.properties.InstrumentationKey }
        { name: 'FUNCTIONS_WORKER_RUNTIME', value: 'python' }
      ]
    }
  }
}

output storageName string = storageName
output queueName string = 'transacciones-pendientes'
output funcApiEndpoint string = funcApi.properties.defaultHostName
output funcScoringEndpoint string = funcScoring.properties.defaultHostName
