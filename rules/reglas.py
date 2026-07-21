import math
from datetime import timezone

from persistence.models import Location, RuleResult, Transaction


def regla_velocidad(
    account_id: str,
    historial: list[Transaction],
    umbral_velocidad: int = 5,
    ventana_minutos: int = 3,
    puntos_velocidad: int = 35,
) -> RuleResult:
    if not historial:
        return RuleResult(
            regla="velocidad_transaccion",
            puntos=0,
            disparada=False,
            evidencia={
                "transacciones_en_ventana": 0,
                "ventana_minutos": ventana_minutos,
                "promedio_historico": "sin historial",
                "umbral_velocidad": umbral_velocidad,
                "motivo": "No hay historial para evaluar velocidad",
            },
        )

    count = len(historial)
    disparada = count >= umbral_velocidad

    return RuleResult(
        regla="velocidad_transaccion",
        puntos=puntos_velocidad if disparada else 0,
        disparada=disparada,
        evidencia={
            "transacciones_en_ventana": count,
            "ventana_minutos": ventana_minutos,
            "promedio_historico": f"{count} en {ventana_minutos} minutos",
            "umbral_velocidad": umbral_velocidad,
            "motivo": (
                f"Se detectaron {count} transacciones en los últimos "
                f"{ventana_minutos} minutos (umbral: {umbral_velocidad})"
                if disparada
                else f"Solo {count} transacciones en la ventana (umbral: {umbral_velocidad})"
            ),
        },
    )


def regla_monto_atipico(
    transaction: Transaction,
    historial: list[Transaction],
    factor: float = 2.0,
    puntos_monto: int = 30,
) -> RuleResult:
    if not historial:
        return RuleResult(
            regla="monto_atipico",
            puntos=0,
            disparada=False,
            evidencia={
                "monto_actual": transaction.amount,
                "promedio_historico": 0,
                "factor": factor,
                "multiplicador": 0,
                "motivo": "No hay historial para calcular promedio",
            },
        )

    promedio = sum(t.amount for t in historial) / len(historial)
    if promedio == 0:
        return RuleResult(
            regla="monto_atipico",
            puntos=0,
            disparada=False,
            evidencia={
                "monto_actual": transaction.amount,
                "promedio_historico": 0,
                "factor": factor,
                "multiplicador": 0,
                "motivo": "El promedio histórico es cero",
            },
        )

    multiplicador = round(transaction.amount / promedio, 2)
    disparada = multiplicador >= factor

    return RuleResult(
        regla="monto_atipico",
        puntos=puntos_monto if disparada else 0,
        disparada=disparada,
        evidencia={
            "monto_actual": transaction.amount,
            "promedio_historico": round(promedio, 2),
            "factor": factor,
            "multiplicador": multiplicador,
            "motivo": (
                f"El monto de ${transaction.amount:,.0f} supera en "
                f"{multiplicador}x el promedio histórico (${promedio:,.0f})"
                if disparada
                else f"Monto ${transaction.amount:,.0f} dentro de lo normal "
                f"({multiplicador}x del promedio ${promedio:,.0f})"
            ),
        },
    )


def _haversine(loc1: Location, loc2: Location) -> float:
    R = 6371
    dlat = math.radians(loc2.latitude - loc1.latitude)
    dlon = math.radians(loc2.longitude - loc1.longitude)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(loc1.latitude))
        * math.cos(math.radians(loc2.latitude))
        * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def regla_ubicacion_imposible(
    transaction: Transaction,
    ultima_transaccion: Transaction | None,
    velocidad_max_kmh: float = 900.0,
    puntos_ubicacion: int = 17,
) -> RuleResult:
    if not ultima_transaccion:
        return RuleResult(
            regla="ubicacion_imposible",
            puntos=0,
            disparada=False,
            evidencia={
                "ubicacion_anterior": None,
                "ubicacion_actual": transaction.location.model_dump(),
                "distancia_km": 0,
                "tiempo_minutos": 0,
                "velocidad_requerida_kmh": 0,
                "velocidad_maxima_kmh": velocidad_max_kmh,
                "motivo": "No hay transacción anterior para comparar ubicación",
            },
        )

    distancia = _haversine(ultima_transaccion.location, transaction.location)
    diff = transaction.timestamp - ultima_transaccion.timestamp
    minutos = diff.total_seconds() / 60

    if minutos <= 0:
        return RuleResult(
            regla="ubicacion_imposible",
            puntos=puntos_ubicacion,
            disparada=True,
            evidencia={
                "ubicacion_anterior": ultima_transaccion.location.model_dump(),
                "ubicacion_actual": transaction.location.model_dump(),
                "distancia_km": round(distancia, 2),
                "tiempo_minutos": 0,
                "velocidad_requerida_kmh": float("inf"),
                "velocidad_maxima_kmh": velocidad_max_kmh,
                "motivo": "Transacciones simultáneas desde ubicaciones distintas",
            },
        )

    velocidad_requerida = (distancia / minutos) * 60
    disparada = velocidad_requerida > velocidad_max_kmh

    return RuleResult(
        regla="ubicacion_imposible",
        puntos=puntos_ubicacion if disparada else 0,
        disparada=disparada,
        evidencia={
            "ubicacion_anterior": {
                "city": ultima_transaccion.location.city,
                "country": ultima_transaccion.location.country,
                "latitude": ultima_transaccion.location.latitude,
                "longitude": ultima_transaccion.location.longitude,
            },
            "ubicacion_actual": {
                "city": transaction.location.city,
                "country": transaction.location.country,
                "latitude": transaction.location.latitude,
                "longitude": transaction.location.longitude,
            },
            "distancia_km": round(distancia, 2),
            "tiempo_minutos": round(minutos, 2),
            "velocidad_requerida_kmh": round(velocidad_requerida, 2),
            "velocidad_maxima_kmh": velocidad_max_kmh,
            "motivo": (
                f"Distancia de {distancia:,.0f} km en {minutos:.0f} minutos "
                f"requiere {velocidad_requerida:,.0f} km/h (máx: {velocidad_max_kmh})"
                if disparada
                else f"Ubicación viable: {distancia:,.0f} km en {minutos:.0f} min "
                f"({velocidad_requerida:,.0f} km/h)"
            ),
        },
    )


def regla_comercio_riesgo(
    transaction: Transaction,
    comercios_riesgo: list[dict],
    puntos_comercio: int = 20,
) -> RuleResult:
    merchant_id = transaction.merchant.id
    categoria = transaction.merchant.category

    for riesgo in comercios_riesgo:
        riesgo_id = riesgo.get("merchant_id", "")
        riesgo_cat = riesgo.get("categoria", "")

        if riesgo_id and riesgo_id == merchant_id:
            return RuleResult(
                regla="comercio_riesgo",
                puntos=puntos_comercio,
                disparada=True,
                evidencia={
                    "merchant_id": merchant_id,
                    "merchant_name": transaction.merchant.name,
                    "categoria": categoria,
                    "tipo_coincidencia": "merchant_id",
                    "motivo": f"Comercio {transaction.merchant.name} ({merchant_id}) está en lista negra",
                },
            )

        if riesgo_cat and riesgo_cat == categoria:
            return RuleResult(
                regla="comercio_riesgo",
                puntos=puntos_comercio,
                disparada=True,
                evidencia={
                    "merchant_id": merchant_id,
                    "merchant_name": transaction.merchant.name,
                    "categoria": categoria,
                    "tipo_coincidencia": "categoria",
                    "motivo": f"Categoría '{categoria}' está marcada como riesgo",
                },
            )

    return RuleResult(
        regla="comercio_riesgo",
        puntos=0,
        disparada=False,
        evidencia={
            "merchant_id": merchant_id,
            "merchant_name": transaction.merchant.name,
            "categoria": categoria,
            "tipo_coincidencia": None,
            "motivo": f"Comercio {transaction.merchant.name} no está en lista negra",
        },
    )
