"""
serie_historica_deuda.py (repository)

Persiste RegistroSerieHistoricaDeuda (dataclasses del transformador) en la
tabla SerieHistoricaDeuda de Postgres. Detecta y loguea cuando una fila ya
existente cambia de valor entre una carga y otra — útil tanto para notar 
revisiones reales de Hacienda como para detectar bugs del propio pipeline.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Iterable

from data_engine.models import SerieHistoricaDeuda
from data_engine.services.transform.serie_historica_deuda import (
    RegistroSerieHistoricaDeuda,
)

logger = logging.getLogger(__name__)

# Campos "de negocio" a comparar entre lo que ya existe en BD y lo entrante.
# fecha_carga queda fuera a propósito: siempre cambia (auto_now_add) y no es
# un dato de la fuente, sino metadata de cuándo se ingestó.
_CAMPOS_A_COMPARAR = ["anio", "monto_millones", "pct_pib", "es_corte_parcial", "fuente"]


def guardar(registros: Iterable[RegistroSerieHistoricaDeuda]) -> dict[str, int]:
    """
    Persiste los registros entrantes. Para cada uno:
      - Si no existe una fila con la misma clave única
        (fecha_corte, tipo_deuda, moneda), la crea.
      - Si existe y no cambió nada, no hace nada.
      - Si existe y algún campo cambió, actualiza y deja un log de warning
        con el detalle del cambio (posible revisión de Hacienda o bug propio).

    Devuelve un resumen: {"creados": n, "actualizados": n, "sin_cambios": n}
    """
    resumen = {"creados": 0, "actualizados": 0, "sin_cambios": 0}

    for registro in registros:
        instancia, creado = SerieHistoricaDeuda.objects.get_or_create(
            fecha_corte=registro.fecha_corte,
            tipo_deuda=registro.tipo_deuda,
            moneda=registro.moneda,
            defaults={
                "anio": registro.anio,
                "monto_millones": registro.monto_millones,
                "pct_pib": registro.pct_pib,
                "es_corte_parcial": registro.es_corte_parcial,
                "fuente": registro.fuente,
            },
        )

        if creado:
            resumen["creados"] += 1
            continue

        cambios = _detectar_cambios(instancia, registro)

        if not cambios:
            resumen["sin_cambios"] += 1
            continue

        for campo, (valor_anterior, valor_nuevo) in cambios.items():
            logger.warning(
                "Revisión detectada en SerieHistoricaDeuda"
                "(fecha_corte=%s, tipo_deuda=%s, moneda=%s): "
                "campo '%s' cambió de %s a %s",
                registro.fecha_corte, registro.tipo_deuda, registro.moneda,
                campo, valor_anterior, valor_nuevo,
            )
            setattr(instancia, campo, valor_nuevo)

        instancia.save()
        resumen["actualizados"] += 1

    return resumen


def _normalizar_para_comparar(instancia: SerieHistoricaDeuda, campo: str, valor):
    """Si el campo es DecimalField, cuantiza el valor entrante a la misma
    precisión (decimal_places) que tiene el campo en el modelo, para que la
    comparación no marque como 'cambio' lo que es solo ruido de precisión
    de punto flotante (ej. pct_pib calculado con más decimales de los que
    el campo realmente almacena)."""
    field = instancia._meta.get_field(campo)
    decimal_places = getattr(field, "decimal_places", None)
    if decimal_places is not None and isinstance(valor, Decimal):
        exponente = Decimal(1).scaleb(-decimal_places)
        return valor.quantize(exponente)
    return valor


def _detectar_cambios(
    instancia: SerieHistoricaDeuda,
    registro: RegistroSerieHistoricaDeuda,
) -> dict[str, tuple]:
    """Compara los campos de negocio entre la fila ya guardada y el registro
    entrante. Devuelve {campo: (valor_anterior, valor_nuevo)} solo para los
    campos que difieren."""
    cambios = {}
    for campo in _CAMPOS_A_COMPARAR:
        valor_actual = getattr(instancia, campo)
        valor_nuevo = _normalizar_para_comparar(
            instancia, campo, getattr(registro, campo)
        )
        if valor_actual != valor_nuevo:
            cambios[campo] = (valor_actual, valor_nuevo)
    return cambios