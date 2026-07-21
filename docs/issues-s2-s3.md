# Issues pendientes — Semana 2 y 3

---

## Daniel — Semana 2

### ISSUE-01: Motor de scoring (QueueTrigger)
**Asignado:** Daniel
**Labels:** semana-2, backend, alta

Crear una Azure Function con QueueTrigger que:
- Escuche la cola `transacciones-pendientes`
- Al recibir un mensaje, llame a las 4 reglas de Brallan (`rules/reglas.py`)
- Consulte el historial de la cuenta vía `persistence.query_historial_por_cuenta()`
- Sume los puntos de cada regla = score
- Si score > umbral → crear caso en Table Storage
- Si score ≤ umbral → solo guardar score
- Archivo: `scoring/function.py` o module aparte
- Dependencias: Brallan (reglas), persistencia, cola

### ISSUE-02: POST /api/transacciones + GET /api/transacciones/{id}
**Asignado:** Daniel
**Labels:** semana-2, backend, alta

Implementar en `api/main.py`:
- `POST /api/transacciones` — validar con Pydantic, responder 202 + `transaction_id`, publicar en Queue Storage vía `api/services.py`
- `GET /api/transacciones/{id}` — consultar estado en Table Storage vía `api/adapters.py`
- Rechazar payloads > 100KB con 422/413
- Usar `api/config.py` para settings

### ISSUE-03: Rate limiting por IP
**Asignado:** Daniel
**Labels:** semana-2, backend, media

Implementar rate limiter en `api/middleware.py`:
- Máximo N requests por minuto por IP
- Configurable vía `REQUEST_LIMIT_PER_MINUTE` (default: 100)
- Responder 429 si se excede
- Usar diccionario en memoria o tabla `configuracion`

### ISSUE-04: @requires_role decorator
**Asignado:** Daniel
**Labels:** semana-2, backend, media

Crear decorador `@requires_role("admin", "analyst", "auditor", "service")`:
- Verificar JWT del request
- Comparar rol del token contra roles permitidos
- Responder 403 si no tiene permiso
- Proteger endpoints de admin, auditor y casos

### ISSUE-05: API Key para endpoint público
**Asignado:** Daniel
**Labels:** semana-2, backend, media

- Generar API Key para la fintech
- Guardarla en Key Vault (`kv-centinela-ufwhov`)
- `POST /api/transacciones` validar API Key via header `X-API-Key`
- Leer la key desde Key Vault usando Managed Identity

### ISSUE-06: Pruebas del pipeline completo
**Asignado:** Daniel
**Labels:** semana-2, backend, testing, alta

Escribir tests que:
- Envíen transacción real a `POST /api/transacciones`
- Verifiquen que aparece en la cola
- Simulen QueueTrigger que ejecute reglas
- Verifiquen que se crea caso si score > umbral
- Verificar respuesta 202 antes del procesamiento

---

## Daniel — Semana 3

### ISSUE-07: Explicador determinista
**Asignado:** Daniel
**Labels:** semana-3, backend, explicador, alta

Función que recibe la evidencia de las reglas disparadas y genera texto legible:

```
Transacción marcada con score 82 (umbral: 60).
Se detectaron 3 transacciones en los últimos 4 minutos (+35 puntos).
El monto de $4.200.000 supera en 84x el promedio (+30 puntos).
```

### ISSUE-08: Verificación documental (AI Document Intelligence)
**Asignado:** Daniel
**Labels:** semana-3, backend, AI, media

- Endpoint que recibe archivo, lo guarda en Blob Storage (carpeta del caso)
- Llama a Azure AI Document Intelligence para extraer datos
- Adjuntar resultado al caso en `documentos`

### ISSUE-09: Endpoints de casos con auditoría
**Asignado:** Daniel
**Labels:** semana-3, backend, media

- `GET /api/casos` — listar casos (con filtro por estado)
- `GET /api/casos/{id}` — detalle del caso
- `PUT /api/casos/{id}` — cambiar estado con auditoría (quién, cuándo, qué cambió)

---

## Brallan — Semana 3

### ISSUE-10: Tests unitarios de reglas
**Asignado:** Brallan
**Labels:** semana-3, rules, testing, alta

Escribir tests para cada regla:
- Caso normal (se dispara)
- Caso borde (justo en el umbral)
- Sin historial
- Con historial vacío
- Ubicación: misma ciudad, ciudades posibles, imposibles
- Comercio: en lista negra, por categoría, no listado

### ISSUE-11: Pruebas de carga (10K transacciones)
**Asignado:** Brallan
**Labels:** semana-3, rules, testing, performance, alta

Usar Locust o script Python que mande 10,000 transacciones simuladas:
- Medir tiempo promedio de scoring
- Detectar cuellos de botella
- Ajustar umbrales si hay muchos falsos positivos
- Reportar resultados

### ISSUE-12: Refinar reglas según pruebas
**Asignado:** Brallan
**Labels:** semana-3, rules, media

Ajustar umbrales internos de cada regla según resultados de pruebas de carga y unitarias.

### ISSUE-13: Documentación final de reglas
**Asignado:** Brallan
**Labels:** semana-3, rules, docs, baja

Documentar cada regla con:
- Fórmula / lógica
- Ejemplo concreto
- Qué evidencia devuelve
- Umbrales recomendados

---

## Jesús — Semana 3

### ISSUE-14: Pruebas de seguridad frontend
**Asignado:** Jesús
**Labels:** semana-3, frontend, seguridad, alta

Verificar:
- CSP funciona correctamente (no bloquea recursos propios)
- No hay XSS reflejado ni almacenado
- Las rutas están protegidas por rol (admin no accede como analyst)
- CSRF tokens funcionan en formularios
- Cookies tienen HttpOnly, Secure, SameSite

---

## Valentina — Semana 3

### ISSUE-15: Dashboards en Application Insights
**Asignado:** Valentina
**Labels:** semana-3, infra, monitoreo, alta

Crear dashboards:
- Transacciones por minuto (gráfico de línea)
- Casos abiertos vs resueltos (gráfico de barras)
- Errores por Function (torta/tabla)
- Tiempo de respuesta de la API

### ISSUE-16: Alertas en Application Insights
**Asignado:** Valentina
**Labels:** semana-3, infra, monitoreo, media

Crear alertas:
- Si más de X errores en 5 minutos → email a administradores
- Si 0 transacciones en 30 minutos (posible caída)
- Si tiempo de respuesta promedio > 5 segundos

### ISSUE-17: Key Vault logging y auditoría
**Asignado:** Valentina
**Labels:** semana-3, infra, seguridad, media

Configurar logging en Key Vault:
- Registrar quién lee secretos
- Enviar logs a Log Analytics
- Crear dashboard de accesos al Key Vault
