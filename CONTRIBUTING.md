# Cómo trabajar en Centinela

## Ramas

| Rama | Dueño | Propósito |
|---|---|---|
| `main` | Todos | Código estable. Solo se mergea por PR con revisión |
| `valentina/infra` | Valentina | Infraestructura Azure (Bicep, scripts, CI/CD) |
| `jesus/frontend` | Jesús | Frontend (templates Jinja2, login, paneles) |
| `brallan/rules` | Brallan | Reglas de detección, persistencia, admin API |
| `daniel/backend` | Daniel | API, motor scoring, explicador, verificación documental, seguridad |

## Flujo diario

```bash
# 1. Empezar el día: traer cambios de main
git checkout main
git pull
git checkout <tu-rama>
git merge main

# 2. Trabajar normalmente
# ... código, commits ...

# 3. Subir cambios
git push
```

## Pull Requests (PR)

Al final de cada semana (o cuando una funcionalidad esté completa):

1. Ir a GitHub y abrir un PR desde tu rama hacia `main`
2. Asignar a otro miembro del equipo como reviewer
3. El reviewer revisa, comenta si hay algo, y aprueba
4. Hacer merge a `main`

## Reglas

- **Nunca hacer push directo a `main`**. Siempre por PR.
- **Los commits deben ser descriptivos**:
  - `feat: agregar regla de velocidad` (nueva funcionalidad)
  - `fix: corregir cálculo de distancia` (bugfix)
  - `infra: agregar firewall a storage` (infraestructura)
- **Actualizar `main` frecuentemente** para evitar conflictos grandes
- **Si dos personas necesitan trabajar en el mismo archivo**, coordinar por Discord/WhatsApp para no pisarse

## Estructura del proyecto

```
centinela/
├── api/                  # Código de la API (Daniel)
│   ├── main.py
│   ├── models.py         # Pydantic models
│   └── middleware.py     # Auth, rate limiting
├── frontend/             # Templates y estáticos (Jesús)
│   ├── templates/
│   └── static/
├── rules/                # Reglas de detección (Brallan)
│   ├── regla_velocidad.py
│   ├── regla_monto.py
│   ├── regla_ubicacion.py
│   └── regla_comercio.py
├── persistence/          # Capa de datos (Brallan)
│   └── table_storage.py
├── infra/                # Scripts de infraestructura (Valentina)
│   ├── main.bicep
│   └── deploy.sh
├── scoring/              # Motor de scoring (Daniel)
│   └── funcion_scoring.py
├── casos/                # Gestión de casos (Daniel + Brallan)
│   └── ...
├── explicador/           # Explicador de casos (Daniel)
│   └── ...
├── requirements.txt
├── proyecto.md
└── requisitos.md
```
