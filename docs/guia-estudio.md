# Centinela — Guía de Estudio Completa

## 1. ¿Qué es Centinela?

- Sistema de detección de fraude transaccional en tiempo real
- Construido para una fintech que procesa transacciones de tarjetas y transferencias
- Arquitectura event-driven, serverless, con presupuesto ajustado
- Objetivo: detectar transacciones sospechosas en milisegundos sin bloquear al cliente

### El problema

La fintech pierde dinero por fraude que nadie detecta a tiempo. Cada transacción debe analizarse en tiempo real contra reglas de riesgo, calcular un score, y decidir si sigue su curso o se abre un caso de fraude.

### Las tres restricciones que definieron la arquitectura

1. **El cliente no puede esperar** → la API responde 202 antes de terminar el análisis (desacoplamiento)
2. **El volumen no es constante** → picos los viernes 6pm vs madrugada; debe auto-escalar
3. **El sistema no se puede caer** → observabilidad de punta a punta, despliegue automatizado

### Actores del sistema

| Rol                          | Qué hace                                                                                              |
| ---------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Cliente**            | Origina transacciones. No interactúa con Centinela.                                                   |
| **Analista de fraude** | Revisa casos, ve evidencia, resuelve: confirma fraude o lo descarta. Escala casos subiendo documentos. |
| **Administrador**      | Configura reglas, ajusta umbral, gestiona comercios de riesgo y usuarios.                              |
| **Servicio**           | Identidad interna que usan los componentes para comunicarse. Corre sin intervención humana.           |
| **Auditor**            | Ve todo el sistema. No modifica nada.                                                                  |

### Stack Tecnológico

| Componente                   | Tecnología                               |
| ---------------------------- | ----------------------------------------- |
| Lenguaje                     | Python 3.11                               |
| API                          | FastAPI (ASGI)                            |
| Compute                      | Azure Functions (Consumption Plan, Linux) |
| Base de datos                | Azure Table Storage (NoSQL)               |
| Mensajería                  | Azure Queue Storage                       |
| Archivos                     | Azure Blob Storage                        |
| Secretos                     | Azure Key Vault                           |
| Monitoreo                    | Application Insights + Log Analytics      |
| Infraestructura como código | Bicep + Bash                              |
| CI/CD                        | GitHub Actions                            |
| Frontend                     | Jinja2 Templates                          |
| Autenticación               | JWT + cookies HttpOnly                    |
| Total código                | ~3704 líneas de Python                   |

---

## 2. Arquitectura General (diagrama)

### Diagrama de flujo

```
┌──────────┐     POST /transaccion     ┌─────────────────────────────────┐
│          │ ──────────────────────────►│                                 │
│  Fintech │                           │     func-api (FastAPI)          │
│ (Cliente)│◄──────────────────────────│  • Recibe transacción           │
│          │     202 Accepted          │  • Valida JWT + API Key         │
└──────────┘                           │  • Responde 202 inmediato       │
                                       │  • Publica evento en cola       │
                                       └──────────────┬──────────────────┘
                                                      │
                                                      │ Azure Queue Storage
                                                      │ "transacciones-pendientes"
                                                      │
                                                      ▼
                                       ┌──────────────────────────────────┐
                                       │  func-scoring (QueueTrigger)     │
                                       │  • Reacciona al evento           │
                                       │  • Consulta historial en Tables  │
                                       │  • Aplica 4 reglas heurísticas   │
                                       │  • Calcula score                 │
                                       │  • Si score > umbral → crea caso │
                                       │  • Genera explicación            │
                                       └──────┬───────────────────────────┘
                                              │
                          ┌───────────────────┼────────────────────┐
                          ▼                   ▼                    ▼
                   ┌────────────┐     ┌──────────────┐    ┌──────────────┐
                   │transacciones│    │    casos      │   │configuracion │
                   │  (Table)    │    │  (Table)      │   │  (Table)     │
                   └────────────┘     └──────┬───────┘    └──────────────┘
                                             │
                                             ▼
                                   ┌──────────────────┐
                                   │ Frontend Web App │
                                   │ (Jinja2 + FastAPI)│
                                   │                  │
                                   │ • Login (JWT)    │
                                   │ • Dashboard caso │
                                   │ • Detalle caso   │
                                   │ • Admin reglas   │
                                   │ • Vista auditor  │
                                   └──────────────────┘
```

### ¿Por qué el cliente recibe respuesta antes del análisis?

La API responde **202 Accepted** inmediatamente después de recibir la transacción. El análisis (scoring) ocurre después, de forma asíncrona, mediante una cola. Esto es obligatorio porque:

- El cliente (la fintech) necesita respuesta en milisegundos para seguir procesando
- El scoring puede tomar segundos (consultar historial, aplicar 4 reglas, guardar resultado)
- Si el scoring falla, la transacción queda en la cola y se reintenta automáticamente
- El cliente no se entera si el scoring falló — ya recibió su 202

### Recorrido de una Transacción (paso a paso)

```
PASO 1: INGESTA
───────────────
Cliente → POST /transaccion → func-api
  • Llega una transacción: {cuenta, monto, ubicacion, comercio, timestamp}
  • API valida: JWT, API Key, payload size
  • Responde 202 Accepted (inmediato)
  • El cliente recibe respuesta y sigue con lo suyo

PASO 2: PUBLICACIÓN DEL EVENTO
─────────────────────────────
func-api → Queue "transacciones-pendientes"
  • La transacción se publica como mensaje en la cola
  • Aquí termina la responsabilidad de la API

PASO 3: SCORING (ASÍNCRONO)
───────────────────────────
Queue → func-scoring (QueueTrigger)
  • El motor de scoring se activa automáticamente
  • Consulta Table "transacciones" para obtener historial reciente de la cuenta
  • Aplica las 4 reglas heurísticas
  • Cada regla suma puntos al score
  • Guarda el resultado en Table "transacciones" con detalle de por qué

PASO 4: DECISIÓN
────────────────
  • Si score > umbral:
    - Se crea un caso en Table "casos"
    - Se genera explicación legible (plantilla determinista)
  • Si score ≤ umbral:
    - Solo queda registrado en transacciones
    - No se abre caso

PASO 5: FRONTEND — EL ANALISTA REVISA
─────────────────────────────────────
  • Analista hace login (JWT, cookies HttpOnly)
  • Ve lista de casos abiertos en Dashboard
  • Abre detalle del caso con explicación legible
  • Decide: confirma fraude o descarta
  • Si escala: sube documento de verificación a Blob "verificaciones"

PASO 6: AUDITORÍA
────────────────
  • Todo queda registrado: quién resolvió, cuándo, qué decisión
  • El auditor puede ver todo sin modificar nada
```

### Diagrama de flujo temporal

```
CLIENTE                    FUNC-API                QUEUE               FUNC-SCORING              TABLES
   │                         │                      │                      │                     │
   │──── POST /transaccion──►│                      │                      │                     │
   │◄──── 202 Accepted ──────│                      │                      │                     │
   │                         │───── mensaje ───────►│                      │                     │
   │                         │                      │───── trigger ──────►│                     │
   │                         │                      │                      │──── consulta ──────►│
   │                         │                      │                      │◄─── historial ──────│
   │                         │                      │                      │                     │
   │                         │                      │                      │─── aplica reglas ───│
   │                         │                      │                      │                     │
   │                         │                      │                      │── guarda score ────►│
   │                         │                      │                      │                     │
   │                         │                      │                      │── si > umbral ─────►│
   │                         │                      │                      │   crea caso         │
```

---

## 3. Infraestructura Completa (diagrama + descripción)

### Diagrama de recursos en Azure

```
┌──────────────────────────────────────────────────────────────────────┐
│                         rg-centinela                                  │
│  (Resource Group: límite administrativo, de costos, y de seguridad)  │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────┐      ┌─────────────────────────────┐    │
│  │  func-api-1784119485    │      │  func-scoring-1784119485    │    │
│  │  (Function App - API)   │      │  (Function App - Scoring)   │    │
│  │  • FastAPI ASGI         │      │  • QueueTrigger             │    │
│  │  • Recibe transacciones │      │  • Aplica reglas            │    │
│  │  • Responde 202         │      │  • Calcula score            │    │
│  │  • Publica en cola      │      │  • Abre casos               │    │
│  └───────────┬─────────────┘      └───────────┬─────────────────┘    │
│              │                               │                        │
│              │         ┌─────────────────────┘                        │
│              ▼         ▼                                              │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  stcentinelaufwhov (Storage Account - Standard_LRS)          │    │
│  │                                                               │    │
│  │  Tables (Azure Table Storage - NoSQL):                       │    │
│  │  ├── transacciones    → historial de transacciones + scores  │    │
│  │  ├── casos            → casos de fraude                      │    │
│  │  └── configuracion    → reglas, umbral, comercios de riesgo  │    │
│  │                                                               │    │
│  │  Queue (Azure Queue Storage):                                │    │
│  │  └── transacciones-pendientes → eventos para scoring         │    │
│  │                                                               │    │
│  │  Blob (Azure Blob Storage):                                  │    │
│  │  └── verificaciones → documentos de identidad                │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              │                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  kv-centinela-ufwhov (Key Vault - Standard)                  │    │
│  │  • StorageConnectionString (secreto)                         │    │
│  │  • RBAC habilitado (sin access policies)                     │    │
│  │  • Solo accesible via Managed Identity                       │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                              │                                        │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  appi-centinela-ufwhov (Application Insights)                │    │
│  │  • Métricas: latencia, throughput, tasa de error             │    │
│  │  • Trazas distribuidas (extremo a extremo)                   │    │
│  │  • Dashboards de monitoreo                                   │    │
│  └──────────────────────────┬───────────────────────────────────┘    │
│                             │                                         │
│  ┌──────────────────────────▼───────────────────────────────────┐    │
│  │  log-centinela-ufwhov (Log Analytics Workspace - PerGB2018)  │    │
│  │  • Almacena logs de App Insights                             │    │
│  │  • Consultas con KQL (Kusto Query Language)                  │    │
│  │  • Base para alertas                                         │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  WestUSLinuxDynamicPlan (App Service Plan)                    │    │
│  │  • Creado automáticamente por Azure                           │    │
│  │  • Plan Consumption (Dinámico) → escala a 0 cuando no se usa │    │
│  │  • Linux + Dynamic = la combinación gratuita                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
```

### Lista completa de recursos en rg-centinela

| Recurso                 | Tipo                 | Creado por                       | Propósito                      |
| ----------------------- | -------------------- | -------------------------------- | ------------------------------- |
| func-api-1784119485     | Function App         | CLI (create-functions.sh)        | API REST FastAPI                |
| func-scoring-1784119485 | Function App         | CLI (create-functions.sh)        | Motor de scoring (QueueTrigger) |
| WestUSLinuxDynamicPlan  | App Service Plan     | Automático (al crear Functions) | Plan de hosting Consumption     |
| stcentinelaufwhov       | Storage Account      | Bicep                            | Datos, colas, archivos          |
| kv-centinela-ufwhov     | Key Vault            | Bicep                            | Secretos y credenciales         |
| appi-centinela-ufwhov   | Application Insights | Bicep                            | Monitoreo y métricas           |
| log-centinela-ufwhov    | Log Analytics        | Bicep                            | Almacén de logs y consultas    |

### Los 3 Scripts — CÓMO se levantó la infraestructura

#### `infra/main.bicep` — ¿Qué crea y por qué Bicep?

**¿Qué crea?** (9 recursos)

- Storage Account (con tables: transacciones, casos, configuracion; queue: transacciones-pendientes; blob: verificaciones)
- Key Vault (con RBAC habilitado, secreto StorageConnectionString)
- Log Analytics Workspace
- Application Insights (vinculado al Log Analytics)

**¿Por qué Bicep y no Terraform/Pulumi?**

- Bicep es nativo de Azure, DSL simple, no requiere estado externo
- Terraform sería overkill para 9 recursos + requiere backend de estado

**¿Por qué las Functions NO están en Bicep?**

- Azure Free tier tiene cuota: **1 App Service Plan por región**
- Bicep/ARM intenta crear un nuevo Plan → error `SubscriptionIsOverQuotaForSku`
- Solución: crearlas con CLI `az functionapp create --consumption-plan-location`

#### `infra/deploy.sh` — Flujo completo

```bash
1. az group create --name rg-centinela
2. az deployment group create --template-file infra/main.bicep
3. bash infra/create-functions.sh
```

- **Unificado**: un solo script recrea todo desde cero
- **Idempotente**: se puede ejecutar múltiples veces sin romper nada
- **Versionado**: está en el repositorio, cualquier miembro del equipo puede ejecutarlo

#### `infra/create-functions.sh` — Las 7 etapas

| Paso | Comando                                               | Propósito                                                                                         |
| ---- | ----------------------------------------------------- | -------------------------------------------------------------------------------------------------- |
| 1    | `az functionapp create --consumption-plan-location` | Crear Function evitando error de quota                                                             |
| 2    | `--disable-app-insights`                            | Evitar que Azure cree App Insights duplicada                                                       |
| 3    | `az functionapp identity assign`                    | Asignar Managed Identity a cada Function                                                           |
| 4    | `sleep 30`                                          | Esperar propagación de la identidad en Azure AD                                                   |
| 5    | `az role assignment create` (con retry loop)        | Asignar roles RBAC: Storage Table Data Contributor, Queue Data Contributor, Key Vault Secrets User |
| 6    | `az functionapp update --set httpsOnly=true`        | Forzar HTTPS exclusivamente                                                                        |
| 7    | `az functionapp config appsettings set`             | Configurar variables de entorno: AZURE_STORAGE_ACCOUNT, KEY_VAULT_URI, App Insights keys           |

**Por qué `--consumption-plan-location` en vez de `--plan`:**

- Normalmente se crea un App Service Plan y se pasa con `--plan`
- En Free tier, no puedes crear un segundo Consumption Plan
- `--consumption-plan-location` reusa el plan existente (`WestUSLinuxDynamicPlan`) o lo crea si no existe
- Esto evita el error `SubscriptionIsOverQuotaForSku`

**Por qué `--disable-app-insights`:**

- Por defecto, `az functionapp create` crea automáticamente un recurso Application Insights por cada Function
- Esto resulta en App Insights duplicadas (recursos zombis)
- Nosotros ya tenemos `appi-centinela-ufwhov` creado por Bicep
- Las Functions se configuran manualmente con las keys de App Insights en el paso 7

### Problemas Encontrados y Soluciones

> ⭐ Esta sección es la más importante para la evaluación — muestra que aprendimos de los errores.

| # | Problema                                            | Contexto                                                                                                                             | Solución                                                                                                                                                         |
| - | --------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1 | **SubscriptionIsOverQuotaForSku**             | Bicep/ARM no puede crear Consumption Plan en Free tier                                                                               | Crear Functions vía CLI con`--consumption-plan-location`. Esto evita crear un nuevo plan y reusa el existente.                                                 |
| 2 | **Firewall bloqueaba creación de Functions** | Pusimos`networkAcls.defaultAction: Deny` en Storage. Azure necesita acceso al Storage para configurar las Functions.               | Cambiar a`defaultAction: Allow` + `bypass: AzureServices`. Esto permite que servicios autenticados de Azure accedan al Storage. NO significa acceso público. |
| 3 | **Managed Identity no propagada**             | Al asignar Managed Identity, Azure AD tarda segundos en propagarla. Si asignas un rol inmediatamente → error "principal not found". | `sleep 30` + loop de reintentos con 3 intentos (`for TRY in 1 2 3`).                                                                                          |
| 4 | **DeploymentActive en CI/CD**                 | GitHub Actions ejecuta deployments concurrentes. Azure bloquea deployments simultáneos al mismo Resource Group.                     | Usar`${{ github.run_id }}` en el nombre del deployment: `centinela-ci-${{ github.run_id }}`. Cada ejecución tiene un nombre único.                          |
| 5 | **App Insights duplicadas**                   | `az functionapp create` sin `--disable-app-insights` crea un App Insights automático por cada Function.                         | Agregar`--disable-app-insights` y configurar manualmente `appi-centinela-ufwhov` via App Settings.                                                            |
| 6 | **Recursos zombis en el portal**              | Del primer deploy quedaron 4 recursos huérfanos (func-api-...9335, func-scoring-...9335 + sus App Insights).                        | Limpieza manual:`az functionapp delete` para los viejos. Lección: siempre usar `--disable-app-insights`.                                                     |
| 7 | **RBAC no disponible para Service Principal** | El SP`sp-centinela-github` tiene rol Contributor pero NO tiene `Microsoft.Authorization/roleAssignments/write`                   | Las asignaciones de roles deben hacerse desde CLI con`az role assignment create`, no desde Bicep.                                                               |
| 8 | **KV soft-delete**                            | Al recrear el Resource Group, Key Vault queda en soft-delete y bloquea la recreación.                                               | Forzar purge:`az keyvault purge --name kv-centinela-...` o esperar 90 días.                                                                                    |

---

## 4. Glosario de Servicios Azure (qué hace cada uno)

| Servicio                       | Qué es                                                          | Para qué sirve                                                    | Costo                                    |
| ------------------------------ | ---------------------------------------------------------------- | ------------------------------------------------------------------ | ---------------------------------------- |
| **Resource Group**       | Contenedor lógico de recursos Azure                             | Agrupa, organiza costos, permite borrar todo junto                 | **$0**                             |
| **Function App**         | Servicio serverless que ejecuta código en respuesta a eventos   | Corre la API (FastAPI) y el motor de scoring (QueueTrigger)        | **$0** (1M ejecuciones/mes gratis) |
| **Consumption Plan**     | Plan de hosting que escala según demanda                        | Paga solo cuando el código se ejecuta, escala a 0 en inactividad  | **$0**                             |
| **Storage Account**      | Almacenamiento masivo con 4 servicios (Blob, Table, Queue, File) | Table → datos NoSQL, Queue → mensajería, Blob → documentos     | **~$1.50/mes**                     |
| **Table Storage**        | Base de datos NoSQL clave-valor                                  | Transacciones, casos, configuración                               | Incluido en Storage                      |
| **Queue Storage**        | Cola de mensajes simple                                          | Desacoplar API de scoring (productor-consumidor)                   | Incluido en Storage                      |
| **Blob Storage**         | Almacenamiento de objetos binarios                               | Documentos de verificación de identidad                           | Incluido en Storage                      |
| **Key Vault**            | Almacén seguro de secretos, claves y certificados               | Guarda StorageConnectionString y API Key                           | **~$0.10/mes**                     |
| **Application Insights** | Servicio APM (Application Performance Monitoring)                | Métricas de latencia, errores, throughput, trazas distribuidas    | **$0** (5GB/mes gratis)            |
| **Log Analytics**        | Almacén y motor de consultas de logs                            | Consultas KQL, dashboards, alertas                                 | **$0** (incluido con App Insights) |
| **App Service Plan**     | Plan de hosting para Functions/Web Apps                          | Define región, SO, escalado                                       | **$0** (se paga por ejecución)    |
| **Managed Identity**     | Identidad Azure AD para recursos Azure                           | Cada Function tiene su propia identidad sin gestionar credenciales | **$0**                             |
| **RBAC**                 | Control de acceso basado en roles                                | Permisos granulares: qué recurso puede acceder a qué             | **$0**                             |

---

## 5. Justificación de Decisiones Técnicas

### ¿Por qué NO usamos Máquinas Virtuales?

| Razón                  | Explicación                                                                                                                                                                                                         |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Costo**         | Una VM B1s (la más barata) = ~$8.76/mes + storage ~$2 =**$10.76/mes**. Funciones Consumption = **$0** por los primeros 1M ejecuciones. Con $200 de crédito y objetivo <$60, cada VM resta presupuesto. |
| **Mantenimiento** | VM requiere: parches de SO, actualizaciones de Python, monitoreo de disco, escalado manual. Functions se actualizan solas.                                                                                           |
| **Escalado**      | VM: una sola instancia, se satura en picos. Function Consumption: escala a cientos de instancias automáticamente.                                                                                                   |
| **Event-Driven**  | El motor de scoring necesita reaccionar a eventos (QueueTrigger). En VM tendrías que instalar y mantener un worker de colas. Functions lo tienen nativo.                                                            |
| **Desperdicio**   | VM paga 24/7 aunque no haya tráfico. Functions pagan solo cuando ejecutan código. El sistema pasa >90% del tiempo sin tráfico.                                                                                    |

**En resumen:** Serverless (Functions Consumption) es la opción correcta para cargas de trabajo event-driven con presupuesto ajustado. VM tendría sentido si necesitáramos control total del SO o cargas predecibles 24/7.

### ¿Por qué Table Storage y no SQL?

| Razón                  | Explicación                                                                                                                                                                                                               |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Costo**         | Table Storage cuesta ~$1/mes. SQL Database (S0) cuesta**$5-15/mes**. Table es 5-15× más barato.                                                                                                                    |
| **Datos simples** | Nuestros datos son clave-valor (transacciones, casos, configuración). No necesitamos joins, relaciones, stored procedures ni consultas complejas.                                                                         |
| **Performance**   | Table Storage tiene latencias de milisegundos para consultas por PartitionKey + RowKey. Nuestra consulta principal ("dame las transacciones recientes de esta cuenta") se resuelve con una sola consulta por PartitionKey. |
| **Escalabilidad** | Table Storage escala a terabytes sin cambiar código. No hay límite práctico de almacenamiento.                                                                                                                          |

**¿Cuándo usaríamos SQL?**

- Si necesitáramos relaciones complejas (ej: casos ↔ analistas ↔ resoluciones con joins)
- Si necesitáramos consultas ad-hoc complejas (ej: "todas las transacciones >$X del último mes agrupadas por comercio")
- Si tuviéramos presupuesto ilimitado

Para Centinela, Table Storage es la opción correcta y justificable.

### ¿Por qué Queue y no llamada directa?

| Razón                               | Explicación                                                                                                                                                                                                                               |
| ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **El cliente no espera**       | La API responde**202 Accepted** inmediatamente. Si llamáramos directo al scoring, el cliente esperaría mientras se procesa la transacción (segundos). En producción financiero, cada milisegundo cuenta.                         |
| **Tolerancia a fallos**        | Si func-scoring falla (error de código, timeout, etc.), el mensaje queda en la cola y se**reintenta automáticamente** hasta 5 veces. Si llamáramos directo, un error en scoring significaría que el cliente recibe un error 500. |
| **Manejo de picos**            | Queue actúa como buffer. Si llegan 10.000 transacciones en un minuto (pico), la cola las acumula y func-scoring las procesa al ritmo que pueda. Nadie se pierde.                                                                          |
| **Desacoplamiento de equipos** | El equipo de API y el equipo de scoring pueden desarrollar y desplegar independientemente. Mientras el contrato del mensaje en la cola se mantenga, cada lado puede cambiar su implementación.                                            |

### ¿Por qué NO usamos API Gateway ni API Management?

| Razón                                | Explicación                                                                                                                         |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Costo**                       | API Gateway (Azure Front Door, Azure API Management) costaría**$50-300+/mes**. Consumiría todo el crédito de $200 en días. |
| **FastAPI ya hace de gateway**  | FastAPI recibe requests, autentica, valida, enruta, hace rate-limiting. No necesitamos una capa adicional.                           |
| **Solo 1 API con 2 endpoints**  | POST transacciones y GET estado. No hay múltiples APIs que enrutar.                                                                 |
| **Portal para desarrolladores** | No tiene sentido — el único cliente es la fintech.                                                                                 |
| **Rate limiting + API Key**     | Ya lo manejamos en el middleware de FastAPI + Key Vault.                                                                             |

**Cómo responder al profesor:**

> No usamos API Gateway aparte porque diseñamos la API con FastAPI, que incluye validación, autenticación y rate limiting en el middleware. Agregar un servicio aparte como API Management costaría ~$50/mes mínimo, y nuestro presupuesto total es de $60 para todo el proyecto. La arquitectura serverless con una Function App como punto de entrada cumple el mismo rol sin costo adicional.

### ¿Por qué Functions por CLI y no por Bicep?

| Razón                                   | Explicación                                                                                                                                                                |
| ---------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Problema de quota en Free tier** | Azure Free tier tiene cuota:**1 App Service Plan por región**. Bicep/ARM intenta crear un nuevo Plan → error `SubscriptionIsOverQuotaForSku`.                     |
| **Solución**                      | `az functionapp create --consumption-plan-location westus`. Esto NO crea un nuevo plan, reusa el `WestUSLinuxDynamicPlan` existente.                                    |
| **Conclusión**                    | No es que no quisiéramos usar Bicep — es que el Free tier**no permite** crear más de un Consumption Plan por región, y Bicep/ARM siempre intenta crear uno nuevo. |

### ¿Por qué Managed Identity + RBAC en vez de claves?

| Razón                                   | Explicación                                                                                                                                                  |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Sin credenciales que gestionar** | Cada Function tiene su propia identidad Azure AD. No hay secretos que rotar, no hay credenciales en texto plano.                                              |
| **Roles granulares**               | Cada Function solo accede a lo que necesita: Storage Table Data Contributor, Queue Data Contributor, Key Vault Secrets User. Principio de mínimo privilegio. |
| **DefaultAzureCredential**         | El código usa`DefaultAzureCredential` — en Azure usa Managed Identity automáticamente, en local usa las credenciales de Azure CLI.                       |
| **Seguridad**                      | Si un secreto se sube a git, queda en el historial para siempre. Con Key Vault + Managed Identity, ningún secreto toca el código ni el repositorio.         |

### ¿Por qué JWT + cookies HttpOnly?

| Razón                          | Explicación                                                                                 |
| ------------------------------- | -------------------------------------------------------------------------------------------- |
| **JWT Stateless**         | No requiere sesión en servidor. Fácil de escalar horizontalmente.                          |
| **HttpOnly**              | La cookie no es accesible desde JavaScript → protección contra XSS (Cross-Site Scripting). |
| **Simple de implementar** | FastAPI + PyJWT. Decorador`@requires_role("admin")` para proteger endpoints por rol.       |
| **API Key**               | Para autenticación machine-to-machine (servicio a servicio), almacenada en Key Vault.       |

---

## 6. Seguridad

- **Managed Identity**: Cada Function App tiene su propia identidad en Azure AD. No se almacenan credenciales en código. En desarrollo local usa Azure CLI.
- **RBAC (6 roles asignados)**: Cada Function tiene Storage Table Data Contributor + Queue Data Contributor + Key Vault Secrets User. Principio de mínimo privilegio.
- **HTTPS forzado**: `az functionapp update --set httpsOnly=true`. TLS mínimo 1.2. Todo tráfico HTTP es redirigido automáticamente a HTTPS.
- **JWT + @requires_role**: Middleware de autenticación JWT con decorador por endpoint (`@requires_role("admin")`). Cookies HttpOnly (no accesibles desde JavaScript).
- **API Key en Key Vault**: Para autenticación machine-to-machine. Nunca aparece en código fuente, variables de entorno, ni logs. Rotación de claves sin cambiar código.
- **NetworkAcls en Storage**: `defaultAction: Allow` + `bypass: AzureServices`. Solo servicios autenticados de Azure pueden acceder al Storage. No es acceso público — requiere autenticación Azure AD.
- **Payload size limiter**: Middleware en FastAPI limita el tamaño máximo de payload. Protege contra ataques de denegación de servicio.

---

## 7. CI/CD

### Pipeline: `.github/workflows/ci.yml`

```yaml
on: push to main

jobs:
  lint:
    - flake8 (linting)
    - black --check (formato)

  deploy:
    - az login con Service Principal (sp-centinela-github)
    - az deployment group create --name centinela-ci-${{ github.run_id }}
    - bash infra/create-functions.sh
```

### Detalles importantes

| Elemento                       | Detalle                                                                |
| ------------------------------ | ---------------------------------------------------------------------- |
| **Disparador**           | Push a rama`main`                                                    |
| **Service Principal**    | `sp-centinela-github` con rol Contributor en rg-centinela            |
| **AZURE_CREDENTIALS**    | Secreto en GitHub Actions con el JSON del SP                           |
| **${{ github.run_id }}** | Evita error`DeploymentActive` — cada ejecución tiene nombre único |
| **Lint primero**         | Si el lint falla, no se despliega                                      |
| **Funciones**            | Se crean/actualizan via`create-functions.sh` (no por Bicep)          |

### Scripts versionados

| Script                        | Propósito                                       |
| ----------------------------- | ------------------------------------------------ |
| `infra/deploy.sh`           | Unificado: RG → Bicep → Functions              |
| `infra/create-functions.sh` | Crea Functions con MI, RBAC, HTTPS, App Settings |
| `infra/main.bicep`          | Define Storage, KV, Log Analytics, App Insights  |

Todo puede recrearse desde cero ejecutando:

```bash
bash infra/deploy.sh
```

---

## 8. Recorrido de una Transacción (paso a paso)

### Diagrama temporal

```
CLIENTE                    FUNC-API                QUEUE               FUNC-SCORING              TABLES
   │                         │                      │                      │                     │
   │──── POST /transaccion──►│                      │                      │                     │
   │◄──── 202 Accepted ──────│                      │                      │                     │
   │                         │───── mensaje ───────►│                      │                     │
   │                         │                      │───── trigger ──────►│                     │
   │                         │                      │                      │──── consulta ──────►│
   │                         │                      │                      │◄─── historial ──────│
   │                         │                      │                      │                     │
   │                         │                      │                      │─── aplica reglas ───│
   │                         │                      │                      │                     │
   │                         │                      │                      │── guarda score ────►│
   │                         │                      │                      │                     │
   │                         │                      │                      │── si > umbral ─────►│
   │                         │                      │                      │   crea caso         │
```

### Paso a paso detallado

**PASO 1: INGESTA**

```
Cliente → POST /transaccion → func-api
  • Llega una transacción: {cuenta, monto, ubicacion, comercio, timestamp}
  • API valida: JWT, API Key, payload size
  • Responde 202 Accepted (inmediato)
  • El cliente recibe respuesta y sigue con lo suyo
```

**PASO 2: PUBLICACIÓN DEL EVENTO**

```
func-api → Queue "transacciones-pendientes"
  • La transacción se publica como mensaje en la cola
  • Aquí termina la responsabilidad de la API
```

**PASO 3: SCORING (ASÍNCRONO)**

```
Queue → func-scoring (QueueTrigger)
  • El motor de scoring se activa automáticamente
  • Consulta Table "transacciones" para obtener historial reciente de la cuenta
  • Aplica las 4 reglas heurísticas:
    - Velocidad: ¿demasiadas transacciones en poco tiempo?
    - Monto atípico: ¿muy por encima del comportamiento histórico?
    - Ubicación imposible: ¿dos ubicaciones incompatibles en el tiempo?
    - Comercio de riesgo: ¿comercio o categoría marcada como sospechosa?
  • Cada regla suma puntos al score
  • Guarda el resultado en Table "transacciones" con detalle de por qué
```

**PASO 4: DECISIÓN**

```
  • Si score > umbral:
    - Se crea un caso en Table "casos"
    - Se genera explicación legible (plantilla determinista)
  • Si score ≤ umbral:
    - Solo queda registrado en transacciones
    - No se abre caso
```

**PASO 5: FRONTEND — EL ANALISTA REVISA**

```
  • Analista hace login (JWT, cookies HttpOnly)
  • Ve lista de casos abiertos en Dashboard
  • Abre detalle del caso:
    - Score y umbral
    - Explicación legible de cada regla disparada
    - Datos de la transacción
  • Decide: confirma fraude o descarta
  • Si escala: sube documento de verificación a Blob "verificaciones"
```

**PASO 6: AUDITORÍA**

```
  • Todo queda registrado: quién resolvió, cuándo, qué decisión
  • El auditor puede ver todo sin modificar nada
```

---

## 9. Código y Componentes

### Estructura del proyecto

```
centinela/
├── api/
│   ├── main.py            # FastAPI app + rutas frontend
│   ├── adapters.py         # Table/Queue adapters (connection string + DefaultAzureCredential)
│   ├── services.py         # TransactionService (accept + get, publica en queue)
│   ├── middleware.py       # JWT auth, @requires_role, payload limiter
│   └── admin.py           # Endpoints admin (umbral, reglas, comercios)
├── persistence/
│   └── repository.py      # TableStorage CRUD (table names lowercase para Azure)
├── rules/
│   └── reglas.py          # 4 reglas heurísticas de detección
├── frontend/
│   └── templates/         # Jinja2 templates
│       ├── base.html
│       ├── login.html
│       ├── casos.html     # Dashboard de casos
│       ├── detalle.html   # Detalle de caso + explicación
│       ├── admin.html     # Panel admin (reglas, umbral, comercios)
│       └── auditor.html   # Vista de solo lectura
├── function_app.py        # Azure Functions ASGI entry point
├── infra/
│   ├── main.bicep         # Bicep template
│   ├── deploy.sh          # Script unificado
│   └── create-functions.sh # Creación de Functions
└── .github/workflows/
    └── ci.yml             # CI/CD pipeline
```

### Componentes clave

| Componente                      | Archivo                       | Responsabilidad                                                                                                                      |
| ------------------------------- | ----------------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **FastAPI App**           | `api/main.py`               | Punto de entrada HTTP. Sirve frontend + API REST.                                                                                    |
| **Adapters**              | `api/adapters.py`           | Capa de acceso a Table Storage y Queue Storage. Soporta dos modos: connection string (local) y DefaultAzureCredential (Azure).       |
| **TransactionService**    | `api/services.py`           | Lógica de negocio: aceptar transacción, obtener transacción, publicar en cola.                                                    |
| **Middleware**            | `api/middleware.py`         | Autenticación JWT, decorador @requires_role, limitador de payload.                                                                  |
| **Admin**                 | `api/admin.py`              | CRUD de configuración: umbral de score, reglas, comercios de riesgo.                                                                |
| **Repository**            | `persistence/repository.py` | Patrón Repository sobre Table Storage. Operaciones CRUD genéricas. Nombres de tabla en minúsculas (requisito de Azure).           |
| **Reglas**                | `rules/reglas.py`           | 4 funciones de detección: velocidad, monto_atipico, ubicacion_imposible, comercio_riesgo. Cada una devuelve (puntos, explicación). |
| **Azure Functions entry** | `function_app.py`           | Conecta FastAPI con Azure Functions via`func.AsgiFunctionApp`.                                                                     |
| **Frontend**              | `frontend/templates/`       | 6 templates Jinja2 para las interfaces de usuario.                                                                                   |

### Lógica de las reglas de scoring

| Regla                          | Qué detecta                                                       | Cómo puntúa                                                                  |
| ------------------------------ | ------------------------------------------------------------------ | ------------------------------------------------------------------------------ |
| **Velocidad**            | Demasiadas transacciones desde la misma cuenta en poco tiempo      | +35 puntos si 8+ transacciones en 3 minutos                                    |
| **Monto atípico**       | Monto muy superior al comportamiento histórico de la cuenta       | +30 puntos si supera 10× el promedio histórico                               |
| **Ubicación imposible** | Dos transacciones desde ubicaciones geográficamente incompatibles | +17 puntos si no es posible viajar entre ubicaciones en el tiempo transcurrido |
| **Comercio de riesgo**   | Transacción hacia comercio o categoría marcada como sospechosa   | +25 puntos si el comercio está en la lista de riesgo                          |

El umbral configurable (default: 60) determina si se abre un caso. Si score > umbral → se crea caso.

---

## 10. Justificación Económica (tabla de costos)

### Costo mensual estimado

| Servicio             | SKU/Plan              | Costo estimado/mes                                          | Notas                                                         |
| -------------------- | --------------------- | ----------------------------------------------------------- | ------------------------------------------------------------- |
| Function Apps x2     | Consumption           | **$0**                                                | 1M ejecuciones gratis. Nuestro volumen está muy por debajo.  |
| Storage Account      | Standard_LRS          | **~$1.50**                                            | Table + Queue + Blob. Almacenamiento de pocos GB.             |
| Key Vault            | Standard              | **~$0.10**                                            | ~10k operaciones/mes.                                         |
| Application Insights | Pay-as-you-go         | **~$0**                                               | 5GB de ingesta de datos gratis/mes.                           |
| Log Analytics        | PerGB2018             | **~$0**                                               | Datos vienen de App Insights, sin costo adicional.            |
| App Service Plan     | Dynamic (Consumption) | **$0**                                                | No se paga el plan, se paga por ejecución (incluido arriba). |
| **Total**      |                       | **~$1.60/mes** | ✅ Muy por debajo del límite de $60 |                                                               |

### Comparación con alternativas

| Alternativa                | Costo/mes                                 | Por qué NO la usamos                                                  |
| -------------------------- | ----------------------------------------- | ---------------------------------------------------------------------- |
| VM B1s (Linux)             | $8.76 + storage $2 =**~$10.76/mes** | Paga 24/7, requiere mantenimiento, no escala. 7× más cara.           |
| SQL Database (S0)          | **~$5-15/mes**                      | No necesitamos relaciones ni joins. Table Storage alcanza.             |
| Cosmos DB (serverless)     | **~$24/mes mínimo**                | 15× más caro que Table Storage. Es overkill.                         |
| API Management (Developer) | **~$50/mes**                        | Consume todo el presupuesto en días. FastAPI ya cumple el rol.        |
| Service Bus (Basic)        | **~$10/mes**                        | Features que no necesitamos (topics, sesiones). Queue Storage alcanza. |
| Azure Front Door           | **~$35/mes**                        | CDN + WAF. No tenemos tráfico global que justifique el costo.         |

### Proyección para 30 días

| Escenario                     | Gasto estimado                     |
| ----------------------------- | ---------------------------------- |
| Uso normal (estimado)         | **~$1.60**                   |
| Uso intensivo (10× normal)   | **~$3-4**                    |
| Máximo posible (dejado 24/7) | **< $5**                     |
| **Crédito disponible** | **$200**                     |
| **Objetivo**            | **< $60** ✅ Vamos en ~$1.60 |
| **Margen**              | **> $195**                   |

Objetivo del proyecto: gastar <$60. Estamos en **~$1.60/mes**, 40× menos del límite.

---

## 11. Preguntas Frecuentes para la Evaluación

### "¿Por qué no usaron Máquinas Virtuales?"

**Respuesta:**
Usar VMs hubiera sido más caro y más trabajo por las siguientes razones:

1. **Costo**: Una VM B1s cuesta ~$8.76/mes + storage = **$10.76/mes**. Toda nuestra infraestructura actual cuesta **~$1.60/mes**. La VM sola es 7× más cara que todo el sistema.
2. **Mantenimiento**: Las VMs requieren parches de SO, actualizaciones de Python, monitoreo de disco. Las Functions se actualizan automáticamente.
3. **Escalado**: Una VM B1s es una sola instancia con 1 vCPU y 1 GB RAM. Si hay un pico de tráfico, se satura. Las Functions Consumption escalan automáticamente a cientos de instancias.
4. **Desperdicio**: Una VM paga 24/7 aunque no haya tráfico. Nuestro sistema pasa >90% del tiempo sin procesar transacciones. Functions pagan solo cuando ejecutan código.
5. **Event-Driven**: El motor de scoring necesita reaccionar a eventos de una cola. Con VM tendríamos que instalar y mantener un worker de colas. Functions tienen QueueTrigger nativo.

**Conclusión**: Serverless (Functions Consumption) es la opción correcta para cargas de trabajo event-driven con presupuesto ajustado. Una VM tendría sentido si necesitáramos control total del SO o cargas predecibles 24/7.

### "¿Qué es Application Insights y para qué sirve?"

**Respuesta:**
Application Insights es el servicio de **APM (Application Performance Monitoring)** de Azure. Es como un "GPS" para nuestro sistema — nos permite ver exactamente qué está pasando dentro de cada Function en tiempo real.

**¿Qué mide?**

- **Tiempo de respuesta** de cada request HTTP (latencia)
- **Tasa de error** (excepciones no controladas, HTTP 500)
- **Throughput** (cuántas transacciones por minuto)
- **Dependencias** (llamadas a Storage, Key Vault, cuánto tardan)
- **Trazas distribuidas** — sigue una transacción desde que entra por func-api hasta que func-scoring termina de procesarla

**¿Por qué lo necesitamos?**

- Si el sistema falla, alguien tiene que poder abrir una consola y ver **exactamente dónde y por qué**
- El profesor nos evalúa en entrega parcial — App Insights muestra que el sistema funciona
- Tiene **5GB de ingesta gratis por mes**, no nos cuesta nada

**Ejemplo de uso real:**

```kusto
// Buscar todas las solicitudes que tardaron más de 5 segundos
requests
| where duration > 5000
| project timestamp, name, duration, success, resultCode
```

### "¿Por qué Table Storage y no Cosmos DB?"

**Respuesta:**

1. **Costo**: Table Storage cuesta ~$1/mes. Cosmos DB cuesta **$24/mes mínimo** (serverless). SQL Database cuesta **$5-15/mes**. Table Storage es 15-24× más barato.
2. **Datos simples**: Nuestros datos son clave-valor (transacciones, casos, configuración). No necesitamos joins, relaciones, stored procedures, ni consultas complejas. Table Storage es perfecto para este tipo de datos.
3. **Performance**: Table Storage tiene latencias de milisegundos para consultas por PartitionKey + RowKey. Nuestra consulta principal ("dame las transacciones recientes de esta cuenta") se resuelve con una sola consulta por PartitionKey.
4. **Escalabilidad**: Table Storage escala a terabytes sin cambiar código. No hay límite práctico de almacenamiento.

**¿Cuándo usaríamos SQL/Cosmos?**

- Si necesitáramos relaciones complejas (ej: casos ↔ analistas ↔ resoluciones con joins)
- Si necesitáramos consultas ad-hoc complejas (ej: "todas las transacciones >$X del último mes agrupadas por comercio")
- Si tuviéramos presupuesto ilimitado

Para Centinela, Table Storage es la opción correcta y justificable.

### "¿Cómo escala el sistema?"

**Respuesta:**
El sistema escala de dos formas:

1. **func-api (HTTP)**: Azure Functions Consumption escala automáticamente el número de instancias según el número de requests HTTP entrantes. Si hay 100 requests simultáneas, Azure crea 100 instancias de nuestra API en segundos.
2. **func-scoring (Queue)**: Azure Functions con QueueTrigger escala según la longitud de la cola. Si hay 1000 mensajes en la cola, Azure crea suficientes instancias para procesarlos en paralelo. Cada mensaje se procesa al menos una vez.
3. **Storage Account**: Table Storage y Queue Storage escalan sin límite práctico. No hay que configurar nada — Azure maneja la partición automática.

**Límites conocidos:**

- Functions Consumption: 200 instancias máximas por Function App (no vamos a llegar ni cerca)
- Queue Storage: hasta 500 TB, 20.000 mensajes/segundo
- Table Storage: hasta 500 TB, 20.000 transacciones/segundo por partición

### "¿Dónde están los secretos?"

**Respuesta:**
Todos los secretos están en **Azure Key Vault** (`kv-centinela-ufwhov`):

- **StorageConnectionString**: cadena de conexión del Storage Account
- **API Key**: para autenticación machine-to-machine

**¿Cómo accede el código a los secretos?**

1. Cada Function App tiene una **Managed Identity** (identidad en Azure AD)
2. Esa identidad tiene rol **Key Vault Secrets User** (solo lectura de secretos)
3. El código usa `DefaultAzureCredential` que automáticamente usa la Managed Identity en Azure
4. En desarrollo local, usa las credenciales de Azure CLI

**¿Qué NO hacemos?**

- ❌ NO almacenamos secretos en variables de entorno
- ❌ NO hardcodeamos credenciales en el código
- ❌ NO commitiamos archivos .env
- ❌ NO usamos access keys directas en el código

**¿Por qué es importante?**
Si un secreto se sube a git, queda en el historial para siempre aunque lo borres después. Con Key Vault + Managed Identity, ningún secreto toca el código ni el repositorio.

### "¿Cómo levantan la infraestructura desde cero?"

**Respuesta:**
Ejecutamos un solo comando:

```bash
bash infra/deploy.sh
```

Ese script hace:

1. **Crea el Resource Group** `rg-centinela` si no existe
2. **Ejecuta Bicep** (`main.bicep`) que despliega: Storage Account (con tables, queue, blob container), Key Vault (con secreto StorageConnectionString), Log Analytics, Application Insights
3. **Ejecuta `create-functions.sh`** que: crea las 2 Function Apps con `--consumption-plan-location`, asigna Managed Identity a cada una, espera 30 segundos para propagación, asigna roles RBAC (Storage Table Data Contributor, Queue Data Contributor, Key Vault Secrets User), fuerza HTTPS, configura App Settings

Todo está versionado en el repositorio. Cualquier miembro del equipo puede recrear toda la infraestructura desde cero.

### "¿Y si se acaba el crédito?"

**Respuesta:**
El sistema cuesta **~$1.60/mes**. Tenemos **$200 de crédito**. Eso significa que podríamos dejar todo encendido 24/7 por **más de 10 años** antes de agotar el crédito.

| Escenario             | Gasto  | Del crédito de $200 |
| --------------------- | ------ | -------------------- |
| Uso normal (30 días) | ~$1.60 | 0.8%                 |
| Uso intensivo         | ~$4    | 2%                   |
| Peor caso posible     | ~$5    | 2.5%                 |

**Nuestro objetivo** era gastar menos de **$60**. Estamos usando ~$1.60 — **40× menos del límite**.

Además, la suscripción tiene **spending limit** habilitado. Si el crédito se agota, los servicios se deshabilitan automáticamente. Nadie va a recibir un cargo.

### "¿Por qué Bicep y no Terraform?"

**Respuesta:**
**Bicep**:

- DSL nativo de Azure, desarrollado por Microsoft
- No requiere backend de estado (no hay archivo .tfstate que gestionar)
- Se integra directamente con Azure Resource Manager
- Sintaxis más simple y legible que ARM JSON
- Compila a ARM templates

**Terraform**:

- Multi-cloud (Azure, AWS, GCP) — overkill si solo usamos Azure
- Requiere backend de estado (Storage Account o similar)
- Más complejo de configurar (proveedores, init, plan, apply)
- Mejor para equipos grandes o infraestructura multi-cloud

Para **9 recursos en un solo cloud**, Bicep es la herramienta correcta. Terraform agregaría complejidad sin beneficio. Si el proyecto creciera a 50+ recursos en múltiples nubes, Terraform sería la mejor opción.

### "¿Qué son los recursos zombis que aparecen en el portal?"

**Respuesta:**
Los recursos zombis son recursos **huérfanos** del primer intento de deploy:

- `func-api-1784119335` (Function + App Insights)
- `func-scoring-1784119335` (Function + App Insights)

**¿Por qué quedaron?**
En el primer deploy creamos las Functions **sin** `--disable-app-insights`. Azure automáticamente creó un Application Insights por cada Function. Cuando rectificamos y borramos el Resource Group para empezar de nuevo, esas App Insights quedaron porque estaban vinculadas al default workspace.

Luego en el segundo deploy (con `--disable-app-insights`), las nuevas Functions se configuraron para usar `appi-centinela-ufwhov` (la instancia principal creada por Bicep), pero las App Insights viejas siguen existiendo.

**¿Hay que limpiarlas?**
Sí, se pueden borrar con `az functionapp delete` y `az monitor app-insights component delete`. No afectan el funcionamiento del sistema, pero ensucian el portal.

**Lección aprendida**: Siempre usar `--disable-app-insights` y configurar manualmente la instancia principal de App Insights.

---

## 12. Explicaciones Técnicas a Fondo

### 12.1 Bicep (`infra/main.bicep`) — Recurso por Recurso

```bicep
param location string = 'westus'
param suffix string = substring(uniqueString(resourceGroup().id), 0, 6)
param storageName string = 'stcentinela${suffix}'
param kvName string = 'kv-centinela-${suffix}'
param appInsightsName string = 'appi-centinela-${suffix}'
```

**Parámetros de entrada:**

- `location`: Fijo en `westus` porque el Free tier solo permite ciertas regiones. West US está dentro de las permitidas.
- `suffix`: Genera un hash único de 6 caracteres basado en el ID del Resource Group. Esto asegura que los nombres sean **globalmente únicos** (Azure requiere nombres de Storage Account únicos en todo el mundo).
- Los nombres de los recursos se construyen con ese suffix: `stcentinela{hash}`, `kv-centinela-{hash}`, `appi-centinela-{hash}`.

---

**Recurso 1: Storage Account**

```bicep
resource storage 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: storageName
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    }
  }
}
```

**Propiedades explicadas:**

- `kind: 'StorageV2'`: La versión moderna de Storage Account. Soporta Table, Queue, Blob y File. La versión V1 era solo Blob.
- `sku: { name: 'Standard_LRS' }`: **Standard_LRS** = Standard (HDD normal, no SSD premium) + LRS (Locally Redundant Storage = 3 copias en el mismo datacenter). Es el SKU más barato. Si el datacenter se destruye, perdemos datos — pero para un proyecto académico con $200 de crédito es aceptable.
- `supportsHttpsTrafficOnly: true`: Rechaza conexiones HTTP, solo acepta HTTPS.
- `minimumTlsVersion: 'TLS1_2'`: Fija TLS 1.2 como mínimo (no acepta TLS 1.0 ni 1.1 que son inseguros).
- `networkAcls.defaultAction: 'Allow'`: Permite tráfico entrante por defecto. Inicialmente lo pusimos en `Deny` pero bloqueaba la creación de Functions. Combinado con `bypass: 'AzureServices'`, solo servicios autenticados de Azure pueden acceder.
- `bypass: 'AzureServices'`: Excepción para servicios Azure (incluyendo Functions) autenticados.

**Tablas de Storage:**

```bicep
resource tableTransacciones 'Microsoft.Storage/storageAccounts/tableServices/tables@2023-01-01' = {
  name: '${storageName}/default/transacciones'
  dependsOn: [storage]
}
```

Cada tabla sigue el patrón `{storageName}/default/{nombre}`. El `default` es el Table Service por defecto (cada Storage Account tiene uno). `dependsOn` asegura que la tabla se cree después del Storage Account.

- **transacciones**: Historial de transacciones con scores. Particionado por `account_id`.
- **casos**: Casos de fraude. Particionado por `case_id`.
- **configuracion**: Configuración del sistema (umbral, reglas, comercios). Particionado por `config_type`.

**Queue Storage:**

```bicep
resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-01-01' = {
  name: '${storageName}/default/transacciones-pendientes'
  dependsOn: [storage]
}
```

Una sola cola `transacciones-pendientes`. Es el canal de comunicación entre func-api y func-scoring.

**Blob Storage:**

```bicep
resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-01-01' = {
  name: '${storageName}/default/verificaciones'
  dependsOn: [storage]
}
```

Contenedor `verificaciones` para documentos PDF/imagen que suben los analistas.

---

**Recurso 2: Key Vault**

```bicep
resource keyVault 'Microsoft.KeyVault/vaults@2022-07-01' = {
  name: kvName
  location: location
  properties: {
    tenantId: subscription().tenantId
    sku: { name: 'standard', family: 'A' }
    enableRbacAuthorization: true
  }
}
```

**Propiedades explicadas:**

- `tenantId: subscription().tenantId`: Asocia el Key Vault al tenant de Azure AD de la suscripción.
- `sku: 'standard'`: SKU Standard (~$0.03 por 10k operaciones). El Premium cuesta ~$1/día y no lo necesitamos (no usamos HSM).
- `enableRbacAuthorization: true`: **Esta es una decisión clave**. En vez de usar **Access Policies** (el modelo viejo de KV donde asignabas permisos directamente en el vault), usamos **RBAC** (el modelo nuevo). Ventajas:
  - Unificado con el resto de Azure (Storage, Functions, etc. también usan RBAC)
  - Roles granulares: `Key Vault Secrets User` solo puede leer secretos
  - Gestionado desde IAM como cualquier otro recurso

**Secreto StorageConnectionString:**

```bicep
resource kvSecretStorageConn 'Microsoft.KeyVault/vaults/secrets@2022-07-01' = {
  name: '${kvName}/StorageConnectionString'
  properties: {
    value: 'DefaultEndpointsProtocol=https;AccountName=${storage.name};AccountKey=${listKeys(storage.id, '2023-01-01').keys[0].value};EndpointSuffix=core.windows.net'
  }
  dependsOn: [keyVault, storage]
}
```

- `listKeys()`: Función de ARM que obtiene las Access Keys del Storage Account. Esto se evalúa **en tiempo de deploy**, no en tiempo de ejecución.
- `keys[0].value`: Toma la primera key del Storage Account.
- **Importante**: Este secreto es el **plan de respaldo**. El plan principal es Managed Identity + RBAC. Si la MI falla, el código puede caer a connection string. El connection string está en KV precisamente para no tenerlo hardcodeado.

---

**Recurso 3: Log Analytics**

```bicep
resource logAnalytics 'Microsoft.OperationalInsights/workspaces@2022-10-01' = {
  name: 'log-centinela-${suffix}'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
  }
}
```

- `PerGB2018`: SKU que cobra **por GB ingerido**. Los primeros 5GB/mes son gratis para App Insights vinculado. Es el más barato para nuestro volumen.
- Log Analytics es el **almacén de datos** de App Insights. Sin este workspace, App Insights no puede guardar logs.

---

**Recurso 4: Application Insights**

```bicep
resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: appInsightsName
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logAnalytics.id
  }
}
```

- `kind: 'web'`: App Insights orientado a aplicaciones web/server-side. La otra opción sería `Node.js` o `java`.
- `Application_Type: 'web'`: Define el tipo de aplicación para los dashboards por defecto.
- `WorkspaceResourceId: logAnalytics.id`: **Vincula App Insights a Log Analytics**. Sin esto, App Insights usa almacenamiento clásico (limitado, sin consultas KQL completas). Vinculado a Log Analytics, puedes hacer consultas KQL avanzadas, retención configurable, y alertas.

---

### 12.2 Azure Functions — Qué son, Cómo Funcionan

**¿Qué es una Function App?**
Es un servicio de Azure que ejecuta código en respuesta a eventos sin que tengas que gestionar servidores. Subes tu código (Python, C#, JavaScript, etc.) y Azure lo ejecuta cuando ocurre un evento.

**¿Qué es un Trigger?**
Es el evento que "despierta" a la Function. Hay muchos tipos:

- **HTTP Trigger**: Se activa cuando recibe una request HTTP (GET, POST, etc.)
- **Queue Trigger**: Se activa cuando llega un mensaje a una cola de Storage
- Timer Trigger: Se activa en un horario (cron)
- Blob Trigger: Se activa cuando se sube un archivo a Blob Storage

**Nuestras 2 Functions:**

| Function               | Trigger | Puerto de entrada    | Qué hace                                                         |
| ---------------------- | ------- | -------------------- | ----------------------------------------------------------------- |
| **func-api**     | HTTP    | Público (internet)  | Recibe transacciones POST, responde 202, publica en cola          |
| **func-scoring** | Queue   | Privado (solo Azure) | Reacciona a mensajes en la cola, aplica reglas, guarda resultados |

**¿Por qué 2 Functions separadas y no 1 sola?**

Razones:

1. **Escalado independiente**: En picos de tráfico, func-api escala según requests HTTP. func-scoring escala según profundidad de la cola. Si hubiera una sola Function, ambas cargas competirían.
2. **Seguridad**: func-api tiene una URL pública (expuesta a internet). func-scoring es interna (solo Azure puede invocarla via Queue). Separarlas reduce la superficie de ataque.
3. **Desacoplamiento**: El equipo de API puede deployar cambios sin afectar al motor de scoring y viceversa.
4. **Costos**: Cada una tiene su propio límite de 1M ejecuciones gratis. Si combinamos todo en una, consumimos el límite más rápido.

**¿Qué es Consumption Plan?**

El **Consumption Plan** es el plan de hosting más barato de Azure Functions:

- **No pagas por el plan**, pagas por **ejecución y tiempo de CPU**
- **1 millón de ejecuciones gratis por mes** por Function App
- **Escala a 0**: Si no hay tráfico, no hay instancias corriendo → no hay costo
- **Escala automáticamente**: Si hay pico, Azure crea instancias (hasta 200)
- **Timeout**: 5 minutos por ejecución (suficiente para nuestro scoring)
- **Memoria**: 1.5 GB máximo por instancia

Alternativas (más caras):

- **App Service Plan (Dedicated)**: Paga por las VMs 24/7 (~$13+/mes). No lo necesitamos.
- **Premium Plan**: Arranque en frío más rápido, VNET integración (~$40+/mes). No lo necesitamos.

**Ciclo de vida de un request en func-api:**

```
1. Fintech hace POST a https://func-api-1784119485.azurewebsites.net/api/transaccion
2. Azure Functions runtime recibe el request HTTP
3. El runtime busca la función con HTTP trigger en nuestro código
4. Ejecuta FastAPI (ASGI) que procesa el request
5. FastAPI valida JWT, API Key, payload
6. Publica mensaje en cola Storage
7. Responde 202 al cliente (todo tomó ~50ms)
```

**Ciclo de vida de un mensaje en func-scoring:**

```
1. Un mensaje aparece en la cola "transacciones-pendientes"
2. Azure Functions runtime detecta el mensaje (polling cada ~100ms)
3. El runtime bloquea el mensaje (invisible por 30s)
4. Ejecuta la función con QueueTrigger
5. La función consulta Table Storage, aplica reglas, guarda resultado
6. Si todo ok → el mensaje se elimina de la cola
7. Si falla → el mensaje se desbloquea y se reintenta (hasta 5 veces)
8. Después de 5 intentos fallidos → el mensaje va a la cola "poison" (para depuración)
```

**El suffijo numérico en los nombres (`1784119485`):**
En `create-functions.sh` se genera con `SUFFIX=$(date +%s)` (timestamp Unix). Esto asegura que el nombre de la Function sea único globalmente. Azure Functions requiere nombres globalmente únicos porque `func-api-XXXX.azurewebsites.net` es un dominio público.

---

### 12.3 `create-functions.sh` — Explicación Línea por Línea

**1. `az functionapp create --consumption-plan-location $LOCATION`**

¿Qué hace exactamente?

- Le dice a Azure: "crea una Function App en la región $LOCATION, pero no me crees un nuevo App Service Plan, reusa el existente o créalo implícitamente"
- Normalmente, el comando completo sería: `az functionapp create --plan <plan-name> --storage-account <storage>`
- Pero en Free tier, no puedes crear un nuevo plan via ARM/Bicep (quota: 1 ASP por región)
- `--consumption-plan-location` es el workaround oficial de Microsoft

¿Qué pasa si usáramos `--plan`?

- Si el plan `WestUSLinuxDynamicPlan` ya existe, funciona
- Si NO existe, falla porque Bicep no puede crearlo
- `--consumption-plan-location` lo crea implícitamente sin pasar por ARM

**2. `--disable-app-insights`**

¿Qué hace exactamente?

- Por defecto, `az functionapp create` ejecuta estos pasos extra:
  1. Crea un recurso Application Insights con nombre `{function-name}-insights`
  2. Configura automáticamente `APPINSIGHTS_INSTRUMENTATIONKEY` en App Settings
- Con `--disable-app-insights`, saltamos esos pasos
- ¿Por qué?: Ya tenemos `appi-centinela-ufwhov` creado por Bicep. Queremos que TODAS las Functions usen la MISMA instancia de App Insights, no una por Function.

**3. `az functionapp identity assign`**

¿Qué hace?

- Crea una **System-Assigned Managed Identity** en Azure AD para la Function App
- Azure AD crea un Service Principal automáticamente con el mismo nombre que la Function
- La Function ahora tiene una identidad: `{app-id}` en Azure AD
- Esta identidad NO tiene permisos por defecto — hay que asignárselos con RBAC

¿Qué es System-Assigned vs User-Assigned?

- **System-Assigned**: Se crea y destruye con el recurso. Unicidad: 1 identidad por recurso. Más simple.
- **User-Assigned**: Se crea aparte y se asigna a múltiples recursos. Útil cuando varios recursos necesitan la MISMA identidad.
- Nosotros usamos System-Assigned porque cada Function necesita diferentes permisos.

**4. `sleep 30` — ¿Por qué 30 segundos?**

Cuando ejecutas `az functionapp identity assign`, Azure AD necesita:

1. Crear el Service Principal en el tenant
2. Propagar la creación a todos los servidores de Azure AD
3. El sistema de RBAC necesita poder resolver el principal ID

Azure AD es un sistema **eventualmente consistente**. No hay garantía de que el principal esté disponible inmediatamente después de crearlo. Si ejecutas `az role assignment create` inmediatamente, obtienes:

```
PrincipalNotFound: Principal <principal-id> does not exist in the directory
```

`sleep 30` es un valor empírico — después de pruebas, 30 segundos fue suficiente para que Azure AD propague la identidad en nuestra suscripción. En algunos casos puede necesitar más tiempo (por eso el retry loop).

**5. Retry Loop — `for TRY in 1 2 3`**

```bash
for TRY in 1 2 3; do
  az role assignment create --assignee $PRINCIPAL --role "$ROLE" --scope $STORAGE_ID 2>/dev/null && break
  echo "  Reintentando role $ROLE en $TRY seg... ($PRINCIPAL)"
  sleep $TRY
done
```

¿Por qué reintentos?

- La propagación de la identidad en Azure AD no es instantánea
- Si falla en el intento 1 (sleep 1s), reintenta en el 2 (sleep 2s), luego en el 3 (sleep 3s)
- `&& break` detiene el loop si el comando fue exitoso
- `2>/dev/null` oculta errores esperados (como PrincipalNotFound temporal)
- Después de 3 intentos (~6 segundos total), si sigue fallando, el script se detiene con error (por `set -euo pipefail`)

**6. `az functionapp update --set httpsOnly=true`**

¿Qué hace?

- Modifica la configuración de la Function App para rechazar tráfico HTTP
- Cualquier request a `http://...` recibe un redirect 301 a `https://...`
- NOTA: Se usa `az functionapp update --set`, NO `az functionapp config set`. Son comandos diferentes:
  - `az functionapp config set` configura el runtime (Python version, etc.)
  - `az functionapp update --set` modifica propiedades ARM directamente
  - `httpsOnly` es una propiedad ARM, no de configuración del runtime

**7. `az functionapp config appsettings set`**

Configura variables de entorno que el código puede leer:

- `AZURE_STORAGE_ACCOUNT=stcentinelaufwhov`: Nombre del Storage Account (lo necesita DefaultAzureCredential)
- `KEY_VAULT_URI=https://kv-centinela-ufwhov.vault.azure.net`: URI del Key Vault (para leer secretos)
- `AzureWebJobsStorage__accountName=stcentinelaufwhov`: Configuración interna de Azure Functions para usar el Storage Account como backend
- `APPINSIGHTS_INSTRUMENTATIONKEY=...`: Key de Application Insights para telemetría
- `APPLICATIONINSIGHTS_CONNECTION_STRING=...`: Connection string completo de App Insights

---

### 12.4 Managed Identity a Fondo

**¿Qué es una Managed Identity?**

Es una **identidad de Azure AD** que se asigna automáticamente a un recurso de Azure (Function, VM, App Service, etc.). Es como un "usuario" para máquinas.

**¿Cómo funciona?**

```
Código en la Function
       │
       ▼
DefaultAzureCredential
       │
       ├── En Azure: Detecta automáticamente la Managed Identity
       │   └── Pide token a Azure Instance Metadata Service (IMDS)
       │       └── Azure AD devuelve un token JWT
       │           └── El token se usa para autenticar contra Storage/KV
       │
       └── En local: Usa Azure CLI, VS Code, o PowerShell
           └── Sin configuración adicional
```

**¿Por qué es más seguro que Access Keys?**

| Aspecto                  | Access Keys                                                    | Managed Identity                                                        |
| ------------------------ | -------------------------------------------------------------- | ----------------------------------------------------------------------- |
| **Almacenamiento** | En variables de entorno o código                              | No se almacena nada — Azure lo gestiona                                |
| **Rotación**      | Manual (regenerar key, actualizar config)                      | Automática (Azure rota los certificados internamente)                  |
| **Permisos**       | Toda la cuenta de Storage (lectura + escritura + eliminación) | Granular por rol (solo Table, solo Queue, solo KV)                      |
| **Exposición**    | Si alguien obtiene la key, tiene acceso total                  | Si alguien obtiene acceso a la Function, solo tiene los roles asignados |
| **Git**            | Puede terminar en un commit por error                          | Nunca aparece en código                                                |

**¿Qué hace `DefaultAzureCredential`?**

Es una clase de la librería `azure-identity` que intenta autenticarse en este orden:

1. **EnvironmentCredential**: Lee variables de entorno `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET`
2. **ManagedIdentityCredential**: Llama al endpoint IMDS de Azure (solo funciona dentro de Azure)
3. **AzureCliCredential**: Usa la sesión de `az login` (para desarrollo local)
4. **VisualStudioCredential**: Usa la sesión de VS Code
5. **...otros**: PowerShell, InteractiveBrowser, etc.

En Azure, el paso 2 (ManagedIdentityCredential) siempre funciona porque IMDS está disponible. En local, usa Azure CLI (paso 3) si hiciste `az login`.

**El problema del sleep 30 explicado técnicamente:**

Cuando ejecutas `az functionapp identity assign`:

1. ARM (Azure Resource Manager) recibe la solicitud
2. ARM llama a Azure AD Graph API para crear el Service Principal
3. Azure AD crea el principal y lo marca como disponible
4. ARM actualiza el resource provider de la Function con el principal ID
5. El principal se replica a todas las particiones de Azure AD (esto toma tiempo)

Cuando ejecutas `az role assignment create`:

1. ARM recibe la solicitud
2. ARM llama a Azure AD para verificar que el principal existe
3. Si el principal no se ha replicado a la partición que consulta ARM → **PrincipalNotFound**
4. Si el principal existe → ARM procede a crear la asignación de rol

El `sleep 30` da tiempo para que la replicación de Azure AD complete antes de que ARM intente verificar el principal.

---

### 12.5 RBAC a Fondo

**¿Qué es RBAC?**

Role-Based Access Control — control de acceso basado en roles. Es el sistema de autorización de Azure. Define **quién** (sujeto) puede hacer **qué** (acción) sobre **qué recurso** (alcance).

**Componentes de RBAC:**

1. **Security Principal**: La identidad (usuario, grupo, Service Principal, Managed Identity)
2. **Role Definition**: Conjunto de permisos (Storage Table Data Contributor, Key Vault Secrets User, etc.)
3. **Scope**: El recurso sobre el que se aplica (/subscriptions/{sub}/resourceGroups/{rg}/...)

**Nuestras 6 asignaciones de rol:**

| Function     | Rol                            | Scope                                                    |
| ------------ | ------------------------------ | -------------------------------------------------------- |
| func-api     | Storage Table Data Contributor | `/subscriptions/.../storageAccounts/stcentinelaufwhov` |
| func-api     | Storage Queue Data Contributor | `/subscriptions/.../storageAccounts/stcentinelaufwhov` |
| func-api     | Key Vault Secrets User         | `/subscriptions/.../vaults/kv-centinela-ufwhov`        |
| func-scoring | Storage Table Data Contributor | `/subscriptions/.../storageAccounts/stcentinelaufwhov` |
| func-scoring | Storage Queue Data Contributor | `/subscriptions/.../storageAccounts/stcentinelaufwhov` |
| func-scoring | Key Vault Secrets User         | `/subscriptions/.../vaults/kv-centinela-ufwhov`        |

**¿Qué permite cada rol?**

| Rol                                      | Acciones que permite                                                                                           |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Storage Table Data Contributor** | Leer, escribir, eliminar datos en Table Storage. NO permite leer Access Keys, ni modificar el Storage Account. |
| **Storage Queue Data Contributor** | Leer, escribir, eliminar mensajes en Queue Storage. NO permite gestionar la cola (crear/eliminar).             |
| **Key Vault Secrets User**         | Leer secretos de Key Vault. NO permite crear, modificar, eliminar secretos ni gestionar el vault.              |

**¿Por qué no usamos roles a nivel de Resource Group?**

Podríamos asignar "Storage Table Data Contributor" a nivel del RG, pero eso le daría permiso a la Function sobre TODAS las tablas de TODOS los Storage Accounts del RG. Al asignar a nivel del **Storage Account específico**, limitamos el alcance (principio de mínimo privilegio).

**La limitación de `sp-centinela-github`:**

El Service Principal `sp-centinela-github` tiene rol **Contributor** en el Resource Group. Contributor permite:

- ✅ Leer, crear, modificar, eliminar recursos
- ✅ Asignar roles a otros principals (SI el SP tiene `Microsoft.Authorization/roleAssignments/write`)
- ❌ Contributor NO incluye `Microsoft.Authorization/roleAssignments/write`

Por eso las asignaciones de RBAC se hacen desde CLI con `az role assignment create`, no desde Bicep. El usuario que ejecuta el script (Valentina) tiene permisos de Owner (por ser la creadora de la suscripción), y Owner sí puede asignar roles.

---

### 12.6 Service Principal — Qué es y Cómo Funciona en CI/CD

**¿Qué es un Service Principal?**

Es una **identidad para aplicaciones o automatizaciones** en Azure AD. Mientras un "usuario" representa a una persona, un Service Principal representa a una aplicación o script que necesita autenticarse contra Azure.

**¿Cómo se creó?**

```bash
az ad sp create-for-rbac --name sp-centinela-github --role Contributor --scopes /subscriptions/.../resourceGroups/rg-centinela
```

Este comando:

1. Crea un Service Principal llamado `sp-centinela-github`
2. Le asigna rol **Contributor** en el Resource Group `rg-centinela`
3. Devuelve un JSON con las credenciales:

```json
{
  "clientId": "xxx-xxx-xxx",
  "clientSecret": "yyy-yyy-yyy",
  "tenantId": "zzz-zzz-zzz",
  "subscriptionId": "www-www-www"
}
```

**¿Cómo se usa en GitHub Actions?**

```yaml
- name: Azure Login
  uses: azure/login@v1
  with:
    creds: ${{ secrets.AZURE_CREDENTIALS }}
```

- `AZURE_CREDENTIALS` es un **secreto** en GitHub Actions que contiene el JSON completo
- `azure/login` usa esas credenciales para hacer `az login --service-principal`
- A partir de ahí, todos los comandos `az` en el pipeline se autentican como ese SP

**¿Por qué no usar las credenciales de una persona?**

- Si la persona deja la empresa, las credenciales dejan de funcionar
- Las contraseñas de persona expiran cada 90 días
- Una persona tiene más permisos de los necesarios
- Un SP tiene exactamente los permisos que necesita, nada más

**¿Qué puede hacer `sp-centinela-github`?**

- ✅ Crear y modificar recursos en `rg-centinela` (por el rol Contributor)
- ✅ Ejecutar `az deployment group create`
- ✅ Ejecutar `az functionapp create` y comandos relacionados
- ❌ NO puede asignar roles RBAC (no tiene `roleAssignments/write`)
- ❌ NO puede modificar recursos fuera de `rg-centinela`
- ❌ NO puede eliminar el Resource Group

---

### 12.7 Firewall Storage a Fondo

**¿Qué es Network ACLs en Storage?**

Es el firewall integrado del Storage Account. Controla qué tráfico de red puede llegar al Storage Account.

**Propiedades:**

```bicep
networkAcls: {
  defaultAction: 'Allow'  # o 'Deny'
  bypass: 'AzureServices'  # qué servicios pueden saltarse el firewall
  ipRules: []              # IPs específicas permitidas
  virtualNetworkRules: []  # VNets específicas permitidas
}
```

**`defaultAction: 'Deny'`** — el enfoque más seguro:

- Solo tráfico de IPs explícitamente permitidas (ipRules) y servicios en bypass puede acceder
- Todo lo demás es rechazado con 403
- **Problema**: Al crear una Function App, Azure necesita:
  1. Configurar el Storage Account como backend de la Function
  2. Esto requiere acceso a Table, Queue y Blob desde la infraestructura de Azure
  3. Si el firewall está en Deny y la IP de la infraestructura de Azure no está en ipRules → bloquea

**`defaultAction: 'Allow'` + `bypass: 'AzureServices'`:**

- Permite tráfico de **servicios Azure autenticados** (Functions, Azure DevOps, etc.)
- NO permite tráfico de internet público sin autenticación
- NO significa "acceso público" — sigue requiriendo autenticación Azure AD o Access Key
- `bypass: 'AzureServices'` es una lista de servicios de confianza: Azure Functions, Azure DevOps, Azure Backup, etc.

**¿Es inseguro `Allow`?**
No, porque:

1. Para acceder a los datos necesitas autenticarte (Managed Identity, Access Key, SAS)
2. El tráfico solo es aceptado en los puertos de Azure Storage (blob, queue, table, file)
3. No es un servidor web público — es un endpoint de Storage que habla el protocolo de Storage
4. Sin una clave válida o token, no puedes leer ni escribir datos

**¿Por qué no pusimos IP rules?**

Podríamos haber puesto las IPs de salida de las Functions en `ipRules`, pero:

- Las Functions Consumption tienen un rango de IPs de salida que puede cambiar
- Azure no publica las IPs exactas de antemano
- Habría que estar actualizando las IP rules constantemente
- `bypass: AzureServices` es más simple y cubre el mismo caso de uso

---

### 12.8 Problemas Resueltos — Explicación Detallada

#### Problema 1: SubscriptionIsOverQuotaForSku

**Contexto técnico:**

- Azure Free tier tiene una cuota de **1 App Service Plan por región**.
- App Service Plan es el contenedor de "compute" donde corren las Functions.
- Bicep/ARM intenta crear un nuevo App Service Plan para cada Function.
- Si ya existe uno (WestUSLinuxDynamicPlan del intento anterior), la cuota está usada.
- El error `SubscriptionIsOverQuotaForSku` significa: "ya alcanzaste el límite de planes de este SKU en esta región".

**¿Por qué Free tier tiene esta limitación?**
Para evitar que uses recursos ilimitados gratis. La cuota es una restricción de la suscripción gratuita.

**Solución a fondo:**

```bash
az functionapp create \
  --consumption-plan-location westus \
  --storage-account stcentinelaufwhov \
  --runtime python \
  --runtime-version 3.11 \
  --os-type Linux \
  --functions-version 4
```

El flag `--consumption-plan-location` le dice a Azure: "no me crees un plan nuevo, usá el plan de Consumption de la región westus". Si no existe, Azure lo crea implícitamente SIN pasar por ARM (y sin contar para la cuota de ARM).

#### Problema 2: Firewall bloqueaba creación de Functions

**Síntoma:**

```bash
az functionapp create ... --storage-account stcentinelaufwhov
# Error: Storage account 'stcentinelaufwhov' cannot be accessed.
# The storage account firewall settings are blocking the request.
```

**Causa raíz:**
Para crear una Function App, Azure necesita:

1. Crear contenedores internos en Blob Storage (para el runtime)
2. Crear tablas internas en Table Storage (para las configuraciones)
3. Verificar que el Storage Account existe y es accesible

Con `defaultAction: Deny`, el firewall bloquea estas operaciones porque la infraestructura de Azure Functions NO pasa por el bypass de AzureServices durante la creación (solo durante la ejecución).

**Solución:**
Cambiar a `defaultAction: Allow` con `bypass: AzureServices`. Las Functions pueden acceder al Storage durante la creación y durante la ejecución.

#### Problema 3: Managed Identity no propagada

**Síntoma:**

```bash
az role assignment create --assignee <principal-id> --role "Storage Table Data Contributor"
# Error: Principal <principal-id> does not exist in the directory.
```

**Causa raíz:**
Azure AD es un sistema distribuido globalmente. Cuando creas un Service Principal (Managed Identity), la creación ocurre en una partición, pero la replicación a todas las particiones puede tomar segundos. ARM (que hace la verificación del principal) puede estar consultando una partición diferente.

**¿Por qué 30 segundos?**
Empíricamente determinamos que 30s es suficiente para nuestra suscripción y región. En otras regiones o suscripciones puede ser diferente. El retry loop con 1s, 2s, 3s cubre casos donde la replicación es más rápida.

**¿Por qué no usar `az role assignment create` con `--assignee-object-id` directamente?**
Porque necesitamos el objectId de la Managed Identity, que se obtiene de `az functionapp identity show`. Y ese comando también puede fallar si la identidad no está propagada. El sleep está entre `identity assign` y `identity show`.

#### Problema 4: DeploymentActive en CI/CD

**Síntoma:**

```
ERROR: Deployment 'centinela-ci' is active and cannot be overwritten.
```

**Causa raíz:**
Azure Resource Manager permite solo **un deployment activo por Resource Group a la vez**. Si haces push dos veces seguidas al repo (dos ejecuciones de GitHub Actions), ambas intentan hacer `az deployment group create` al mismo RG. La segunda encuentra que la primera sigue activa y falla.

**Solución:**
`--name centinela-ci-${{ github.run_id }}`. `github.run_id` es único para cada ejecución de Actions. Así cada deployment tiene un nombre diferente y no hay conflicto.

**¿Por qué no usar un nombre fijo y esperar?**
Porque si el primer deployment tarda 2 minutos y el segundo push ocurre a los 30 segundos, la segunda ejecución esperaría bloqueada 1.5 minutos. Con nombres únicos, ambas pueden ejecutarse en paralelo sin problema.

#### Problema 5: App Insights duplicadas

**Síntoma:**
En el portal aparecen múltiples recursos de Application Insights:

- `appi-centinela-ufwhov` (la nuestra)
- `func-api-1784119335-insights` (automática)
- `func-scoring-1784119335-insights` (automática)

**Causa raíz:**
`az functionapp create` sin `--disable-app-insights` ejecuta automáticamente:

```bash
az monitor app-insights component create --app <function-name> --resource-group <rg>
az functionapp config appsettings set --settings APPINSIGHTS_INSTRUMENTATIONKEY=<key>
```

Azure no sabe que ya tenemos una instancia de App Insights — simplemente crea una nueva para cada Function.

**¿Por qué es malo?**

- Recursos zombis que ensucian el portal
- Cada App Insights tiene su propio límite de 5GB gratis, pero los datos de la Function van a su propia instancia, no a la principal
- Si miramos la instancia principal, no vemos los datos de las Functions

**Solución:**
`--disable-app-insights` + configuración manual: todas las Functions apuntan a `appi-centinela-ufwhov`.

#### Problema 6: Recursos Zombis

Los 4 recursos zombis del portal (`func-api-1784119335`, `func-scoring-1784119335` + sus App Insights) quedaron del primer deploy porque:

1. Primer deploy: creamos Functions SIN `--disable-app-insights` → se crearon App Insights automáticas
2. Borramos el Resource Group para empezar de nuevo
3. Las App Insights no se borraron porque estaban en "soft-delete" (protegidas)
4. Segundo deploy: creamos Functions CON `--disable-app-insights`, apuntando a la instancia principal
5. Las App Insights viejas quedaron huérfanas

Se pueden limpiar con:

```bash
az functionapp delete --name func-api-1784119335 -g rg-centinela
az functionapp delete --name func-scoring-1784119335 -g rg-centinela
```

#### Problema 7: RBAC no disponible para Service Principal

**Contexto:**
En Bicep se pueden asignar roles con:

```bicep
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(...)
  properties: {
    principalId: <managed-identity-id>
    roleDefinitionId: <role-id>
    principalType: 'ServicePrincipal'
  }
}
```

**Problema:**
Esto requiere que el principal que ejecuta el deployment tenga `Microsoft.Authorization/roleAssignments/write`. El Service Principal `sp-centinela-github` tiene rol Contributor, que **no incluye** ese permiso.

**Solución:**
Ejecutar `az role assignment create` desde CLI **después** del Bicep. El usuario que ejecuta el script tiene permisos de Owner (por ser el creador de la suscripción), y Owner sí incluye `roleAssignments/write`.

#### Problema 8: KV soft-delete

**Contexto:**
Key Vault tiene soft-delete habilitado por defecto. Cuando borras un KV (incluso borrando el Resource Group), el KV no se elimina realmente — entra en estado "soft-deleted" por 90 días.

**Síntoma:**

```bash
az deployment group create --template-file main.bicep
# Error: Key Vault 'kv-centinela-ufwhov' already exists in soft-deleted state.
```

**Solución:**

```bash
az keyvault purge --name kv-centinela-ufwhov
```

**¿Cómo evitarlo?**
Se puede deshabilitar soft-delete con `--enable-soft-delete false` al crear el KV, pero Microsoft recomienda mantenerlo activado por seguridad. Para desarrollo, es más práctico hacer purge manual cuando sea necesario.

---

## Apéndice A: Resumen del Estado del Proyecto

### Completado

| Área                                                             | Estado |
| ----------------------------------------------------------------- | ------ |
| Cuenta Azure + Service Principal                                  | ✅     |
| Bicep (Storage, KV, App Insights, Log Analytics)                  | ✅     |
| Functions creadas vía CLI                                        | ✅     |
| Managed Identity + RBAC (6 roles)                                 | ✅     |
| HTTPS forzado                                                     | ✅     |
| App Settings configuradas                                         | ✅     |
| deploy.sh unificado + probado desde cero                          | ✅     |
| create-functions.sh (con retry loop)                              | ✅     |
| CI/CD (lint + deploy automático)                                 | ✅     |
| Documentación (README, proyecto, requisitos, contributing)       | ✅     |
| PRs mergeados (Jesús frontend, Daniel API, Brallan persistencia) | ✅     |
| Issues organizados para Week 2-3                                  | ✅     |

### En progreso

- Coordinación de issues para Week 2-3
- Motor de scoring (QueueTrigger funcional)
- Tests unitarios
- Dashboards de App Insights

---

## Apéndice B: Comandos Azure útiles

```bash
# Listar recursos en el RG
az resource list -g rg-centinela -o table

# Ver logs de una Function
az functionapp log tail --name func-api-1784119485 -g rg-centinela

# Ver App Settings
az functionapp config appsettings list --name func-api-1784119485 -g rg-centinela -o table

# Forzar HTTPS (ya aplicado)
az functionapp update --name func-api-1784119485 -g rg-centinela --set httpsOnly=true

# Purge Key Vault (después de borrar RG)
az keyvault purge --name kv-centinela-ufwhov
```

### Variables de entorno configuradas en Functions

```
AZURE_STORAGE_ACCOUNT=stcentinelaufwhov
KEY_VAULT_URI=https://kv-centinela-ufwhov.vault.azure.net
AzureWebJobsStorage__accountName=stcentinelaufwhov
APPINSIGHTS_INSTRUMENTATIONKEY=<key>
APPLICATIONINSIGHTS_CONNECTION_STRING=InstrumentationKey=<key>
```

---

> **Documento de estudio — Centinela**
> Incluye todo lo discutido y construido durante el proyecto.
> Última actualización: Julio 2026
