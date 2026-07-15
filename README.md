# Centinela

**Motor de detección de fraude transaccional en tiempo real.**

Cada vez que un cliente de la fintech hace una compra, transferencia o retiro, Centinela analiza la transacción, aplica reglas de riesgo, asigna un puntaje y decide si es sospechosa.

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| API | Python 3.11 + FastAPI sobre Azure Functions HTTP trigger |
| Backend serverless | Azure Functions (Consumption Plan Linux) |
| Cola de mensajes | Azure Queue Storage |
| Base de datos | Azure Table Storage (NoSQL, particionado por cuenta) |
| Documentos | Azure Blob Storage |
| Secretos | Azure Key Vault + Managed Identity |
| Monitoreo | Application Insights |
| Infraestructura | Bicep + Azure CLI |
| Frontend | Jinja2 templates (HTML + CSS, sin framework JS) |
| CI/CD | GitHub Actions |

---

## Arquitectura

```
                    ┌──────────────┐
                    │   Cliente    │
                    │  (Fintech)   │
                    └──────┬───────┘
                           │ POST /api/transacciones
                           ▼
              ┌──────────────────────────┐
              │  func-api (FastAPI)      │
              │  Valida con Pydantic     │
              │  Responde 202 Accepted   │
              │  Encola mensaje          │
              └──────────┬───────────────┘
                         │
                         ▼
              ┌──────────────────────────┐
              │  Queue: transacciones-   │
              │         pendientes       │
              └──────────┬───────────────┘
                         │ QueueTrigger
                         ▼
              ┌──────────────────────────┐
              │  func-scoring            │
              │  Regla: velocidad        │
              │  Regla: monto atípico    │
              │  Regla: ubicación impos. │
              │  Regla: comercio riesgo  │
              │  Suma score              │
              │  ¿Score > umbral?        │
              │  → Crear caso            │
              └──────────┬───────────────┘
                         │
               ┌─────────┴─────────┐
               ▼                   ▼
     ┌─────────────────┐  ┌──────────────┐
     │ Table Storage   │  │ Blob Storage │
     │ - transacciones │  │ documentos   │
     │ - casos         │  │ verificacion │
     │ - configuracion │  └──────────────┘
     └─────────────────┘

Servicios compartidos:
  ┌──────────────┐  ┌────────────────────┐
  │ Key Vault    │  │ Application Insights│
  │ - Secretos   │  │ - Métricas         │
  │ - Managed ID │  │ - Logs             │
  └──────────────┘  └────────────────────┘
```

---

## Base de datos

No usamos SQL. Usamos **Azure Table Storage** (NoSQL clave-valor), suficiente para el volumen del proyecto y mucho más barato.

| Tabla / Contenedor | Partition Key | Row Key | Uso |
|-------------------|---------------|---------|-----|
| `transacciones` | `account_id` | `transaction_id` | Historial de transacciones + scores. TTL: 30 días |
| `casos` | `case_id` | `case_id` | Casos de fraude, evidencia y auditoría |
| `configuracion` | `config_type` | `config_key` | Umbral, reglas activas, lista negra de comercios |
| `verificaciones` (blob) | carpeta por `case_id` | — | PDFs e imágenes de verificación |

---

## Infraestructura desplegada en Azure

### Resource Group
`rg-centinela` (West US)

### Recursos

| Recurso | Nombre | Propósito |
|---------|--------|-----------|
| Storage Account | `stcentinelaufwhov` | Tablas, cola y blobs |
| Key Vault | `kv-centinela-ufwhov` | Secretos (connection strings, API keys) |
| Application Insights | `appi-centinela-ufwhov` | Monitoreo y dashboards |
| Log Analytics | `log-centinela-ufwhov` | Workspace de logs |
| Function API | `func-api-1784119485` | Endpoint REST de transacciones |
| Function Scoring | `func-scoring-1784119485` | Motor de reglas y scoring |

### Seguridad

- **Managed Identity:** Cada Function tiene su propia identidad en Azure AD
- **RBAC:** Las identidades tienen permisos específicos sobre Storage y Key Vault (sin claves)
- **HTTPS forzado:** Todo el tráfico es HTTPS
- **Firewall Storage:** `Allow` + `AzureServices` bypass; la seguridad se basa en RBAC

### Roles asignados

| Identity | Roles |
|----------|-------|
| func-api | Storage Table Data Contributor, Storage Queue Data Contributor, Key Vault Secrets User |
| func-scoring | Storage Table Data Contributor, Storage Queue Data Contributor, Key Vault Secrets User |

---

## Equipo

| Persona | Rol | Responsabilidades |
|---------|-----|-------------------|
| **Valentina** | Infraestructura Azure | Bicep, scripts, CI/CD, seguridad, Key Vault, App Insights |
| **Jesús** | Frontend | Jinja2 templates, login, paneles de analista/admin/auditor, seguridad frontend |
| **Brallan** | Reglas + Admin API | Persistencia (Table Storage), 4 reglas de detección, endpoints admin |
| **Daniel** | Backend | API de ingesta, motor de scoring, QueueTrigger, JWT, explicador, verificación documental |

---

## Presupuesto

| Servicio | Costo estimado |
|----------|---------------|
| Azure Functions (Consumption) | ~$0 (1M ejecuciones/mes gratis) |
| Queue Storage | ~$0 (primeros 1GB gratis) |
| Table Storage | ~$0.10/GB |
| Blob Storage | ~$0.02/GB |
| Key Vault | ~$0 (10K transacciones gratis) |
| Application Insights | ~$0 (1GB/mes gratis) |
| AI Document Intelligence | ~$1-2 |
| **Total mensual** | **< $10 USD** |

Meta: gastar menos de **$60 USD** de los **$200 USD** de crédito de la cuenta gratuita.

---

## Cómo empezar

### Requisitos
- Python 3.11+
- Azure CLI
- Cuenta Azure (crédito gratuito)
- Git

### Clonar

```bash
git clone https://github.com/ValenColm/centinela.git
cd centinela
```

### Flujo de trabajo (cada miembro)

```bash
git checkout -b tu-rama     # crear rama propia (ej: jesus/frontend)
# ... trabajar, hacer commits ...
git push origin tu-rama     # subir cambios
# → Abrir Pull Request a main en GitHub
# → Valentina revisa y mergea
# → CI/CD despliega automáticamente
```

---

## Documentación

| Archivo | Contenido |
|---------|-----------|
| `requisitos.md` | Requisitos completos, contratos API, cronograma, dependencias |
| `CONTRIBUTING.md` | Flujo de trabajo, reglas de Git, PRs |
| `docs/infra-completa.md` | Infraestructura detallada, arquitectura, recursos |
| `docs/errores-resueltos.md` | Errores encontrados y cómo se solucionaron |
| `docs/pendiente-semana.md` | Estado actual y próximas tareas |

---

## Licencia

Proyecto académico / interno.
