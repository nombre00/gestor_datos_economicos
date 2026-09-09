"""
composicion_deuda.py (ingestion)

Orquesta la ingesta completa del archivo Composicion_de_la_Deuda_sep-2025.xlsx:
conecta las 3 combinaciones transform + repository (Moneda, Acreedor,
Legislación) y devuelve un resumen combinado de las 3.

A diferencia de serie_historica_deuda.py (que ingesta un solo dataset desde
un solo Excel), acá "ingestar Composición de la Deuda" es conceptualmente
UNA sola operación de negocio que actualiza 3 tablas a la vez, porque las
3 hojas vienen del mismo archivo -- por eso una sola función ingerir(),
no tres funciones separadas por tabla.
"""

from __future__ import annotations

import logging

from data_engine.repositories.composicion_deuda import (
    guardar_acreedor,
    guardar_legislacion,
    guardar_moneda,
)
from data_engine.services.transform.composicion_deuda import (
    transformar_acreedor,
    transformar_legislacion,
    transformar_moneda,
)

logger = logging.getLogger(__name__)


def ingerir(path_excel: str) -> dict[str, dict[str, int]]:
    """Ingesta las 3 hojas del Excel de Composición de la Deuda.

    Sin manejo de excepciones propio, misma decisión que en
    serie_historica_deuda.py: si falla una hoja, se propaga tal cual en vez
    de tragarse el error o intentar seguir con las otras -- correcto
    mientras no exista un pipeline multi-dataset que deba decidir si un
    dataset fallido frena a los demás.
    """
    resumen_moneda = guardar_moneda(transformar_moneda(path_excel))
    logger.info("Ingesta Composición de la Deuda (Moneda) completada: %s", resumen_moneda)

    resumen_acreedor = guardar_acreedor(transformar_acreedor(path_excel))
    logger.info("Ingesta Composición de la Deuda (Acreedor) completada: %s", resumen_acreedor)

    resumen_legislacion = guardar_legislacion(transformar_legislacion(path_excel))
    logger.info("Ingesta Composición de la Deuda (Legislación) completada: %s", resumen_legislacion)

    return {
        "moneda": resumen_moneda,
        "acreedor": resumen_acreedor,
        "legislacion": resumen_legislacion,
    }