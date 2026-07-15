#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="rg-centinela"
LOCATION="westus"

echo "=== Verificando Azure CLI ==="
az account show --query id -o tsv

echo "=== Registrando providers ==="
az provider register --namespace Microsoft.Web --output none
az provider register --namespace Microsoft.Storage --output none
az provider register --namespace Microsoft.KeyVault --output none
az provider register --namespace Microsoft.Insights --output none
az provider register --namespace Microsoft.OperationalInsights --output none

echo "=== Verificando cuota disponible ==="
az vm list-usage --location $LOCATION --output table 2>/dev/null || echo "No se pudo verificar cuota"
echo "Si falla por cuota, probá: az vm quota increase --location westus"

echo "=== Creando Resource Group ==="
az group create --name $RESOURCE_GROUP --location $LOCATION --output none

SCRIPT_DIR="$(dirname "$0")"

echo "=== Desplegando infraestructura ==="
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file "$SCRIPT_DIR/main.bicep" \
  --output table

echo "=== Obteniendo outputs ==="
az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --name main \
  --query properties.outputs

echo ""
echo "=== Creando Functions vía CLI ==="
if [ -f "$SCRIPT_DIR/create-functions.sh" ]; then
  bash "$SCRIPT_DIR/create-functions.sh"
else
  echo "ERROR: create-functions.sh no encontrado en $SCRIPT_DIR"
  exit 1
fi

echo "=== Deploy completado ==="
