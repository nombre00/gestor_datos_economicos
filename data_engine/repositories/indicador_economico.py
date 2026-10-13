import logging
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from data_engine.models import IndicadorEconomico

logger = logging.getLogger(__name__)

DOS_DECIMALES = Decimal("0.01")


def guardar(registros):
    resumen = {"creados": 0, "actualizados": 0, "sin_cambios": 0}

    por_indicador = defaultdict(list)
    for r in registros:
        por_indicador[r["indicador"]].append(r)

    for indicador, filas in por_indicador.items():
        existentes = {
            obj.fecha: obj
            for obj in IndicadorEconomico.objects.filter(indicador=indicador)
        }

        nuevos, cambiados = [], []
        for r in filas:
            obj = existentes.get(r["fecha"])
            if obj is None:
                nuevos.append(IndicadorEconomico(**r))
                continue

            valor_actual = obj.valor.quantize(DOS_DECIMALES, rounding=ROUND_HALF_UP)
            if valor_actual != r["valor"]:
                logger.warning(
                    "Cambio detectado en %s %s: %s -> %s",
                    indicador, r["fecha"], valor_actual, r["valor"],
                )
                obj.valor = r["valor"]
                cambiados.append(obj)
            else:
                resumen["sin_cambios"] += 1

        with transaction.atomic():
            IndicadorEconomico.objects.bulk_create(nuevos, batch_size=1000)
            IndicadorEconomico.objects.bulk_update(cambiados, ["valor"], batch_size=1000)

        resumen["creados"] += len(nuevos)
        resumen["actualizados"] += len(cambiados)

    return resumen