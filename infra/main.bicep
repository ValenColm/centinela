param location string = 'westus'
param suffix string = substring(uniqueString(resourceGroup().id), 0, 6)
param storageName string = 'stcentinela${suffix}'
param kvName string = 'kv-centinela-${suffix}'
param appInsightsName string = 'appi-centinela-${suffix}'

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
  dependsOn: [logAnalytics]
}

output storageName string = storageName
output storageConnectionString string = 'DefaultEndpointsProtocol=https;AccountName=${storage.name};EndpointSuffix=core.windows.net'
output queueName string = 'transacciones-pendientes'
output keyVaultName string = kvName
