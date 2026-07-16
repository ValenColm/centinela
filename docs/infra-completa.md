# Infraestructura desplegada

## Stack

Python 3.11 + FastAPI sobre Azure Functions (Consumption Plan Linux).
Infraestructura como código con Bicep + scripts Azure CLI.

---

## Tipo de arquitectura

**Arquitectura Serverless orientada a eventos (Event-Driven Serverless).**

| Principio | Cómo se aplica |
|-----------|---------------|
| Sin servidores | Azure Functions Consumption — no hay VMs, no hay servidores que administrar |
| Orientada a eventos | Queue Storage desacopla la API del procesamiento |
| Escala automática | De 0 a miles de requests según demanda |
| Pago por uso | Solo se cobra cuando hay ejecuciones (0 si no hay tráfico) |
| Mínimos privilegios | Managed Identity + RBAC — cada componente solo accede a lo que necesita |

### ¿Por qué esta arquitectura?

- **Serverless (Consumption Plan):** No hay VMs encendidas 24/7. Si nadie usa el sistema, el costo es ~$0.
- **Cola de mensajes (Queue Storage):** El cliente recibe `202 Accepted` al instante. El procesamiento pesado (scoring) ocurre después de forma asíncrona.
- **Table Storage (NoSQL):** Cuesta ~$0.10/GB vs ~$15/mes de Azure SQL. Es suficiente para el volumen del proyecto.
- **Managed Identity:** Las Functions se autentican contra Storage y Key Vault sin usar claves ni secrets en código.

---

## Arquitectura del proyecto

```
                    ┌──────────────┐
                    │   Cliente    │
                    │  (Fintech)   │
                    └──────┬───────┘
                           │ POST /api/transacciones
                           ▼
              ┌──────────────────────────────────┐
              │  func-api (Azure Function)       │
              │  Python 3.11 + FastAPI           │
              │                                  │
              │  1. Valida payload (Pydantic)    │
              │  2. Responde 202 Accepted        │
              │  3. Publica en Queue Storage     │
              └──────────┬───────────────────────┘
                         │
                         ▼
              ┌──────────────────────────────────┐
              │  Queue Storage                   │
              │  transacciones-pendientes        │
              │  (Mensaje persistido)            │
              └──────────┬───────────────────────┘
                         │ QueueTrigger
                         ▼
              ┌──────────────────────────────────┐
              │  func-scoring (Azure Function)   │
              │  Python 3.11                     │
              │                                  │
              │  1. Lee mensaje de la cola       │
              │  2. Consulta historial cuenta    │
              │  3. Ejecuta 4 reglas:            │
              │     · Velocidad                  │
              │     · Monto atípico              │
              │     · Ubicación imposible        │
              │     · Comercio riesgo            │
              │  4. Suma puntos = score          │
              │  5. Score > umbral → crea caso   │
              │  6. Guarda en Table Storage      │
              └──────┬───────────────────────────┘
                     │
          ┌──────────┼────────────┐
          ▼          ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────────┐
   │ Table    │ │ Table    │ │ Blob         │
   │ transac- │ │ casos    │ │ verificaciones│
   │ ciones   │ │          │ │ (imágenes/   │
   │          │ │          │ │  PDFs)       │
   └──────────┘ └──────────┘ └──────────────┘


Servicios compartidos:
   ┌─────────────────────┐   ┌──────────────────────────┐
   │ Key Vault           │   │ Application Insights      │
   │ kv-centinela-ufwhov │   │ appi-centinela-ufwhov     │
   │ └─ StorageConnStr   │   │ (métricas, logs, tracing)│
   └─────────────────────┘   └──────────────────────────┘
```

---

## Estructura de recursos en Azure (jerarquía)

```
Subscription: c191446a-23f6-4ebd-96e5-7e9be3c1c214 (Free Account $200)
│
└── Resource Group: rg-centinela (West US)
    │
    ├── 📦 Storage Account: stcentinelaufwhov (StorageV2, Standard_LRS)
    │   │   networkAcls: { defaultAction: Allow, bypass: AzureServices }
    │   │
    │   ├── 📋 Table: transacciones          [PK: account_id, RK: transaction_id]
    │   ├── 📋 Table: casos                  [PK: case_id,    RK: case_id]
    │   ├── 📋 Table: configuracion          [PK: config_type, RK: config_key]
    │   ├── 📬 Queue: transacciones-pendientes
    │   └── 📁 Blob Container: verificaciones
    │
    ├── 🔐 Key Vault: kv-centinela-ufwhov
    │   │   enableRbacAuthorization: true
    │   │   sku: Standard
    │   │
    │   └── 🔑 Secret: StorageConnectionString
    │
    ├── 📊 Application Insights: appi-centinela-ufwhov
    │       kind: web
    │       plan: PerGB2018
    │
    ├── 📈 Log Analytics: log-centinela-ufwhov
    │       sku: PerGB2018
    │
    ├── 🏗️ App Service Plan: WestUSLinuxDynamicPlan
    │       (creado automáticamente por --consumption-plan-location)
    │
    ├── ⚡ Function App: func-api-1784119485
    │   │   runtime: Python 3.11
    │   │   httpsOnly: true
    │   │   linuxFxVersion: Python|3.11
    │   │
    │   ├── 🆔 Managed Identity: 416bb239-71dc-43fe-bfd5-39d32c670659
    │   └── ⚙️ App Settings:
    │       ├── AZURE_STORAGE_ACCOUNT = stcentinelaufwhov
    │       ├── KEY_VAULT_URI = https://kv-centinela-ufwhov.vault.azure.net
    │       ├── AzureWebJobsStorage__accountName = stcentinelaufwhov
    │       ├── APPINSIGHTS_INSTRUMENTATIONKEY = 808ded26-...
    │       └── APPLICATIONINSIGHTS_CONNECTION_STRING = InstrumentationKey=808ded26-...
    │
    └── ⚡ Function App: func-scoring-1784119485
        │   runtime: Python 3.11
        │   httpsOnly: true
        │   linuxFxVersion: Python|3.11
        │
        ├── 🆔 Managed Identity: d48871de-7bb8-418a-ad15-e4bda3531b06
        └── ⚙️ App Settings:
            ├── AZURE_STORAGE_ACCOUNT = stcentinelaufwhov
            ├── KEY_VAULT_URI = https://kv-centinela-ufwhov.vault.azure.net
            ├── AzureWebJobsStorage__accountName = stcentinelaufwhov
            ├── APPINSIGHTS_INSTRUMENTATIONKEY = 808ded26-...
            └── APPLICATIONINSIGHTS_CONNECTION_STRING = InstrumentationKey=808ded26-...
```

---

## Estructura de seguridad (RBAC + identidades)

```
Azure Active Directory
│
├── 👤 Service Principal: sp-centinela-github
│   │   Usado por: GitHub Actions (CI/CD)
│   │
│   └── 📋 Role: Contributor → Subscription c191446a-...
│       (Puede crear recursos pero NO asignar roles)
│
├── 🆔 Managed Identity: func-api (416bb239-...)
│   │   Usado por: func-api en runtime
│   │
│   ├── 📋 Role: Storage Table Data Contributor → stcentinelaufwhov
│   ├── 📋 Role: Storage Queue Data Contributor → stcentinelaufwhov
│   └── 📋 Role: Key Vault Secrets User → kv-centinela-ufwhov
│
└── 🆔 Managed Identity: func-scoring (d48871de-...)
│   │   Usado por: func-scoring en runtime
│   │
│   ├── 📋 Role: Storage Table Data Contributor → stcentinelaufwhov
│   ├── 📋 Role: Storage Queue Data Contributor → stcentinelaufwhov
│   └── 📋 Role: Key Vault Secrets User → kv-centinela-ufwhov
```

### ¿Cómo se autentican las Functions?

```
func-api / func-scoring
        │
        │ (1) Pide token a Azure AD Managed Identity endpoint
        ▼
Azure AD ──→ Devuelve token JWT
        │
        │ (2) Usa ese token para autenticarse
        ▼
Storage Account / Key Vault
        │
        │ (3) Valida token + verifica RBAC
        ▼
¿Tiene el rol necesario? → Sí: permite acceso
                      → No: rechaza (403)
```

**No hay connection strings. No hay claves. No hay secrets en código.**

---

## Base de datos

**No usamos SQL.** Usamos **Azure Table Storage** (NoSQL clave-valor):

| Tabla / Contenedor | Partition Key | Row Key | Uso |
|-------------------|---------------|---------|-----|
| `transacciones` | `account_id` | `transaction_id` | Historial de transacciones + scores. TTL: 30 días |
| `casos` | `case_id` | `case_id` | Casos de fraude, evidencia, auditoría |
| `configuracion` | `config_type` | `config_key` | Umbral, reglas activas, lista negra |
| `verificaciones` (blob) | carpeta por `case_id` | — | PDFs/imágenes de verificación |

---

## Decisiones de construcción

| Decisión | Alternativa descartada | Por qué elegimos esta |
|----------|----------------------|-----------------------|
| Functions vía CLI (no Bicep) | Bicep con App Service Plan | Error `SubscriptionIsOverQuotaForSku` — cuota insuficiente |
| Storage sin firewall | Storage con `defaultAction: Deny` | Firewall bloqueaba aprovisionamiento de Functions |
| Table Storage (NoSQL) | Azure SQL Database | Costo (~$0.10 vs ~$15/mes mínimo de SQL) |
| Consumption Plan | App Service Plan dedicado | $0 si no hay uso (pago por ejecución) |
| Managed Identity (SystemAssigned) | Claves de acceso (access keys) | Más seguro, sin secrets que rotar |
| RBAC manual en CLI | RBAC desde Bicep | SP no tiene permiso `roleAssignments/write` |
| `--consumption-plan-location` | `--plan` con plan propio | Evita crear App Service Plan manualmente (cuota) |
| `--disable-app-insights` + config manual | `--application-insights` auto | Evita crear App Insights duplicados por Function |
| `sleep 30` + retry loop para RBAC | Asignación inmediata | Managed Identity tarda en propagarse al graph de Azure AD |
| `az functionapp update --set httpsOnly=true` | `az functionapp config set --https-only true` | El segundo comando no existe |

---

## Recursos en Azure (post-deploy 15/07/2026)

### Resource Group
- **Nombre:** `rg-centinela` (West US)

### Storage Account
- **Nombre:** `stcentinelaufwhov`
- **Tipo:** StorageV2, Standard_LRS
- **Red:** `defaultAction: Allow` + `bypass: AzureServices`
- **Tablas:** `transacciones`, `casos`, `configuracion`
- **Cola:** `transacciones-pendientes`
- **Contenedor blob:** `verificaciones`

### Key Vault
- **Nombre:** `kv-centinela-ufwhov`
- **RBAC:** habilitado
- **Secretos:** `StorageConnectionString`
- **Soft-delete:** habilitado

### Application Insights
- **Nombre:** `appi-centinela-ufwhov`
- **Plan:** PerGB2018
- **Workspace:** `log-centinela-ufwhov` (Log Analytics)

### Log Analytics
- **Nombre:** `log-centinela-ufwhov`

### Function Apps

| Propiedad | func-api | func-scoring |
|-----------|----------|--------------|
| Nombre | `func-api-1784119485` | `func-scoring-1784119485` |
| Runtime | Python 3.11 | Python 3.11 |
| Plan | Consumption (Linux) | Consumption (Linux) |
| App Service Plan | `WestUSLinuxDynamicPlan` | `WestUSLinuxDynamicPlan` |
| Managed Identity | `416bb239-...` | `d48871de-...` |
| HTTPS | `httpsOnly: true` | `httpsOnly: true` |

### App Settings (ambas Functions)

| Setting | Valor |
|---------|-------|
| `AZURE_STORAGE_ACCOUNT` | `stcentinelaufwhov` |
| `KEY_VAULT_URI` | `https://kv-centinela-ufwhov.vault.azure.net` |
| `AzureWebJobsStorage__accountName` | `stcentinelaufwhov` |
| `APPINSIGHTS_INSTRUMENTATIONKEY` | `808ded26-4859-48f9-8cf5-37d6b169676d` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | `InstrumentationKey=808ded26-...` |

### Roles RBAC

| Managed Identity | Role | Recurso |
|-----------------|------|---------|
| func-api | Storage Table Data Contributor | stcentinelaufwhov |
| func-api | Storage Queue Data Contributor | stcentinelaufwhov |
| func-api | Key Vault Secrets User | kv-centinela-ufwhov |
| func-scoring | Storage Table Data Contributor | stcentinelaufwhov |
| func-scoring | Storage Queue Data Contributor | stcentinelaufwhov |
| func-scoring | Key Vault Secrets User | kv-centinela-ufwhov |

---

## Presupuesto

| Servicio | Costo estimado |
|----------|---------------|
| Azure Functions (Consumption) | ~$0 (1M ejecuciones gratis/mes) |
| Queue Storage | ~$0 (primeros 1GB gratis) |
| Table Storage | ~$0.10/GB |
| Blob Storage | ~$0.02/GB |
| Key Vault | ~$0 (10K transacciones gratis) |
| Application Insights | ~$0 (1GB/mes gratis) |
| AI Document Intelligence | ~$1-2 (si se usa) |
| **Total estimado mensual** | **< $10 USD** |
| **Meta del proyecto** | **< $60 USD de $200 crédito** |

---

## CI/CD

GitHub Actions en `.github/workflows/ci.yml`:
- **Trigger:** push a `main` o PR a `main`
- **Jobs:**
  1. `lint` — Ruff (Python lint)
  2. `deploy` — `az login` con Service Principal → despliega Bicep

**Nota:** El Service Principal `sp-centinela-github` NO tiene permisos para asignar roles RBAC.
`create-functions.sh` lo corre Valentina manualmente desde su sesión de Azure.

---

## Archivos de infraestructura

| Archivo | Propósito |
|---------|-----------|
| `infra/main.bicep` | Bicep con Storage, Key Vault, App Insights, Log Analytics |
| `infra/deploy.sh` | Script unificado: crea RG → Bicep → Functions |
| `infra/create-functions.sh` | Crea Functions, Managed Identity, roles RBAC, HTTPS, App Settings |
| `.github/workflows/ci.yml` | Pipeline CI/CD (lint + Bicep deploy) |
| `docs/infra-completa.md` | Este documento |
| `docs/errores-resueltos.md` | Errores encontrados y soluciones |
| `docs/pendiente-semana.md` | Estado actual y próximas tareas |

---

## Cómo reconstruir todo desde cero

```bash
# 1. Eliminar resource group completo
az group delete --name rg-centinela --yes

# 2. Esperar que termine la eliminación
az group wait --deleted --name rg-centinela

# 3. Clonar y deployar
git clone https://github.com/ValenColm/centinela.git
cd centinela
bash infra/deploy.sh
```

---

## Errores conocidos y workarounds

Los principales errores encontrados durante el setup (ver `docs/errores-resueltos.md` para detalle):

| Error | Solución |
|-------|----------|
| `SubscriptionIsOverQuotaForSku` al crear App Service Plan | Functions vía CLI con `--consumption-plan-location` |
| `AuthorizationFailed` en roleAssignments de Bicep | Roles se asignan desde CLI manual (SP no tiene permiso) |
| Storage firewall bloquea creación de Functions | `defaultAction: Allow` + `bypass: AzureServices` |
| `Cannot find user or service principal in graph database` | `sleep 30` + retry loop para propagación de Managed Identity |
| Key Vault en soft-delete bloquea redeploy | `az keyvault purge --name <kv> --location westus` antes de redeploy |
| `DeploymentActive` conflict | Usar nombre único con timestamp (`centinela-$(date +%s)`) |
| App Insights duplicados por Function | `--disable-app-insights` + configurar manualmente el central |
| `az functionapp config set --https-only` no existe | `az functionapp update --set httpsOnly=true` |
