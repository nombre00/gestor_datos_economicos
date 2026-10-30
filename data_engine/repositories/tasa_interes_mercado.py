import logging
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from data_engine.models import TasaInteresMercado

logger = logging.getLogger(__name__)

SEIS_DECIMALES = Decimal("0.000001")
CAMPOS_A_COMPARAR = ["valor", "instrumento", "plazo_anios", "plazo_etiqueta", "tipo", "nombre"]


def _normalizar(campo, valor):
    if campo == "valor" and valor is not None:
        return Decimal(valor).quantize(SEIS_DECIMALES, rounding=ROUND_HALF_UP)
    return valor


def guardar(registros):
    resumen = {"creados": 0, "actualizados": 0, "sin_cambios": 0}

    existentes = {(o.fecha, o.codigo): o for o in TasaInteresMercado.objects.all()}

    nuevos, cambiados = [], []
    for r in registros:
        clave = (r["fecha"], r["codigo"])
        obj = existentes.get(clave)
        if obj is None:
            nuevos.append(TasaInteresMercado(**r))
            continue

        diferencias = [
            campo for campo in CAMPOS_A_COMPARAR
            if _normalizar(campo, getattr(obj, campo)) != _normalizar(campo, r[campo])
        ]
        if diferencias:
            logger.warning(
                "Cambio detectado en %s: %s",
                clave,
                {c: (getattr(obj, c), r[c]) for c in diferencias},
            )
            for campo in diferencias:
                setattr(obj, campo, r[campo])
            cambiados.append(obj)
        else:
            resumen["sin_cambios"] += 1

    with transaction.atomic():
        TasaInteresMercado.objects.bulk_create(nuevos, batch_size=1000)
        TasaInteresMercado.objects.bulk_update(cambiados, CAMPOS_A_COMPARAR, batch_size=1000)

    resumen["creados"] = len(nuevos)
    resumen["actualizados"] = len(cambiados)
    return resumen