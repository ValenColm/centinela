import os
import shutil
import jwt
import datetime
import jinja2
from fastapi import FastAPI, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Optional

from api.models import (
    UserSession, RuleConfig, MerchantConfig, SystemConfig, 
    AuditLogEntry, RuleEvidence, Case
)
from api.middleware import AuthAndSecurityMiddleware, JWT_SECRET, JWT_ALGORITHM

# Create upload directory
UPLOAD_DIR = "frontend/static/uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI(title="Centinela API & Frontend")

# Register middleware
app.add_middleware(AuthAndSecurityMiddleware)

# Mount static files and setup templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

# Use a Jinja2 Environment directly to avoid the unhashable-dict cache bug
# in newer Jinja2 versions when globals are passed as part of the cache key.
# Setting cache_size=0 disables the LRU cache entirely.
_jinja2_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("frontend/templates"),
    autoescape=True,
    auto_reload=True,
    cache_size=0,
)
templates = Jinja2Templates(env=_jinja2_env)

# Mock Credentials
MOCK_USERS = {
    "admin": {"password": "admin123", "role": "admin", "name": "Admin Centinela"},
    "analyst": {"password": "analyst123", "role": "analyst", "name": "Jesús Analista"},
    "auditor": {"password": "auditor123", "role": "auditor", "name": "Daniel Auditor"}
}

# In-Memory Mock Database
system_config = SystemConfig(
    umbral=60,
    reglas=[
        RuleConfig(nombre="velocidad_transaccion", puntos=35, activa=True),
        RuleConfig(nombre="monto_atípico", puntos=30, activa=True),
        RuleConfig(nombre="ubicacion_imposible", puntos=25, activa=True),
        RuleConfig(nombre="comercio_riesgo", puntos=20, activa=True)
    ],
    comercios=[
        MerchantConfig(merchant_id="M001", name="Casino Virtual VIP", category="casino"),
        MerchantConfig(merchant_id="M002", name="Cryptos Facil", category="crypto"),
        MerchantConfig(merchant_id="M003", name="Joyeria Imperial", category="luxury")
    ]
)

audit_logs = [
    AuditLogEntry(fecha="2026-07-15 08:30:12", usuario="Admin Centinela", accion="modificar_umbral", detalle="Se cambió el umbral del score global a 60 puntos."),
    AuditLogEntry(fecha="2026-07-15 08:35:45", usuario="System", accion="generar_caso", detalle="Caso CASE-2026-001 generado de forma automática."),
    AuditLogEntry(fecha="2026-07-15 08:40:02", usuario="System", accion="generar_caso", detalle="Caso CASE-2026-002 generado de forma automática."),
    AuditLogEntry(fecha="2026-07-15 09:10:30", usuario="Jesús Analista", accion="cambiar_estado", detalle="Caso CASE-2026-002 cambiado a 'en_revision'.")
]

cases_db = [
    Case(
        case_id="CASE-2026-001",
        transaction_id="TXN-90231",
        account_id="ACC-8839",
        score=85,
        monto=1200.0,
        explicacion="Esta cuenta ha realizado 5 transacciones de alto valor en los últimos 3 minutos desde tres dispositivos distintos, excediendo la regla de velocidad de transacción.",
        estado="abierto",
        documentos=[],
        audit_log=[
            AuditLogEntry(fecha="2026-07-15 08:35:45", usuario="System", accion="crear_caso", detalle="Alerta inicial disparada por score de 85.")
        ],
        reglas_disparadas=[
            RuleEvidence(
                regla="velocidad_transaccion", puntos=35, disparada=True,
                evidencia={"transacciones_en_ventana": 5, "ventana_minutos": 3, "promedio_historico": "1 trans/hr"}
            ),
            RuleEvidence(
                regla="monto_atípico", puntos=30, disparada=True,
                evidencia={"monto_historico_promedio": 150.0, "desviacion_veces": 8.0}
            ),
            RuleEvidence(
                regla="comercio_riesgo", puntos=20, disparada=True,
                evidencia={"nombre_comercio": "Cryptos Facil", "id_comercio": "M002", "categoria": "crypto"}
            )
        ],
        creado_en="2026-07-15 08:35:45"
    ),
    Case(
        case_id="CASE-2026-002",
        transaction_id="TXN-90245",
        account_id="ACC-1294",
        score=92,
        monto=3500.0,
        explicacion="Transacción realizada en Madrid 10 minutos después de una compra física en Bogotá (velocidad física imposible); además, el comercio destino es un casino online.",
        estado="en_revision",
        documentos=["/static/uploads/identidad_temporal.png"] if os.path.exists(f"{UPLOAD_DIR}/identidad_temporal.png") else [],
        audit_log=[
            AuditLogEntry(fecha="2026-07-15 08:40:02", usuario="System", accion="crear_caso", detalle="Alerta inicial disparada por score de 92."),
            AuditLogEntry(fecha="2026-07-15 09:10:30", usuario="Jesús Analista", accion="cambiar_estado", detalle="Estado transicionado a 'en_revision' para análisis documental.")
        ],
        reglas_disparadas=[
            RuleEvidence(
                regla="ubicacion_imposible", puntos=25, disparada=True,
                evidencia={"ciudad_actual": "Madrid", "pais_actual": "España", "ciudad_anterior": "Bogotá", "pais_anterior": "Colombia", "distancia_km": 8000, "tiempo_minutos": 10}
            ),
            RuleEvidence(
                regla="monto_atípico", puntos=30, disparada=True,
                evidencia={"monto_historico_promedio": 400.0, "desviacion_veces": 8.75}
            ),
            RuleEvidence(
                regla="comercio_riesgo", puntos=20, disparada=True,
                evidencia={"nombre_comercio": "Casino Virtual VIP", "id_comercio": "M001", "categoria": "casino"}
            )
        ],
        creado_en="2026-07-15 08:40:02"
    ),
    Case(
        case_id="CASE-2026-003",
        transaction_id="TXN-88192",
        account_id="ACC-9041",
        score=45,
        monto=500.0,
        explicacion="Monto de transacción 4x superior al promedio pero la cuenta presenta transacciones históricas similares en fechas festivas.",
        estado="resuelto_descarte",
        documentos=[],
        audit_log=[
            AuditLogEntry(fecha="2026-07-14 15:10:00", usuario="System", accion="crear_caso", detalle="Caso creado de forma preventiva con score de 45."),
            AuditLogEntry(fecha="2026-07-14 16:30:00", usuario="Jesús Analista", accion="cambiar_estado", detalle="Resuelto como descarte. Justificación: Patrón histórico confirmado.")
        ],
        reglas_disparadas=[
            RuleEvidence(
                regla="monto_atípico", puntos=30, disparada=True,
                evidencia={"monto_historico_promedio": 125.0, "desviacion_veces": 4.0}
            )
        ],
        creado_en="2026-07-14 15:10:00"
    ),
    Case(
        case_id="CASE-2026-004",
        transaction_id="TXN-90112",
        account_id="ACC-7729",
        score=97,
        monto=7500.0,
        explicacion="La transacción se ha dirigido a un comercio catalogado como fraude de lujo en lista negra y excede el umbral de monto.",
        estado="resuelto_fraude",
        documentos=[],
        audit_log=[
            AuditLogEntry(fecha="2026-07-14 11:20:00", usuario="System", accion="crear_caso", detalle="Alerta crítica disparada por score de 97."),
            AuditLogEntry(fecha="2026-07-14 12:45:00", usuario="Jesús Analista", accion="cambiar_estado", detalle="Resuelto como fraude. Cuenta bloqueada y fondos congelados.")
        ],
        reglas_disparadas=[
            RuleEvidence(
                regla="comercio_riesgo", puntos=20, disparada=True,
                evidencia={"nombre_comercio": "Joyeria Imperial", "id_comercio": "M003", "categoria": "luxury"}
            ),
            RuleEvidence(
                regla="monto_atípico", puntos=30, disparada=True,
                evidencia={"monto_historico_promedio": 300.0, "desviacion_veces": 25.0}
            )
        ],
        creado_en="2026-07-14 11:20:00"
    )
]

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

# --- Routes ---

@app.get("/")
async def root(request: Request):
    return RedirectResponse(url="/casos", status_code=303)

@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, error: Optional[str] = None):
    return templates.TemplateResponse(request, "login.html", {"error": error})

@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    user = MOCK_USERS.get(username)
    if not user or user["password"] != password:
        return templates.TemplateResponse(request, "login.html", {"error": "Credenciales inválidas. Inténtelo de nuevo."})
    
    # Generate token
    token = create_access_token({"username": username, "name": user["name"], "role": user["role"]})
    
    response = RedirectResponse(url="/casos", status_code=303)
    
    # Secure=True would break local development without HTTPS, so we set it conditionally
    is_secure = request.url.scheme == "https"
    response.set_cookie(
        key="session_token", 
        value=token, 
        httponly=True, 
        secure=is_secure, 
        samesite="lax",
        max_age=86400  # 24 hours
    )
    return response

@app.get("/logout")
async def logout(request: Request):
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response

@app.get("/casos", response_class=HTMLResponse)
async def list_cases(request: Request):
    return templates.TemplateResponse(request, "casos.html", {
        "current_user": request.state.user,
        "active_page": "casos",
        "casos": cases_db
    })

@app.get("/casos/{case_id}", response_class=HTMLResponse)
async def case_detail(request: Request, case_id: str):
    caso = next((c for c in cases_db if c.case_id == case_id), None)
    if not caso:
        return HTMLResponse(content="Caso no encontrado", status_code=404)
    return templates.TemplateResponse(request, "caso_detalle.html", {
        "current_user": request.state.user,
        "active_page": "casos",
        "caso": caso
    })

@app.post("/casos/{case_id}/estado")
async def change_case_status(request: Request, case_id: str, estado: str = Form(...)):
    caso = next((c for c in cases_db if c.case_id == case_id), None)
    if not caso:
        return HTMLResponse(content="Caso no encontrado", status_code=404)
    
    user = request.state.user
    old_status = caso.estado
    caso.estado = estado
    
    # Audit log
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="cambiar_estado",
        detalle=f"Estado del caso cambiado de '{old_status}' a '{estado}'."
    )
    caso.audit_log.append(entry)
    
    # Global log
    audit_logs.append(AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="cambiar_estado",
        detalle=f"Estado del caso {case_id} cambiado de '{old_status}' a '{estado}'."
    ))
    
    return RedirectResponse(url=f"/casos/{case_id}", status_code=303)

@app.post("/casos/{case_id}/subir-documento")
async def upload_case_document(request: Request, case_id: str, documento: UploadFile = File(...)):
    caso = next((c for c in cases_db if c.case_id == case_id), None)
    if not caso:
        return HTMLResponse(content="Caso no encontrado", status_code=404)
    
    # Save file to uploads folder
    file_ext = os.path.splitext(documento.filename)[1]
    filename = f"{case_id}_{int(datetime.datetime.now().timestamp())}{file_ext}"
    filepath = os.path.join(UPLOAD_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(documento.file, buffer)
        
    static_url = f"/static/uploads/{filename}"
    caso.documentos.append(static_url)
    
    user = request.state.user
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Audit log
    entry = AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="subir_documento",
        detalle=f"Documento adjunto: {documento.filename}"
    )
    caso.audit_log.append(entry)
    
    # Global log
    audit_logs.append(AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="subir_documento",
        detalle=f"Se subió documento '{documento.filename}' para el caso {case_id}."
    ))
    
    return RedirectResponse(url=f"/casos/{case_id}", status_code=303)

@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    return templates.TemplateResponse(request, "admin.html", {
        "current_user": request.state.user,
        "active_page": "admin",
        "config": system_config
    })

@app.post("/admin/umbral")
async def update_threshold(request: Request, umbral: int = Form(...)):
    user = request.state.user
    old_val = system_config.umbral
    system_config.umbral = umbral
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    audit_logs.append(AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="modificar_umbral",
        detalle=f"Umbral del score global cambiado de {old_val} a {umbral}."
    ))
    
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/reglas")
async def update_rules(request: Request):
    user = request.state.user
    form_data = await request.form()
    
    updated_rules = []
    for regla in system_config.reglas:
        is_checked = f"regla_{regla.nombre}" in form_data
        old_val = regla.activa
        regla.activa = is_checked
        
        if old_val != is_checked:
            status_text = "Activada" if is_checked else "Desactivada"
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            audit_logs.append(AuditLogEntry(
                fecha=now_str,
                usuario=user["name"],
                accion="modificar_regla",
                detalle=f"Regla '{regla.nombre}' {status_text}."
            ))
            
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/comercios")
async def add_merchant(
    request: Request, 
    merchant_id: str = Form(...), 
    name: str = Form(...), 
    category: str = Form(...)
):
    user = request.state.user
    
    # Check if merchant already exists
    exists = any(c.merchant_id == merchant_id for c in system_config.comercios)
    if exists:
        return RedirectResponse(url="/admin", status_code=303)
        
    merchant = MerchantConfig(merchant_id=merchant_id, name=name, category=category)
    system_config.comercios.append(merchant)
    
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    audit_logs.append(AuditLogEntry(
        fecha=now_str,
        usuario=user["name"],
        accion="agregar_comercio",
        detalle=f"Se agregó el comercio '{name}' (ID: {merchant_id}) a la lista de riesgo."
    ))
    
    return RedirectResponse(url="/admin", status_code=303)

@app.post("/admin/comercios/{merchant_id}/eliminar")
async def remove_merchant(request: Request, merchant_id: str):
    user = request.state.user
    merchant = next((c for c in system_config.comercios if c.merchant_id == merchant_id), None)
    
    if merchant:
        system_config.comercios.remove(merchant)
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        audit_logs.append(AuditLogEntry(
            fecha=now_str,
            usuario=user["name"],
            accion="eliminar_comercio",
            detalle=f"Se eliminó el comercio '{merchant.name}' (ID: {merchant_id}) de la lista de riesgo."
        ))
        
    return RedirectResponse(url="/admin", status_code=303)

@app.get("/auditor", response_class=HTMLResponse)
async def auditor_panel(request: Request):
    return templates.TemplateResponse(request, "auditor.html", {
        "current_user": request.state.user,
        "active_page": "auditor",
        "config": system_config,
        "logs": sorted(audit_logs, key=lambda x: x.fecha, reverse=True)
    })
