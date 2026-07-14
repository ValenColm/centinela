#!/bin/bash
set -e

RESOURCE_GROUP="rg-centinela"
LOCATION="eastus"

echo "=== Creando Resource Group ==="
az group create --name $RESOURCE_GROUP --location $LOCATION

echo "=== Desplegando infraestructura ==="
az deployment group create \
  --resource-group $RESOURCE_GROUP \
  --template-file main.bicep

echo "=== Deploy completado ==="
