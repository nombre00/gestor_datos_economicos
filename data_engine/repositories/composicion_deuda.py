"""
composicion_deuda.py (repository)

Persiste los registros de las 3 tablas de Composición de la Deuda
(ComposicionDeudaMoneda, ComposicionDeudaAcreedor, ComposicionDeudaLegislacion)
usando un único motor genérico, en vez de repetir la lógica de
get_or_create + detección de cambios 3 veces (una por tabla).

Decisión tomada en sesión: este motor NO reemplaza el repository ya
existente de SerieHistoricaDeuda (queda como está, por separado); queda
scoped solo a los 3 datasets de Composición de la Deuda, que sí comparten
exactamente el mismo algoritmo sin ninguna diferencia de lógica de negocio
entre ellos -- solo cambia el modelo y qué campos comparar.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable

from data_engine.models import (
    ComposicionDeudaAcreedor,
    ComposicionDeudaLegislacion,
    ComposicionDeudaMoneda,
)

logger = logging.getLogger(__name__)


def _normalizar_para_comparar(modelo, campo: str, valor):
    """Cuantiza el valor entrante a la misma precisión (decimal_places) que
    tiene el campo en el modelo, para evitar falsos positivos de 'cambio'
    por ruido de precisión de punto flotante -- mismo bug ya encontrado y
    corregido en el repository de SerieHistoricaDeuda (ahí con pct_pib; acá
    el candidato sería monto_millones, aunque en la práctica no se ha visto
    el problema todavía con estos datasets)."""
    field = modelo._meta.get_field(campo)
    decimal_places = getattr(field, "decimal_places", None)
    if decimal_places is not None and isinstance(valor, Decimal):
        exponente = Decimal(1).scaleb(-decimal_places)
        return valor.quantize(exponente)
    return valor


def _detectar_cambios(modelo, instancia, registro, campos_a_comparar) -> dict[str, tuple]:
    cambios = {}
    for campo in campos_a_comparar:
        valor_actual = getattr(instancia, campo)
        valor_nuevo = _normalizar_para_comparar(modelo, campo, getattr(registro, campo))
        if valor_actual != valor_nuevo:
            cambios[campo] = (valor_actual, valor_nuevo)
    return cambios


def _guardar_generico(
    modelo,
    registros: Iterable,
    campos_clave: list[str],
    campos_a_comparar: list[str],
) -> dict[str, int]:
    """Motor compartido: no sabe nada de moneda/acreedor/legislación, solo
    opera sobre cualquier modelo + configuración de campos recibida."""
    resumen = {"creados": 0, "actualizados": 0, "sin_cambios": 0}

    for registro in registros:
        filtro = {campo: getattr(registro, campo) for campo in campos_clave}
        defaults = {campo: getattr(registro, campo) for campo in campos_a_comparar}

        instancia, creado = modelo.objects.get_or_create(**filtro, defaults=defaults)

        if creado:
            resumen["creados"] += 1
            continue

        cambios = _detectar_cambios(modelo, instancia, registro, campos_a_comparar)

        if not cambios:
            resumen["sin_cambios"] += 1
            continue

        for campo, (valor_anterior, valor_nuevo) in cambios.items():
            logger.warning(
                "Revisión detectada en %s (%s): campo '%s' cambió de %s a %s",
                modelo.__name__, filtro, campo, valor_anterior, valor_nuevo,
            )
            setattr(instancia, campo, valor_nuevo)

        instancia.save()
        resumen["actualizados"] += 1

    return resumen


# Campos comunes a las 3 tablas -- si el día de mañana una tabla necesita
# comparar un campo distinto a las otras, esto deja de ser una constante
# compartida y pasa a definirse por separado en cada función de abajo.
_CAMPOS_A_COMPARAR = ["anio", "monto_millones", "es_corte_parcial", "fuente"]


def guardar_moneda(registros) -> dict[str, int]:
    return _guardar_generico(
        ComposicionDeudaMoneda, registros,
        campos_clave=["fecha_corte", "categoria"],
        campos_a_comparar=_CAMPOS_A_COMPARAR,
    )


def guardar_acreedor(registros) -> dict[str, int]:
    return _guardar_generico(
        ComposicionDeudaAcreedor, registros,
        campos_clave=["fecha_corte", "categoria"],
        campos_a_comparar=_CAMPOS_A_COMPARAR,
    )


def guardar_legislacion(registros) -> dict[str, int]:
    return _guardar_generico(
        ComposicionDeudaLegislacion, registros,
        campos_clave=["fecha_corte", "categoria"],
        campos_a_comparar=_CAMPOS_A_COMPARAR,
    )