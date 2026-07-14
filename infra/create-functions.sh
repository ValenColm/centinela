#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="rg-centinela"
LOCATION="westus"
STORAGE_ACCOUNT="stcentinelaufwhov"
APPINSIGHTS_KEY=$(az monitor app-insights component show --resource-group $RESOURCE_GROUP --query instrumentationKey -o tsv)
SUFFIX=$(date +%s)

echo "=== Creando App Service Plan ==="
az appservice plan create \
  --name "asp-centinela-$SUFFIX" \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Y1 \
  --is-linux

echo "=== Creando Function API ==="
az functionapp create \
  --name "func-api-$SUFFIX" \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --plan "asp-centinela-$SUFFIX" \
  --functions-version 4 \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux \
  --app-insights-key "$APPINSIGHTS_KEY"

echo "=== Creando Function Scoring ==="
az functionapp create \
  --name "func-scoring-$SUFFIX" \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --plan "asp-centinela-$SUFFIX" \
  --functions-version 4 \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux \
  --app-insights-key "$APPINSIGHTS_KEY"

echo "=== Asignando Managed Identity ==="
az functionapp identity assign --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP
az functionapp identity assign --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP

echo "=== Obteniendo Principal IDs ==="
API_PRINCIPAL=$(az functionapp identity show --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP --query principalId -o tsv)
SCORING_PRINCIPAL=$(az functionapp identity show --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP --query principalId -o tsv)

echo "=== Asignando roles Storage ==="
STORAGE_ID=$(az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query id -o tsv)

az role assignment create --assignee $API_PRINCIPAL --role "Storage Table Data Contributor" --scope $STORAGE_ID
az role assignment create --assignee $API_PRINCIPAL --role "Storage Queue Data Contributor" --scope $STORAGE_ID
az role assignment create --assignee $SCORING_PRINCIPAL --role "Storage Table Data Contributor" --scope $STORAGE_ID
az role assignment create --assignee $SCORING_PRINCIPAL --role "Storage Queue Data Contributor" --scope $STORAGE_ID

echo "=== Asignando roles Key Vault ==="
KV_ID=$(az keyvault show --name kv-centinela-ufwhov --resource-group $RESOURCE_GROUP --query id -o tsv)

az role assignment create --assignee $API_PRINCIPAL --role "Key Vault Secrets User" --scope $KV_ID
az role assignment create --assignee $SCORING_PRINCIPAL --role "Key Vault Secrets User" --scope $KV_ID

echo "=== Configurando HTTPS ==="
az functionapp config set --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP --https-only true
az functionapp config set --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP --https-only true

echo ""
echo "Functions creadas:"
echo "  API: func-api-$SUFFIX"
echo "  Scoring: func-scoring-$SUFFIX"
