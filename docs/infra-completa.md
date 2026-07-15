# Infraestructura desplegada

## Stack

Python 3.11 + FastAPI sobre Azure Functions (Consumption Plan Linux).
Infraestructura como código con Bicep + scripts Azure CLI.

## Arquitectura

```
                    ┌──────────────┐
                    │   Cliente    │
                    │  (Fintech)   │
                    └──────┬───────┘
                           │ POST /api/transacciones
                           ▼
              ┌────────────────────────┐
              │  func-api (FastAPI)    │
              │  HTTP Trigger          │
              │  202 Accepted          │
              └──────┬─────────────────┘
                     │ Mensaje a cola
                     ▼
        ┌──────────────────────────────┐
        │  Cola: transacciones-        │
        │        pendientes            │
        │  (Queue Storage)             │
        └──────┬───────────────────────┘
               │ QueueTrigger
               ▼
        ┌──────────────────────────────┐
        │  func-scoring                │
        │  Ejecuta 4 reglas            │
        │  Calcula score               │
        │  Crea caso si > umbral       │
        └──────┬───────────────────────┘
               │ Guarda en Table Storage
               ▼
        ┌──────────────────────────────┐
        │  Table Storage               │
        │  - transacciones             │
        │  - casos                     │
        │  - configuracion             │
        └──────────────────────────────┘

Servicios compartidos:
  ┌──────────┐  ┌──────────────┐  ┌──────────────┐
  │ Key Vault│  │ App Insights │  │ Blob Storage │
  │ Secretos │  │ Monitoreo    │  │ Documentos   │
  └──────────┘  └──────────────┘  └──────────────┘
```

## Base de datos

**No usamos SQL.** Usamos **Azure Table Storage** (NoSQL clave-valor):

| Tabla / Contenedor | Partición | Row Key | Uso |
|-------------------|-----------|---------|-----|
| `transacciones` | `account_id` | `transaction_id` | Historial de transacciones + scores. TTL: 30 días |
| `casos` | `case_id` | `case_id` | Casos de fraude, evidencia, auditoría |
| `configuracion` | `config_type` | `config_key` | Umbral, reglas activas, lista negra |
| `verificaciones` (blob) | carpeta por `case_id` | — | PDFs/imágenes de verificación |

## Presupuesto

| Servicio | Costo |
|----------|-------|
| Azure Functions (Consumption) | ~$0 (1M ejecuciones gratis/mes) |
| Queue Storage | ~$0 (primeros 1GB gratis) |
| Table Storage | ~$0.10/GB |
| Blob Storage | ~$0.02/GB |
| Key Vault | ~$0 (10K transacciones gratis) |
| App Insights | ~$0 (plan gratuito 1GB/mes) |
| **Total estimado** | **< $10 USD** (meta: < $60 de $200 crédito) |

## Recursos en Azure (post-deploy 15/07/2026)

### Resource Group
- **Nombre:** `rg-centinela` (West US)

### Storage Account
- **Nombre:** `stcentinelaufwhov`
- **Tipo:** StorageV2, Standard_LRS
- **Red:** `defaultAction: Allow` + `bypass: AzureServices` (sin firewall de red, seguridad por RBAC)
- **Tablas:** `transacciones`, `casos`, `configuracion`
- **Cola:** `transacciones-pendientes`
- **Contenedor blob:** `verificaciones`

### Key Vault
- **Nombre:** `kv-centinela-ufwhov`
- **RBAC:** habilitado
- **Secretos:** `StorageConnectionString` (connection string con access key del Storage)
- **Soft-delete:** habilitado (por defecto)

### Application Insights
- **Nombre:** `appi-centinela-ufwhov`
- **Plan:** PerGB2018
- **Workspace:** `log-centinela-ufwhov` (Log Analytics)

### Log Analytics
- **Nombre:** `log-centinela-ufwhov`

### Function Apps

Ambas creadas vía CLI (no Bicep) por cuota insuficiente de App Service Plan.

| Propiedad | func-api | func-scoring |
|-----------|----------|--------------|
| Nombre | `func-api-1784119485` | `func-scoring-1784119485` |
| Runtime | Python 3.11 | Python 3.11 |
| Plan | Consumption (Linux) | Consumption (Linux) |
| App Service Plan | `WestUSLinuxDynamicPlan` | `WestUSLinuxDynamicPlan` |
| Managed Identity | `416bb239-71dc-43fe-bfd5-39d32c670659` | `d48871de-7bb8-418a-ad15-e4bda3531b06` |
| HTTPS | `httpsOnly: true` | `httpsOnly: true` |
| App Insights | Conectado a `appi-centinela-ufwhov` | Conectado a `appi-centinela-ufwhov` |

### App Settings configuradas en ambas Functions

| Setting | Valor |
|---------|-------|
| `AZURE_STORAGE_ACCOUNT` | `stcentinelaufwhov` |
| `KEY_VAULT_URI` | `https://kv-centinela-ufwhov.vault.azure.net` |
| `AzureWebJobsStorage__accountName` | `stcentinelaufwhov` |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | `808ded26-4859-48f9-8cf5-37d6b169676d` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=808ded26-4859-48f9-8cf5-37d6b169676d` |

### Roles RBAC asignados

| Principal ID | Function | Role | Recurso |
|-------------|----------|------|---------|
| `416bb239-...` | func-api | Storage Table Data Contributor | Storage |
| `416bb239-...` | func-api | Storage Queue Data Contributor | Storage |
| `d48871de-...` | func-scoring | Storage Table Data Contributor | Storage |
| `d48871de-...` | func-scoring | Storage Queue Data Contributor | Storage |
| `416bb239-...` | func-api | Key Vault Secrets User | Key Vault |
| `d48871de-...` | func-scoring | Key Vault Secrets User | Key Vault |

## CI/CD

GitHub Actions en `.github/workflows/ci.yml`:
- **Trigger:** push a `main` o PR a `main`
- **Jobs:**
  1. `lint` — Ruff (Python lint)
  2. `deploy` — `az login` con Service Principal → despliega Bicep

**Nota:** El Service Principal `sp-centinela-github` NO tiene permisos para asignar roles RBAC. `create-functions.sh` lo corre Valentina manualmente.

## Archivos de infraestructura

| Archivo | Propósito |
|---------|-----------|
| `infra/main.bicep` | Bicep con Storage, Key Vault, App Insights, Log Analytics |
| `infra/deploy.sh` | Script unificado: crea RG → Bicep → Functions |
| `infra/create-functions.sh` | Crea Functions, Managed Identity, roles RBAC, HTTPS, App Settings |
| `.github/workflows/ci.yml` | Pipeline CI/CD (lint + Bicep deploy) |

## Cómo reconstruir todo desde cero

```bash
az group delete --name rg-centinela --yes
# esperar que termine
git clone https://github.com/ValenColm/centinela.git
cd centinela
bash infra/deploy.sh
```

## Errores conocidos y workarounds

Véase `docs/errores-resueltos.md` para la lista completa de errores encontrados y sus soluciones.

Los principales:
1. Cuota insuficiente para App Service Plan → Functions vía CLI con `--consumption-plan-location`
2. SP sin permisos para asignar roles → roles se asignan desde sesión personal
3. Firewall Storage bloqueaba creación de Functions → `defaultAction: Allow`
4. Managed Identity no propagada → `sleep 30` + retry loop en script
5. Key Vault en soft-delete → `az keyvault purge` antes de redeploy
