# Infraestructura desplegada

## Stack

Python 3.11 + FastAPI sobre Azure Functions (Consumption Plan Linux).
Infraestructura como código con Bicep + scripts Azure CLI.

## Recursos en Azure

### Resource Group
- **Nombre:** `rg-centinela` (West US)

### Storage Account
- **Nombre:** `stcentinelaufwhov`
- **Tipo:** StorageV2, Standard_LRS
- **Red:** `defaultAction: Allow` + `bypass: AzureServices`
- **Elementos creados:**
  - Tabla `transacciones`
  - Tabla `casos`
  - Tabla `configuracion`
  - Cola `transacciones-pendientes`
  - Contenedor blob `verificaciones`

### Key Vault
- **Nombre:** `kv-centinela-ufwhov`
- **RBAC habilitado:** sí
- **Secretos:** `StorageConnectionString` (connection string con access key del Storage)

### Application Insights
- **Nombre:** `appi-centinela-ufwhov`
- **Plan:** PerGB2018
- **Workspace:** `log-centinela-ufwhov` (Log Analytics)

### Function Apps
- **API:** `func-api-1784054556` (Python 3.11, Consumption Linux)
- **Scoring:** `func-scoring-1784054556` (Python 3.11, Consumption Linux)
- **App Service Plan:** `WestUSLinuxDynamicPlan` (creado automáticamente)
- **Managed Identity:** SystemAssigned en ambas
- **HTTPS forzado:** sí (`httpsOnly: true`)

## Roles RBAC asignados

| Function | Role | Recurso |
|----------|------|---------|
| func-api | Storage Table Data Contributor | Storage Account |
| func-api | Storage Queue Data Contributor | Storage Account |
| func-scoring | Storage Table Data Contributor | Storage Account |
| func-scoring | Storage Queue Data Contributor | Storage Account |
| func-api | Key Vault Secrets User | Key Vault |
| func-scoring | Key Vault Secrets User | Key Vault |

## CI/CD

GitHub Actions en `.github/workflows/ci.yml`:
- **Trigger:** push a `main` o PR a `main`
- **Jobs:**
  1. `lint` — corre Ruff (Python lint)
  2. `deploy` — az login con Service Principal → `az deployment group create` del Bicep

Service Principal `sp-centinela-github` con rol Contributor sobre la suscripción.
Secret `AZURE_CREDENTIALS` configurado en GitHub.

## Archivos de infraestructura

| Archivo | Propósito |
|---------|-----------|
| `infra/main.bicep` | Bicep con Storage, Key Vault, App Insights, Log Analytics |
| `infra/deploy.sh` | Script que crea RG y despliega Bicep |
| `infra/create-functions.sh` | Script que crea Functions, Managed Identity, roles RBAC, HTTPS |
| `.github/workflows/ci.yml` | Pipeline CI/CD |
