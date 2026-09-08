"""
serie_historica_deuda.py (ingestion)

Orquesta el flujo completo de ingesta para el dataset "Series Históricas
de Deuda": lee el Excel de origen, lo transforma al formato limpio, y
persiste el resultado en la base de datos. Es la pieza "lego" que conoce
este dataset de principio a fin; la composición de varios datasets se
maneja en pipelines/etl_pipeline.py, no acá.
"""

from __future__ import annotations

import logging

from data_engine.repositories.serie_historica_deuda import guardar
from data_engine.services.transform.serie_historica_deuda import transformar

logger = logging.getLogger(__name__)


def ingerir(path_excel: str) -> dict[str, int]:
    """
    Punto de entrada del dataset. Lee y persiste el Excel de Series
    Históricas de Deuda ubicado en path_excel.

    Devuelve el resumen entregado por el repository:
    {"creados": n, "actualizados": n, "sin_cambios": n}
    """
    logger.info("Iniciando ingesta de Series Históricas de Deuda: %s", path_excel)

    registros = transformar(path_excel)
    logger.info("Transformación completa: %d registros generados", len(registros))

    resumen = guardar(registros)
    logger.info(
        "Ingesta completa: %d creados, %d actualizados, %d sin cambios",
        resumen["creados"], resumen["actualizados"], resumen["sin_cambios"],
    )

    return resumen