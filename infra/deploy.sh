#!/bin/bash
set -euo pipefail

RESOURCE_GROUP="rg-centinela"
LOCATION="eastus"

echo "=== Verificando Azure CLI ==="
az account show --query id -o tsv

echo "=== Creando Resource Group (si no existe) ==="
az group create --name $RESOURCE_GROUP --location $LOCATION --output none

echo "=== Desplegando infraestructura ==="
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file main.bicep

echo "=== Obteniendo outputs ==="
az deployment group show \
  --resource-group $RESOURCE_GROUP \
  --query properties.outputs

echo ""
echo "=== Deploy completado exitosamente ==="
