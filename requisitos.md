# Centinela — Documento de Requisitos

## Visión general

Centinela es un motor de detección de fraude transaccional en tiempo real. Cada vez que un cliente de la fintech hace una compra, transferencia o retiro, la transacción entra a Centinela, se analiza contra reglas de riesgo, se le asigna un puntaje (score) y se decide si es sospechosa o no.

### Flujo resumido

```
Cliente hace transacción
        ↓
API recibe y responde al instante (202 Accepted)
        ↓
Mensaje encolado en Queue Storage
        ↓
Función serverless scoring toma el mensaje
        ↓
Ejecuta 4 reglas contra el historial de la cuenta
        ↓
Suma puntos = score
        ↓
¿Score > umbral? → Se crea un caso para el analista
        ↓
Analista revisa, ve la explicación, resuelve
```

### Stack tecnológico

| Capa                         | Tecnología                                         |
| ---------------------------- | --------------------------------------------------- |
| API                          | Python + FastAPI sobre Azure Functions HTTP trigger |
| Backend serverless           | Azure Functions (Consumption Plan)                  |
| Cola de mensajes             | Azure Queue Storage                                 |
| Base de datos transacciones  | Azure Table Storage (particionado por cuenta)       |
| Base de datos casos          | Azure Table Storage                                 |
| Documentos de verificación  | Azure Blob Storage                                  |
| Secretos y claves            | Azure Key Vault                                     |
| Monitoreo                    | Application Insights                                |
| Verificación de documentos  | Azure AI Document Intelligence                      |
| Infraestructura como código | Bicep + scripts Azure CLI                           |
| Autenticación               | Managed Identity + JWT / Azure AD                   |
| Frontend                     | Jinja2 templates (HTML + CSS, sin framework JS)     |

---

## Contratos de API (definir el día 1 entre todos)

### Formato de transacción (POST /api/transacciones)

```json
{
  "transaction_id": "uuid-unico",
  "account_id": "id-de-la-cuenta",
  "amount": 1234.50,
  "currency": "COP",
  "timestamp": "2026-07-14T12:00:00Z",
  "location": {
    "city": "Medellin",
    "country": "CO",
    "latitude": 6.2476,
    "longitude": -75.5658
  },
  "merchant": {
    "id": "M001",
    "name": "Almacen XYZ",
    "category": "retail"
  },
  "device_id": "uuid-del-dispositivo"
}
```

### Formato del mensaje en la cola

```json
{
  "transaction_id": "uuid",
  "account_id": "id",
  "amount": 1234.50,
  "currency": "COP",
  "timestamp": "2026-07-14T12:00:00Z",
  "location": { ... },
  "merchant": { ... },
  "device_id": "uuid",
  "received_at": "2026-07-14T12:00:01Z"
}
```

### Formato del resultado de cada regla

```json
{
  "regla": "velocidad_transaccion",
  "puntos": 35,
  "disparada": true,
  "evidencia": {
    "transacciones_en_ventana": 8,
    "ventana_minutos": 3,
    "promedio_historico": "1 cada 6 horas",
    "umbral_velocidad": 5
  }
}
```

### Formato del score completo

```json
{
  "transaction_id": "uuid",
  "account_id": "id",
  "score": 82,
  "umbral": 60,
  "reglas": [ ...array de resultados de reglas... ],
  "decision": "abrir_caso" | "aprobar"
}
```

### Formato del caso

```json
{
  "case_id": "uuid",
  "transaction_id": "uuid",
  "account_id": "id",
  "score": 82,
  "umbral": 60,
  "reglas_disparadas": [ ... ],
  "explicacion": "texto legible generado...",
  "estado": "abierto" | "en_revision" | "resuelto_fraude" | "resuelto_descarte" | "escalado",
  "analista_asignado": "email-del-analista",
  "documentos": [ "url-doc1.pdf" ],
  "audit_log": [
    { "fecha": "2026-07-14T12:00:05Z", "usuario": "sistema", "accion": "creacion", "detalle": "..." }
  ],
  "creado_en": "2026-07-14T12:00:05Z",
  "actualizado_en": "2026-07-14T12:00:05Z"
}
```

---

## Reglas de detección

| Regla                          | Qué detecta                               | Lógica                                                                                     |
| ------------------------------ | ------------------------------------------ | ------------------------------------------------------------------------------------------- |
| **Velocidad**            | Muchas transacciones en poco tiempo        | Si N transacciones en M minutos > umbral → suma puntos. Ej: 8 compras en 3 minutos         |
| **Monto atípico**       | Monto muy superior al historial            | Si monto > factor × promedio histórico → suma puntos. Ej: $4M cuando el promedio es $50K |
| **Ubicación imposible** | Dos transacciones en lugares incompatibles | Distancia / tiempo entre última y actual > velocidad posible (ej: 900 km/h) → suma puntos |
| **Comercio riesgo**      | Comercio o categoría marcada              | Si merchant_id o categoría está en lista negra → suma puntos                             |

Cada regla retorna: `{ "regla": "...", "puntos": N, "disparada": bool, "evidencia": {...} }`

---

## Almacenamiento

| Tabla / Contenedor | Partición                                                 | Row Key                | Uso                                                |
| ------------------ | ---------------------------------------------------------- | ---------------------- | -------------------------------------------------- |
| `Transacciones`  | `account_id`                                             | `transaction_id`     | Historial de transacciones + scores. TTL: 30 días |
| `Casos`          | `case_id`                                                | `case_id`            | Casos de fraude, evidencia, auditoría             |
| `Configuracion`  | `config_type` (ej: "umbral", "regla", "comercio_riesgo") | `config_key`         | Umbral, reglas activas, lista negra                |
| `Documentos`     | Blob container`verificaciones`                           | carpeta por`case_id` | PDFs/imágenes de verificación                    |

---

## Asignación del equipo

---

### Valentina — Infraestructura Azure

Eres la dueña de la nube. Todo lo que toca Azure pasa por vos. Creás los recursos, configurás la seguridad de red, y te asegurás de que todo se pueda recrear desde cero con un solo script.

| Semana | Qué hace                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1      | **Crear la cuenta Azure** (la gratuita con los $200). Crear un **Service Principal** para que los scripts puedan autenticarse sin usuario humano. Escribir los archivos **Bicep** (infraestructura como código) que crean: Resource Group, Storage Account (con Table + Queue + Blob), las Function Apps, Key Vault, Application Insights. Configurar **Managed Identities** para que cada Function pueda acceder a Storage y Key Vault sin usar claves. Configurar **RBAC** (quién puede hacer qué en Azure). Hacer que el firewall de Storage solo acepte conexiones de los servicios Azure |
| 2      | Crear el**script de despliegue** (`deploy.sh`) que ejecuta los archivos Bicep y despliega el código de las Functions. Configurar **GitHub Actions** (o el CI que prefieran) para que cada vez que alguien haga push a `main` se despliegue solo. Asegurarse de que las Functions tengan **HTTPS forzado** y los **App Settings** correctos (conexiones a Storage, referencia a Key Vault)                                                                                                                                                                                                         |
| 3      | Configurar**Application Insights** dashboards: uno para ver transacciones por minuto, otro para casos abiertos, otro para errores. Crear **alertas** (si hay más de X errores en 5 minutos, mandar correo). Configurar **Key Vault logging** para auditar quién lee secretos. Asegurarse de que todo se pueda **reconstruir desde cero** corriendo `bash deploy.sh`                                                                                                                                                                                                                                |

**No te preocupes por:** escribir lógica de negocio, reglas, frontend. Tu mundo es Azure, Bicep y scripts.

---

### Jesús — Frontend (paneles del sistema)

Eres la cara visible del sistema. Hacés que los analistas, administradores y auditores puedan usar Centinela desde el navegador. No necesitás un framework JS moderno: usamos Jinja2 (templates HTML que renderiza FastAPI).

| Semana | Qué hace                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| ------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1      | **Login**: implementar pantalla de inicio de sesión con JWT o Azure AD. Crear el **middleware de sesión** en FastAPI (si no hay token, redirigir al login). Hacer el **layout base** del frontend: navbar con el nombre del usuario, sidebar con las secciones según el rol, footer. Agregar **headers de seguridad HTTP** en todas las respuestas: `Content-Security-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`. Proteger las cookies con `HttpOnly`, `Secure`, `SameSite=Lax` |
| 2      | **Panel del analista**: página que lista los casos abiertos (tabla con: ID, score, fecha, estado). Página de detalle del caso: muestra la explicación generada, las reglas que se dispararon, la evidencia. Botones para **cambiar estado** (abierto → en_revisión → resuelto_fraude / resuelto_descarte). Formulario para **subir documento de verificación** (PDF o imagen) asociado al caso. **CSRF tokens** en todos los formularios para evitar ataques                                                                                    |
| 3      | **Panel de administrador**: página para ver y cambiar el **umbral de score** (input numérico + botón guardar). Página para **activar/desactivar reglas** individualmente. Página para **gestionar comercios de riesgo** (agregar, listar, eliminar). **Panel de auditor**: vista de solo lectura de casos, transacciones y configuración. **Pruebas de seguridad** del frontend: verificar que CSP funciona, que no hay XSS, que las rutas están protegidas por rol                                                                 |

**Trabajás con:** Brallan (porque tus pantallas consumen sus endpoints admin) y Daniel (porque consumís los endpoints de casos y transacciones).

---

### Brallan — Reglas de detección + Admin API + Persistencia

Sos el que construye el cerebro del sistema: las reglas que detectan fraude, la base de datos donde se guarda todo, y los endpoints de configuración que usa el administrador.

| Semana | Qué hace                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | Crear la**capa de persistencia**: una clase o módulo en Python que sepa leer y escribir en Azure Table Storage. Funciones necesarias: `insertar_transaccion()`, `query_historial_por_cuenta(account_id, minutos)`, `insertar_caso()`, `query_casos()`, `actualizar_caso()`, `leer_config()`, `guardar_config()`. Definir las **firmas de las 4 reglas** (qué reciben, qué devuelven) para que Jesús y Daniel puedan trabajar en paralelo. Documentar bien el formato de evidencia de cada regla                                                                                                                                                                       |
| 2      | **Implementar las 4 reglas**: cada una consulta el historial (por account_id), aplica su lógica y retorna puntos + evidencia. **Regla de velocidad**: contar transacciones en los últimos N minutos, comparar con umbral. **Regla de monto atípico**: calcular promedio histórico, comparar con monto actual * factor. **Regla de ubicación imposible**: obtener última ubicación, calcular distancia vs tiempo. **Regla de comercio riesgo**: consultar lista negra, verificar merchant_id y categoría. Crear los **endpoints admin**: `GET/PUT /api/admin/umbral`, `GET/PUT /api/admin/reglas/{nombre}`, `GET/POST/DELETE /api/admin/comercios` |
| 3      | **Pruebas**: escribir tests unitarios para cada regla (casos normales, bordes, sin historial). **Pruebas de carga**: usar Locust o script Python que mande 10,000 transacciones simuladas y mida cuánto tarda el pipeline. **Refinar reglas**: si las pruebas muestran muchos falsos positivos o negativos, ajustar umbrales internos de cada regla. Documentar cada regla con ejemplos                                                                                                                                                                                                                                                                                          |

**Trabajás con:** Daniel (tu capa de persistencia y tus reglas las usa el orquestador de scoring) y Jesús (tus endpoints admin los consume su panel).

---

### Daniel — Backend (API + Motor de scoring + Explicador + Verificación documental + Seguridad backend)

Sos el integrador. Conectás la API que recibe transacciones con el motor que las procesa, el explicador que las justifica y la verificación documental. También ponés la seguridad del backend.

| Semana | Qué hace                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| ------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | **API de ingesta**: crear `POST /api/transacciones` con FastAPI. Validar el payload con **Pydantic** (tipos correctos, rangos válidos, campos requeridos). Responder al instante con `202 Accepted` y el `transaction_id`. **No esperar a que termine el análisis**. Publicar el mensaje en **Queue Storage**. Crear `GET /api/transacciones/{id}` para consultar estado. Configurar **rate limiting** (máximo X requests por minuto por IP). Rechazar payloads grandes (+100KB) o malformados con 422                                                                                                                                                                   |
| 2      | **Motor de scoring**: la función Azure (QueueTrigger) que recibe el mensaje de la cola. Llama a las 4 reglas de Brallan, suma los puntos, compara contra el umbral. Si score > umbral: guardar score en Table, crear caso en Table Storage. Si score ≤ umbral: solo guardar score. **Autenticación**: implementar middleware de JWT para la API. Crear el decorador `@requires_role("admin", "analyst", "auditor", "service")` para proteger endpoints. **API Key** para el endpoint público de transacciones (la fintech llama con una key guardada en Key Vault)                                                                                                                        |
| 3      | **Explicador**: función que recibe la evidencia de las reglas disparadas y genera texto legible con plantilla. Ejemplo: *"Se detectaron 3 transacciones de esta cuenta en los últimos 4 minutos (+35 puntos)"*. **Verificación documental**: endpoint que recibe un archivo, lo guarda en Blob Storage (carpeta del caso), y llama a Azure AI Document Intelligence para extraer nombre, número de ID y fechas. **Auditoría**: en cada cambio de estado de un caso, registrar quién, cuándo y qué cambió en el `audit_log`. **Endpoints de casos**: `GET /api/casos` (listar), `GET /api/casos/{id}` (detalle), `PUT /api/casos/{id}` (cambiar estado, con auditoría) |

**Trabajás con:** todos. Tus endpoints los consume Jesús (frontend), tu motor llama las reglas de Brallan, tu infraestructura depende de Valentina.

---

## Seguridad general (resumen)

| Qué                           | Cómo                                                                                                        | Quién          |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------ | --------------- |
| Secretos en Key Vault          | Nada de connection strings en código. Las Functions leen desde App Settings con`@Microsoft.KeyVault(...)` | Valentina       |
| Managed Identity               | Las Functions se autentican contra Storage y Key Vault sin claves, solo con su identidad de Azure            | Valentina       |
| HTTPS forzado                  | `httpsOnly: true` en la config de la Function App. HTTP redirige a HTTPS                                   | Valentina       |
| Firewall Storage               | Solo acepta tráfico de servicios Azure y de las Managed Identity                                            | Valentina       |
| Autenticación JWT / Azure AD  | Login en el frontend, token JWT firmado. Middleware en FastAPI que verifica el token en cada request         | Daniel          |
| Roles y permisos               | Decorador`@requires_role()` en los endpoints. El frontend oculta botones según el rol                     | Daniel + Jesús |
| API Key para endpoint público | La fintech llama`POST /api/transacciones` con una API Key. Se valida contra Key Vault                      | Daniel          |
| Validación de input           | Pydantic valida tipos, rangos y formatos. Payloads inválidos se rechazan con 422                            | Daniel          |
| Rate limiting                  | Máximo N requests por minuto. Configurable. Evita abusos                                                    | Daniel          |
| Headers de seguridad           | CSP, HSTS, X-Content-Type-Options, X-Frame-Options en todas las respuestas HTTP                              | Jesús          |
| CSRF tokens                    | En todos los formularios del frontend para evitar ataques de falsificación                                  | Jesús          |
| Cookies seguras                | HttpOnly, Secure, SameSite=Lax. La sesión expira automáticamente                                           | Jesús          |
| Auditoría de casos            | Cada cambio de estado se registra con usuario, fecha, valor anterior y nuevo                                 | Daniel          |
| Auditoría de configuración   | Cambios de umbral, reglas y comercios se registran en tabla de auditoría                                    | Daniel          |

---

## Cronograma por semana

### Semana 1 — Fundamentos

| Día | Valentina                                             | Jesús                                        | Brallan                                  | Daniel                                         |
| ---- | ----------------------------------------------------- | --------------------------------------------- | ---------------------------------------- | ---------------------------------------------- |
| 1-2  | Crear cuenta Azure + Service Principal                | Setup proyecto Python + Jinja2 templates base | Estructura de persistencia Table Storage | FastAPI + endpoint POST /transacciones + Queue |
| 3-4  | Escribir Bicep (Storage, Functions, KV, AppInsights)  | Layout base HTML/CSS + navbar + sidebar       | Firmas de las 4 reglas                   | Validación Pydantic + GET /transacciones/{id} |
| 5-6  | Configurar Managed Identity + RBAC + firewall Storage | Pantalla de login + JWT middleware            | Documentar formato evidencia de reglas   | Rate limiting + rechazo payloads inválidos    |
| 7    | Validar que todo se crea desde cero con Bicep         | Headers de seguridad (CSP, HSTS, etc.)        | Tests de persistencia                    | Pruebas de API                                 |

### Semana 2 — El motor

| Día  | Valentina                           | Jesús                            | Brallan                           | Daniel                                        |
| ----- | ----------------------------------- | --------------------------------- | --------------------------------- | --------------------------------------------- |
| 8-9   | Script deploy.sh + GitHub Actions   | Panel analista: listar casos      | Regla velocidad + regla monto     | Motor de scoring (QueueTrigger)               |
| 10-11 | Automatizar deploy de Functions     | Detalle de caso + explicación    | Regla ubicación + regla comercio | Integrar reglas + umbral + creación de casos |
| 12-13 | App Settings + Key Vault references | Botones cambiar estado caso       | Endpoints admin (umbral, reglas)  | Middleware JWT + @requires_role + API Key     |
| 14    | Pruebas de despliegue completo      | Formulario subir documento + CSRF | Endpoints admin (comercios)       | Pruebas del pipeline completo                 |

### Semana 3 — Producción

| Día  | Valentina                       | Jesús                       | Brallan                              | Daniel                                              |
| ----- | ------------------------------- | ---------------------------- | ------------------------------------ | --------------------------------------------------- |
| 15-16 | Dashboards Application Insights | Panel admin (umbral, reglas) | Tests unitarios de reglas            | Explicador determinista                             |
| 17-18 | Alertas en Application Insights | Panel admin (comercios)      | Pruebas de carga (10K transacciones) | Verificación documental (AI Document Intelligence) |
| 19-20 | Key Vault logging + auditoría  | Panel auditor (solo lectura) | Refinar reglas según pruebas        | Endpoints casos con auditoría                      |
| 21    | Validar deploy desde cero       | Pruebas seguridad frontend   | Documentación final de reglas       | Integración final + demo                           |

---

## Presupuesto

| Servicio                       | Costo estimado                                                 |
| ------------------------------ | -------------------------------------------------------------- |
| Azure Functions (Consumption)  | ~$0 (1M ejecuciones gratis / mes)                              |
| Queue Storage                  | ~$0 (primeros 1GB gratis)                                      |
| Table Storage                  | ~$0.10/GB (estimado < 1GB)                                     |
| Blob Storage                   | ~$0.02/GB                                                      |
| Key Vault                      | ~$0 (10,000 transacciones gratis)                              |
| Application Insights           | ~$0 (plan gratuito 1GB/mes)                                    |
| Azure AI Document Intelligence | ~$1-2 (primeras páginas gratis, luego $0.01-0.02 por página) |
| **Total estimado**       | **< $10 USD**                                            |

Meta del proyecto: gastar menos de $60 USD de los $200 de crédito.

---

---

## Flujo de trabajo con Git y CI/CD

### Cómo trabajamos

```
Cada uno en su rama:
  Jesús (jesus/frontend)  ──┐
  Brallan (brallan/rules) ──┤
  Daniel (daniel/backend) ──┤
  Valentina (valentina/infra) ──┤
                              │
                    Abren Pull Request (PR) a main
                              │
                    Valentina revisa y aprueba
                              │
                    Merge a main
                              │
                    GitHub Actions deploya solo a Azure
```

### Reglas del flujo

1. **Cada uno trabaja en su propia rama.** Nadie toca `main` directamente.
2. **Cuando algo funciona** (una funcionalidad completa, no a mitad de camino), se abre un Pull Request en GitHub desde tu rama hacia `main`.
3. **Siempre asignar a Valentina como reviewer** del PR. Ella revisa el código, verifica que no haya errores y decide si se mergea.
4. **Nadie hace merge de su propio PR.** Solo Valentina aprueba y mergea.
5. **Cuando se mergea a `main`, GitHub Actions se activa automáticamente:**
   - Corre `ruff` para verificar que el código no tenga errores de sintaxis
   - Despliega la infraestructura con Bicep en Azure
   - Despliega el código de las Azure Functions
6. **Si el pipeline falla**, llega una notificación en GitHub y hay que revisar qué pasó antes de mergear otra cosa.

### Lo que NO cambia

- Seguimos usando Discord/WhatsApp para coordinar
- Si alguien necesita el código de otro (ej: Jesús necesita los endpoints de Brallan), puede mergear `main` a su rama para traer los cambios
- Si dos personas necesitan modificar el mismo archivo, se coordinan para no pisarse

### La responsabilidad de Valentina

- Es la **única que mergea PRs a `main`**
- Es la **dueña de Azure**: secrets, Service Principal, cuenta gratuita
- Configura el CI/CD (GitHub Actions) y los secrets necesarios
- Revisa que el pipeline no esté quemando crédito al pedo

---

## Reglas que NO debemos olvidar

1. **Ningún secreto en el código.** Todo connection string, API key o contraseña va a Key Vault.
2. **Todo se crea por script.** Si borran toda la infraestructura, `bash deploy.sh` la reconstruye.
3. **Apagar lo que no se usa.** Un Function App olvidada un fin de semana quema crédito al pedo.
4. **Definir contratos el día 1.** Los formatos JSON de transacción, evento, score y caso se acuerdan hoy, no cuando ya hay código escrito.
5. **El cliente no espera.** La API responde 202 antes de procesar. Si alguien diseña algo que hace esperar al cliente, está mal.
6. **Guardar el porqué.** Cada regla que se dispara guarda la evidencia con los datos concretos. Sin eso, el explicador no funciona.
