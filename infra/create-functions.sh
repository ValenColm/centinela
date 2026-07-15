#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="rg-centinela"
LOCATION="westus"
STORAGE_ACCOUNT="stcentinelaufwhov"
SUFFIX=$(date +%s)

echo "=== Creando Function API (Consumption) ==="
az functionapp create \
  --name "func-api-$SUFFIX" \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --consumption-plan-location $LOCATION \
  --functions-version 4 \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux \
  --disable-app-insights

echo "=== Creando Function Scoring (Consumption) ==="
az functionapp create \
  --name "func-scoring-$SUFFIX" \
  --resource-group $RESOURCE_GROUP \
  --storage-account $STORAGE_ACCOUNT \
  --consumption-plan-location $LOCATION \
  --functions-version 4 \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux \
  --disable-app-insights

echo "=== Asignando Managed Identity ==="
az functionapp identity assign --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP
az functionapp identity assign --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP

echo "=== Obteniendo Principal IDs ==="
API_PRINCIPAL=$(az functionapp identity show --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP --query principalId -o tsv)
SCORING_PRINCIPAL=$(az functionapp identity show --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP --query principalId -o tsv)

echo "=== Esperando propagación de Managed Identity... ==="
sleep 30

echo "=== Asignando roles Storage ==="
STORAGE_ID=$(az storage account show --name $STORAGE_ACCOUNT --resource-group $RESOURCE_GROUP --query id -o tsv)

for PRINCIPAL in $API_PRINCIPAL $SCORING_PRINCIPAL; do
  for ROLE in "Storage Table Data Contributor" "Storage Queue Data Contributor"; do
    for TRY in 1 2 3; do
      az role assignment create --assignee $PRINCIPAL --role "$ROLE" --scope $STORAGE_ID 2>/dev/null && break
      echo "  Reintentando role $ROLE en $TRY seg... ($PRINCIPAL)"
      sleep $TRY
    done
  done
done

echo "=== Asignando roles Key Vault ==="
KV_ID=$(az keyvault show --name "kv-centinela-ufwhov" --resource-group $RESOURCE_GROUP --query id -o tsv)

for PRINCIPAL in $API_PRINCIPAL $SCORING_PRINCIPAL; do
  for TRY in 1 2 3; do
    az role assignment create --assignee $PRINCIPAL --role "Key Vault Secrets User" --scope $KV_ID 2>/dev/null && break
    echo "  Reintentando Key Vault role en $TRY seg..."
    sleep $TRY
  done
done

echo "=== Configurando HTTPS forzado ==="
az functionapp update --name "func-api-$SUFFIX" --resource-group $RESOURCE_GROUP --set httpsOnly=true
az functionapp update --name "func-scoring-$SUFFIX" --resource-group $RESOURCE_GROUP --set httpsOnly=true

echo "=== Configurando App Settings ==="
APPI_KEY=$(az monitor app-insights component show --app appi-centinela-ufwhov --resource-group $RESOURCE_GROUP --query instrumentationKey -o tsv 2>/dev/null || echo "")

for FUNC in "func-api-$SUFFIX" "func-scoring-$SUFFIX"; do
  SETTINGS="AZURE_STORAGE_ACCOUNT=$STORAGE_ACCOUNT KEY_VAULT_URI=https://kv-centinela-ufwhov.vault.azure.net AzureWebJobsStorage__accountName=$STORAGE_ACCOUNT"
  if [ -n "$APPI_KEY" ]; then
    SETTINGS="$SETTINGS APPINSIGHTS_INSTRUMENTATIONKEY=$APPI_KEY APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=$APPI_KEY"
  fi
  az functionapp config appsettings set --name $FUNC --resource-group $RESOURCE_GROUP --settings $SETTINGS > /dev/null
done

echo ""
echo "=== Functions creadas ==="
echo "  API:     func-api-$SUFFIX"
echo "  Scoring: func-scoring-$SUFFIX"
